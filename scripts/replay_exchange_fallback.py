"""Full retained-request replay with causal recovered books and source fallback."""
import json,sqlite3,zlib,heapq,math,sys
from pathlib import Path
from collections import Counter,defaultdict
from copy import deepcopy
from combos.pricing_service import PricingService
from combos.weighted_fair import WeightPolicy
from combos.pinnacle_feed import fixture_index,normalize
from combos.shadow_engine import quote_price,fee_per_share
from decimal import Decimal,ROUND_CEILING
from shadow_trade_review import stamp
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'runs/shadow_exchange_fallback_20260909';OUT.mkdir(exist_ok=True)
CONFIG=json.loads((ROOT/'config/runtime_nfl_authorized_shadow_20260910.json').read_text())
WEIGHTS=WeightPolicy(**json.loads((ROOT/'config/weighting.json').read_text()))
CUTOFF=stamp('2026-09-10T00:20:00Z')

class State:
    def __init__(self):self.data={}
    def get(self,owner,key,default=None):return self.data.get((owner,key),default)

def decode(raw):return json.loads(zlib.decompress(raw))
totals=Counter();sources=Counter();runs=[];missing=Counter();pending=[];used=defaultdict(float);serial=0
with (OUT/'quotes.jsonl').open('w') as output:
 for run in ('shadow_20260909_161131','shadow_20260909_172437'):
    c=sqlite3.connect(f'file:{ROOT}/runs/{run}/events.sqlite?mode=ro',uri=True)
    manifest=json.loads(c.execute("SELECT value FROM state WHERE owner='runtime' AND key='manifest'").fetchone()[0])
    config=deepcopy(CONFIG)
    # Historical fees/terms and timestamps stay frozen, not refreshed from today.
    config['combo_terms']=manifest['config']['combo_terms']
    state=State();pricer=PricingService(state,config,WEIGHTS);local=Counter()
    maps=pricer.registry.by_ticker;original_keys={m['market_key'] for m in manifest['config']['mappings']}
    newpin=[m for m in config['mappings'] if m['market_key'] not in original_keys and m.get('pinnacle') and not m.get('pricing_block_reason')]
    events=iter(c.execute("SELECT seq,kind,received_at,payload FROM events WHERE kind IN ('observation','fixture_status','venue_reset','unmapped_book','external_raw') ORDER BY seq"))
    event=next(events,None)
    decisions=c.execute("SELECT d.source_seq,e.payload FROM decisions d JOIN events e ON e.seq=json_extract(d.result,'$.decision_event_seq') ORDER BY d.source_seq")
    for seq,raw in decisions:
        while event is not None and event[0]<seq:
            es,kind,at,payload=event;d=decode(payload)
            if kind=='observation':state.data[('observations',d['market_key']+':'+d['venue'])]=d
            elif kind=='fixture_status':
                old=state.get(kind,d['fixture_key'],{})
                state.data[(kind,d['fixture_key'])]=dict(d,started=old.get('started',False) or d['phase'] in ('in_play','finished'))
            elif kind=='venue_reset':
                for (owner,key),v in state.data.items():
                    if owner=='observations' and v['venue']==d['venue']:v.update(active=False,available_at=at,observed_at=at)
            elif kind=='unmapped_book':
                m=maps.get(d['market_ticker'])
                if m is not None:
                    fee=m['fees']['kalshi']
                    row=dict(d,market_key=m['market_key'],venue='kalshi',active=d['valid'],available_at=at,
                        mapping_reference=m['mapping_reference'],fee_reference=fee['reference'],taker_rate=fee['rate'],
                        fee_model=fee.get('fee_model','venue_cash_v2'),balance_precision=fee.get('balance_precision','.0001'),size_unit='payout_dollars')
                    state.data[('observations',m['market_key']+':kalshi')]=row
            elif kind=='external_raw':
                try:
                    fixtures=fixture_index(d['payload'])
                    for m in newpin:
                        row,_=normalize(m,fixtures,at,f'event:{es}',bookmaker='pinnacle+30',snapshot=d,
                            freshness_policy=manifest['config'].get('pinnacle_freshness_policy'))
                        state.data[('observations',m['market_key']+':pinnacle')]=row
                except (ValueError,KeyError,TypeError):local['raw_pinnacle_recovery_error']+=1
            event=next(events,None)
        original=decode(raw);at=original['decision_at'];published=original['decision_completed_at']
        if published>CUTOFF:continue
        local['requests']+=1
        if local['requests']%100000==0:print(run,local['requests'],local['quotes'],flush=True)
        q=original['request'];legs=q['mve_selected_legs']
        if not original.get('creator_policy_eligible',True):local['creator_policy_blocked']+=1;continue
        if original.get('processing_lag_seconds',0)>config['maximum_processing_lag_seconds']:local['processing_backlog']+=1;continue
        try:
            pricing=pricer.price(legs,at)
            if not pricing['quote_allowed']:raise ValueError(pricing.get('block_reason','pricing_guard'))
            local['priceable']+=1
            terms=next(v for k,v in config['combo_terms'].items() if q['market_ticker'].startswith(k))
            if published>=terms['valid_until']:raise ValueError('combo_fee_expired')
            edge=config['minimum_net_edge_per_share'];rate=terms['maker_fee_rate']
            price=quote_price(pricing['joint']['point'],edge,rate,terms['price_ranges'])
            fixed=q.get('contracts_fp')
            qty=float(fixed) if fixed and float(fixed)>0 else int((Decimal(str(q['target_cost_dollars']))/Decimal(str(price))).to_integral_value(rounding=ROUND_CEILING))
            fee=fee_per_share(price,rate);loss=1-price+fee
            qty=math.floor(min(qty,config['maximum_ticket_gross_liability_dollars']/loss)*100+1e-9)/100
            if qty<.01:raise ValueError('ticket_too_small')
            while pending and pending[0][0]<=published:
                _,_,cost,buckets=heapq.heappop(pending)
                for b in buckets:used[b]-=cost
            mult=pricing['risk_multiplier']
            limits={'total':config['maximum_committed_dollars']}
            limits.update({'contract:'+k:config['per_contract_dollars']*mult for k in set(pricing['contracts'])})
            limits.update({'fixture:'+k:config['per_fixture_dollars']*mult for k in set(pricing['fixtures'])})
            limits['combo:'+q['market_ticker']]=config['per_combo_dollars']*mult
            cost=qty*loss
            if any(used[k]+cost>cap+1e-8 for k,cap in limits.items()):raise ValueError('pending_gross_risk_limit')
            expiry=min(at+config['quote_lifetime_seconds'],CUTOFF)
            if expiry<=published:raise ValueError('expired_before_publication')
            serial+=1
            for b in limits:used[b]+=cost
            heapq.heappush(pending,(expiry,serial,cost,list(limits)))
            source_sets=[','.join(sorted(l['venues'])) for l in pricing['legs']];sources.update(source_sets)
            brief={k:pricing[k] for k in ('joint','stressed_upper','risk_multiplier','contracts','fixtures')}
            brief['source_sets']=source_sets
            row=dict(run=run,quote_key=f'{run}:{seq}',source_seq=seq,rfq_id=q['id'],request=q,
                market_ticker=q['market_ticker'],creator_id=original['creator_id'],creator_policy=original['creator_policy'],
                decision_at=at,decision_completed_at=published,received_at=original['received_at'],expires_at=expiry,valid_until=expiry,
                status='shadow_quote',pricing=brief,quantity=qty,yes_ask=price,leg_count=len(legs),
                required_net_edge_per_share=edge,economics={'maker_fee':qty*fee,'expected_edge':qty*(price-pricing['joint']['point']-fee)},
                original_status=original['status'],original_reason=original.get('reason'))
            output.write(json.dumps(row)+'\n');local['quotes']+=1
        except (ValueError,KeyError,TypeError,StopIteration) as exc:
            reason=str(exc)
            if reason.startswith('no_liquid_fresh_exchange:'):
                missing[reason]+=1;reason='no_liquid_fresh_exchange'
            local[reason]+=1
    c.close();totals.update(local);runs.append(dict(run=run,counts=dict(local)));print(run,dict(local),flush=True)
summary=dict(runs=runs,counts=dict(totals),leg_source_sets=dict(sources),source_exclusions=dict(missing),
    config_mappings=len(CONFIG['mappings']),source_fallback=CONFIG['source_fallback'],cutoff='2026-09-10T00:20:00Z',
    limitations=['Recorded decision clocks and creator eligibility; not new worker timing.',
        'Recovered Kalshi unmapped books and Pinnacle snapshots; missing prices not imputed.',
        'Three-second lifetime; new cancellation decisions not replayed.',
        'Conservative gross pending reservations; no signed hedge offsets or filled inventory in quote admission.',
        'Saved market definitions only; outside-week-one events excluded.'])
(OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))

"""Causal fill-time source/guard checks for all low-price public-tape pairs."""
import json, sqlite3, zlib, heapq
from collections import defaultdict, Counter
from combos.pricing_service import PricingService
from combos.weighted_fair import WeightPolicy
from combos.pinnacle_feed import fixture_index, normalize
from combos.shadow_engine import quote_price
from combos.payoff_risk import canonical_leg_risk
from offsession_inventory_study import load, ROOT, OUT
from offsession_source_diagnostics import State

def run():
    qs,trades=load();pending={};active=defaultdict(dict);expiry=[];targets=defaultdict(list)
    events=sorted([(q['at'],0,i) for i,q in enumerate(qs)]+[(t['at'],1,i) for i,t in enumerate(trades)])
    for at,kind,index in events:
        while expiry and expiry[0][0]<=at:
            _,i=heapq.heappop(expiry);q=qs[i];active[q['ticker']].pop(i,None)
        if kind==0:
            q=qs[index];active[q['ticker']][index]=quote_price(q['fair'],.0005,0,q['grids']);heapq.heappush(expiry,(q['expiry'],index))
        else:
            t=trades[index]
            for i,ask in active[t['ticker']].items():
                if ask<=t['price']+1e-9:targets[qs[i]['run']].append((at,i,t['id']))
    records=[];counts=Counter()
    config=json.loads((ROOT/'config/runtime_nfl_authorized_shadow_20260910.json').read_text())
    weights=WeightPolicy(**json.loads((ROOT/'config/weighting.json').read_text()))
    mapping={m['kalshi_ticker']:m for m in config['mappings']}
    # Recover raw original selected legs; canonical risk orientation alone is
    # deliberately not substituted for exact exchange payoff selection.
    requestlegs={}
    needed={qs[i]['key'] for ts in targets.values() for at,i,tid in ts}
    for raw in (OUT/'candidate_census/quotes.jsonl').open():
        q=json.loads(raw)
        if q['quote_key'] in needed:requestlegs[q['quote_key']]=q['request']['mve_selected_legs']
    for name,tasks in targets.items():
        tasks.sort();ix=0;state=State();pricer=PricingService(state,config,weights)
        db=sqlite3.connect((ROOT/'runs'/name/'events.sqlite').as_uri()+'?mode=ro',uri=True)
        manifest=json.loads(db.execute("SELECT value FROM state WHERE owner='runtime' AND key='manifest'").fetchone()[0])
        original={m['market_key'] for m in manifest['config']['mappings']}
        newpin=[m for m in config['mappings'] if m['market_key'] not in original and m.get('pinnacle') and not m.get('pricing_block_reason')]
        cache={};last_at=None
        def evaluate(task):
            nonlocal last_at
            at,index,tid=task;q=qs[index];legs=requestlegs[q['key']]
            signature=tuple(sorted((l['market_ticker'],l['side']) for l in legs))
            if at!=last_at:cache.clear();last_at=at
            if signature not in cache:
                try:
                    p=pricer.price(legs,at)
                    probs={}
                    for leg in p['legs']:
                        risk=canonical_leg_risk(leg['mapping'],leg['selected_side'])
                        selected=leg['fair']['point'] if leg['selected_side']=='yes' else 1-leg['fair']['point']
                        probs[risk['key']]=selected if risk['selected_sign']==1 else 1-selected
                    cache[signature]={'available':True,'allowed':p['quote_allowed'],'point':p['joint']['point'],'risk_multiplier':p['risk_multiplier'],'probs':probs}
                except (ValueError,KeyError,TypeError) as e:cache[signature]={'available':False,'reason':str(e)}
            result={'quote_key':q['key'],'trade_id':tid,**cache[signature]};records.append(result)
            counts['available' if result['available'] else result['reason'].split(':')[0]]+=1
        clock=0
        for seq,kind,at,raw in db.execute("SELECT seq,kind,received_at,payload FROM events WHERE kind IN ('observation','fixture_status','venue_reset','unmapped_book','external_raw','heartbeat') ORDER BY seq"):
            clock=max(clock,at)
            while ix<len(tasks) and tasks[ix][0]<clock:evaluate(tasks[ix]);ix+=1
            if ix==len(tasks):break
            if kind=='heartbeat':continue
            d=json.loads(zlib.decompress(raw))
            if kind=='observation':state.data[('observations',d['market_key']+':'+d['venue'])]=d
            elif kind=='fixture_status':
                old=state.get(kind,d['fixture_key'],{});state.data[(kind,d['fixture_key'])]=dict(d,started=old.get('started',False) or d['phase'] in ('in_play','finished'))
            elif kind=='venue_reset':
                for (owner,key),v in state.data.items():
                    if owner=='observations' and v['venue']==d['venue']:v.update(active=False,available_at=at,observed_at=at)
            elif kind=='unmapped_book':
                m=mapping.get(d['market_ticker'])
                if m:
                    fee=m['fees']['kalshi'];state.data[('observations',m['market_key']+':kalshi')]=dict(d,market_key=m['market_key'],venue='kalshi',active=d['valid'],available_at=at,
                        mapping_reference=m['mapping_reference'],fee_reference=fee['reference'],taker_rate=fee['rate'],fee_model=fee.get('fee_model','venue_cash_v2'),
                        balance_precision=fee.get('balance_precision','.0001'),size_unit='payout_dollars')
            elif kind=='external_raw':
                fixtures=fixture_index(d['payload'])
                for m in newpin:
                    row,_=normalize(m,fixtures,at,f'event:{seq}',bookmaker='pinnacle+30',snapshot=d,freshness_policy=manifest['config'].get('pinnacle_freshness_policy'))
                    state.data[('observations',m['market_key']+':pinnacle')]=row
        while ix<len(tasks):evaluate(tasks[ix]);ix+=1
        db.close();print(name,len(tasks),'pair checks',flush=True)
    assert len(records)==len({(r['quote_key'],r['trade_id']) for r in records})
    (OUT/'inventory_fill_checks.json').write_text(json.dumps(records)+'\n')
    (OUT/'inventory_fill_check_summary.json').write_text(json.dumps(dict(counts),indent=2)+'\n')
    print(json.dumps(dict(counts),indent=2))

if __name__=='__main__':run()

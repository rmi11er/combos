"""Causal snapshot audit on distinct matched-print quotes and every blocked RFQ.

No order/capture/config mutations. Variants are same-decision source ablations,
not portfolio paths. Raw capture state is reconstructed as in the frozen replay.
"""
import json
import sqlite3
import zlib
import math
from collections import Counter, defaultdict
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import numpy as np
from combos.pricing_service import PricingService
from combos.weighted_fair import WeightPolicy
from combos.pinnacle_feed import fixture_index, normalize
from offsession_quote_diagnostics import dist

ROOT=Path(__file__).resolve().parents[1]
D=ROOT/'runs/shadow_exchange_fallback_20260909'
OUT=ROOT/'runs/offsession_review_20260910'
CUTOFF=1788999600

class State:
    def __init__(self,base=None,allowed=None):
        self.data={} if base is None else base.data
        self.allowed=allowed
    def get(self,owner,key,default=None):
        if owner=='observations' and self.allowed is not None and key.rsplit(':',1)[-1] not in self.allowed:return default
        return self.data.get((owner,key),default)

def unpack(raw):return json.loads(zlib.decompress(raw))

def brief(p,state):
    point=p['joint']['point'];legs=[]
    for l in p['legs']:
        raw={}
        for v in ('kalshi','polymarket'):
            if v not in l['venues']:continue
            row=state.get('observations',l['mapping']['market_key']+':'+v)
            b,a=float(row['yes_bid']),float(row['yes_ask'])
            bs,az=float(row['yes_bid_size']),float(row['yes_ask_size'])
            mid=(a+b)/2;micro=(a*bs+b*az)/(bs+az)
            raw[v]={'mid':mid if l['selected_side']=='yes' else 1-mid,
                'micro':micro if l['selected_side']=='yes' else 1-micro,
                'spread_cents':100*(a-b),'depth':min(bs,az),
                'age':l['venues'][v]['age_seconds'],'weight':l['venues'][v]['weight']}
        legs.append({'fixture':l['mapping']['fixture_key'],'raw':raw,
            'sources':sorted(l['venues']),'lean':l['consensus_lean']})
    return {'point':point,'allowed':p['quote_allowed'],'reason':p.get('block_reason'),
        'tail_cents':100*(p['stressed_upper']-point),
        'marginal_envelope_cents':100*(p['joint']['upper']-point),
        'dependence_component_cents':100*(p['stressed_upper']-p['joint']['upper']),
        'risk_multiplier':p['risk_multiplier'],'legs':legs}

def run():
    OUT.mkdir(exist_ok=True)
    qs={q['quote_key']:q for q in map(json.loads,(D/'quotes.jsonl').open())}
    targets=json.loads((OUT/'matched_targets.json').read_text())
    selected={r['quote_key'] for r in targets}
    rows=[];blocked=Counter();blocked_creators=Counter();original_blocked=Counter();recovery=Counter()
    for run in sorted({q['run'] for q in qs.values()}):
        db=sqlite3.connect((ROOT/'runs'/run/'events.sqlite').as_uri()+'?mode=ro',uri=True)
        manifest=json.loads(db.execute("SELECT value FROM state WHERE owner='runtime' AND key='manifest'").fetchone()[0])
        config=json.loads((ROOT/'config/runtime_nfl_authorized_shadow_20260910.json').read_text())
        config['combo_terms']=manifest['config']['combo_terms']
        weights=WeightPolicy(**json.loads((ROOT/'config/weighting.json').read_text()))
        state=State();pricers={'baseline':PricingService(state,config,weights),
            'no_lean':PricingService(state,config,replace(weights,consensus_lean_enabled=False))}
        for name,vs in [('K',{'kalshi'}),('K_PM',{'kalshi','polymarket'}),('K_PIN',{'kalshi','pinnacle'})]:
            pricers[name]=PricingService(State(state,vs),config,weights)
        maps=pricers['baseline'].registry.by_ticker
        original={m['market_key'] for m in manifest['config']['mappings']}
        newpin=[m for m in config['mappings'] if m['market_key'] not in original and m.get('pinnacle') and not m.get('pricing_block_reason')]
        wanted={q['source_seq']:q for k,q in qs.items() if k in selected and q['run']==run}
        scanned=0
        for seq,raw in db.execute("SELECT d.source_seq,e.payload FROM decisions d JOIN events e ON e.seq=json_extract(d.result,'$.decision_event_seq') ORDER BY d.source_seq"):
            o=unpack(raw);scanned+=1
            if o['decision_completed_at']<=CUTOFF and not o.get('creator_policy_eligible',True):
                wanted[seq]={'request':o['request'],'decision_at':o['decision_at'],'blocked':True,
                    'original_reason':o.get('reason'),'creator_id':o['creator_id']}
            if scanned%250000==0:print(run,'scanned',scanned,flush=True)
        events=iter(db.execute("SELECT seq,kind,received_at,payload FROM events WHERE kind IN ('observation','fixture_status','venue_reset','unmapped_book','external_raw') ORDER BY seq"))
        event=next(events,None)
        for i,(seq,q) in enumerate(sorted(wanted.items())):
            while event is not None and event[0]<seq:
                es,kind,at,raw=event;d=unpack(raw)
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
                        state.data[('observations',m['market_key']+':kalshi')]=dict(d,market_key=m['market_key'],venue='kalshi',active=d['valid'],available_at=at,
                            mapping_reference=m['mapping_reference'],fee_reference=fee['reference'],taker_rate=fee['rate'],
                            fee_model=fee.get('fee_model','venue_cash_v2'),balance_precision=fee.get('balance_precision','.0001'),size_unit='payout_dollars')
                elif kind=='external_raw':
                    try:
                        fixtures=fixture_index(d['payload'])
                        for m in newpin:
                            row,_=normalize(m,fixtures,at,f'event:{es}',bookmaker='pinnacle+30',snapshot=d,
                                freshness_policy=manifest['config'].get('pinnacle_freshness_policy'))
                            state.data[('observations',m['market_key']+':pinnacle')]=row
                    except (ValueError,KeyError,TypeError):recovery['raw_pinnacle_errors']+=1
                event=next(events,None)
            result={'quote_key':f'{run}:{seq}','blocked':q.get('blocked',False),'variants':{}}
            names=['baseline'] if result['blocked'] else list(pricers)
            for name in names:
                try:
                    p=pricers[name].price(q['request']['mve_selected_legs'],q['decision_at'])
                    result['variants'][name]=brief(p,state)
                except (ValueError,KeyError,TypeError) as e:result['variants'][name]={'error':str(e)}
            base=result['variants']['baseline']
            if result['blocked']:
                reason=base['error'] if 'error' in base else base.get('reason') or ('priceable' if base['allowed'] else 'pricing_guard')
                blocked[reason.split(':')[0]]+=1;blocked_creators[q['creator_id']]+=1
                original_blocked[str(q.get('original_reason'))]+=1
            else:
                assert 'point' in base and base['allowed'],result
                assert abs(base['point']-q['pricing']['joint']['point'])<1e-10,result['quote_key']
                assert abs(base['tail_cents']-100*(q['pricing']['stressed_upper']-q['pricing']['joint']['point']))<1e-7
            rows.append(result)
            if i%1000==0:print(run,'priced',i,'of',len(wanted),flush=True)
        db.close()
    (OUT/'source_rows.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
    chosen={r['quote_key']:r for r in rows if not r['blocked']}
    comparison={}
    for name in ('K','K_PM','K_PIN','no_lean'):
        paired=[];allowed=0;changed=0;all_sources=0
        for t in targets:
            r=chosen[t['quote_key']]['variants'];v=r[name];base=r['baseline']
            if 'point' not in v:continue
            paired.append(100*(v['point']-base['point']));allowed+=v['allowed'];changed+=v['allowed']!=base['allowed']
            required={'K':{'kalshi'},'K_PM':{'kalshi','polymarket'},'K_PIN':{'kalshi','pinnacle'},'no_lean':{'kalshi','polymarket','pinnacle'}}[name]
            all_sources+=all(required<=set(l['sources']) for l in v['legs'])
        comparison[name]={'paired_fair_delta_cents':dist(paired),'allowed':allowed,'eligibility_changes':changed,'complete_requested_sources_every_leg':all_sources}
    features=[]
    for t in targets:
        q=qs[t['quote_key']];base=chosen[t['quote_key']]['variants']['baseline'];legs=base['legs']
        if not all('kalshi' in l['raw'] for l in legs):continue
        books=[l['raw']['kalshi'] for l in legs];mid=math.prod(b['mid'] for b in books)
        micro=math.prod(b['micro'] for b in books)
        public=q['yes_ask']+t['public_minus_ask_cents']/100
        features.append({'quote_key':t['quote_key'],'trade_id':t['trade_id'],'nlegs':len(legs),'point':mid,
            'public_edge_k_mid_cents':100*(public-mid),'micro_minus_mid_cents':100*(micro-mid),
            'mean_raw_spread_cents':sum(b['spread_cents'] for b in books)/len(books),
            'minimum_depth':min(b['depth'] for b in books),'max_age':max(b['age'] for b in books),
            'tail_cents':base['tail_cents'],'marginal_envelope_cents':base['marginal_envelope_cents'],
            'dependence_component_cents':base['dependence_component_cents']})
    correlations={}
    y=np.array([f['public_edge_k_mid_cents'] for f in features])
    controls=np.array([[1,f['point'],f['point']**2,f['nlegs']] for f in features])
    yr=y-controls@np.linalg.lstsq(controls,y,rcond=None)[0]
    for key in ('mean_raw_spread_cents','minimum_depth','max_age','micro_minus_mid_cents'):
        x=np.array([math.log1p(f[key]) if key=='minimum_depth' else f[key] for f in features])
        xr=x-controls@np.linalg.lstsq(controls,x,rcond=None)[0]
        correlations[key]={'raw':float(np.corrcoef(x,y)[0,1]),'residual_after_point_point_squared_legcount':float(np.corrcoef(xr,yr)[0,1])} if np.std(x)>1e-10 else {'constant':True}
    summary={'matched_prints':len(targets),'distinct_repriced_quotes':len(chosen),'blocked_total':sum(blocked.values()),
        'blocked_counterfactual_pricing':dict(blocked),'blocked_creators':len(blocked_creators),
        'blocked_original_reasons':dict(original_blocked),'source_comparisons':comparison,'recovery':dict(recovery),
        'liquidity_cohort':len(features),'liquidity_correlations':correlations,
        'tail_decomposition':{k:dist([f[k] for f in features]) for k in ('tail_cents','marginal_envelope_cents','dependence_component_cents')},
        'lean_applied_quotes':sum(any(l['lean']['applied'] for l in r['variants']['baseline']['legs']) for r in chosen.values()),
        'limitations':['Print-selected original eligible cohort, not full RFQ population; repeated fixture dependencies, no inference or significance.',
            'Variants retain fallback, so K_PM may contain K only; exact requested-source counts reported separately.',
            'Blocked counterfactual reprices independently without creator gate, not admission, fills or avoided PNL.',
            'Price-edge versus own component mid is contemporaneous; correlation is not predictive alpha.',
            'Microprice here is a simple top-book imbalance proxy, not a fitted efficient-price model.']}
    assert sum(blocked.values())==6259
    (OUT/'source_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    (OUT/'liquidity_features.json').write_text(json.dumps(features)+'\n')
    print(json.dumps(summary,indent=2))

if __name__=='__main__':run()

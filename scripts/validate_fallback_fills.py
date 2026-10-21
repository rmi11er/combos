"""Revalue tape matches using causal source state at fill and markout times."""
import json,sqlite3,zlib
from pathlib import Path
from collections import defaultdict,Counter
from copy import deepcopy
from combos.pricing_service import PricingService
from combos.weighted_fair import WeightPolicy
from combos.pinnacle_feed import fixture_index,normalize
ROOT=Path(__file__).resolve().parents[1];D=ROOT/'runs/shadow_exchange_fallback_20260909'
qs={q['quote_key']:q for q in map(json.loads,(D/'quotes.jsonl').open())}
fills=json.loads((D/'potential_fills.json').read_text());targets=defaultdict(list)
for i,f in enumerate(fills):
    for h in (0,5,30,120):
        if f['at']+h<=1788999600:targets[qs[f['quote_key']]['run']].append((f['at']+h,i,h))
class State:
    def __init__(self):self.data={}
    def get(self,owner,key,default=None):return self.data.get((owner,key),default)
results=[]
for run,tasks in targets.items():
    tasks.sort();index=0;state=State();config=json.loads((ROOT/'config/runtime_nfl_authorized_shadow_20260910.json').read_text())
    weights=WeightPolicy(**json.loads((ROOT/'config/weighting.json').read_text()));pricer=PricingService(state,config,weights)
    c=sqlite3.connect(f'file:{ROOT}/runs/{run}/events.sqlite?mode=ro',uri=True)
    manifest=json.loads(c.execute("SELECT value FROM state WHERE owner='runtime' AND key='manifest'").fetchone()[0]);original={m['market_key'] for m in manifest['config']['mappings']}
    newpin=[m for m in config['mappings'] if m['market_key'] not in original and m.get('pinnacle') and not m.get('pricing_block_reason')]
    def evaluate(target):
        at,i,h=target;f=fills[i];q=qs[f['quote_key']];row=dict(allocation=i,quote_key=q['quote_key'],horizon=h,at=at)
        try:
            p=pricer.price(q['request']['mve_selected_legs'],at);point=p['joint']['point'];fee=q['economics']['maker_fee']/q['quantity']
            edge=q['yes_ask']-point-fee;reasons=[]
            if not p['quote_allowed']:reasons.append('pricing_guard')
            if h==0:
                if edge+1e-12<q['required_net_edge_per_share']:reasons.append('edge_below_hurdle')
                if abs(point-q['pricing']['joint']['point'])>.01+1e-12:reasons.append('fair_move_exceeded')
                if p['risk_multiplier']<q['pricing']['risk_multiplier']:reasons.append('risk_regime_tightened')
            row.update(available=True,passed=not reasons,reasons=reasons,point=point,edge_cents=100*edge,model_value_dollars=f['quantity']*edge)
        except (ValueError,KeyError,TypeError) as e:row.update(available=False,passed=False,reasons=[str(e)])
        results.append(row)
    clock=0
    for seq,kind,at,raw in c.execute("SELECT seq,kind,received_at,payload FROM events WHERE kind IN ('observation','fixture_status','venue_reset','unmapped_book','external_raw','heartbeat') ORDER BY seq"):
        clock=max(clock,at)
        while index<len(tasks) and tasks[index][0]<clock:evaluate(tasks[index]);index+=1
        if index==len(tasks):break
        if kind=='heartbeat':continue
        d=json.loads(zlib.decompress(raw))
        if kind=='observation':state.data[('observations',d['market_key']+':'+d['venue'])]=d
        elif kind=='fixture_status':
            old=state.get(kind,d['fixture_key'],{});state.data[(kind,d['fixture_key'])]=dict(d,started=old.get('started',False) or d['phase'] in ('in_play','finished'))
        elif kind=='venue_reset':
            for (owner,key),v in state.data.items():
                if owner=='observations' and v['venue']==d['venue']:v.update(active=False,available_at=at,observed_at=at)
        elif kind=='unmapped_book':
            m=pricer.registry.by_ticker.get(d['market_ticker'])
            if m:
                fee=m['fees']['kalshi'];row=dict(d,market_key=m['market_key'],venue='kalshi',active=d['valid'],available_at=at,
                    mapping_reference=m['mapping_reference'],fee_reference=fee['reference'],taker_rate=fee['rate'],fee_model=fee.get('fee_model','venue_cash_v2'),
                    balance_precision=fee.get('balance_precision','.0001'),size_unit='payout_dollars')
                state.data[('observations',m['market_key']+':kalshi')]=row
        elif kind=='external_raw':
            fixtures=fixture_index(d['payload'])
            for m in newpin:
                row,_=normalize(m,fixtures,at,f'event:{seq}',bookmaker='pinnacle+30',snapshot=d,freshness_policy=manifest['config'].get('pinnacle_freshness_policy'))
                state.data[('observations',m['market_key']+':pinnacle')]=row
    while index<len(tasks):evaluate(tasks[index]);index+=1
    c.close();print(run,'validated',len(tasks),'snapshots',flush=True)
(D/'fill_and_model_mark_validation.json').write_text(json.dumps(results,indent=2)+'\n')
passed={r['allocation'] for r in results if r['horizon']==0 and r['passed']}
valid=[dict(f,allocation=i) for i,f in enumerate(fills) if i in passed]
(D/'validated_potential_fills.json').write_text(json.dumps(valid,indent=2)+'\n')
print(json.dumps(dict(total_allocations=len(fills),passed=len(passed),failures=dict(Counter(reason for r in results if r['horizon']==0 and not r['passed'] for reason in r['reasons']))),indent=2))

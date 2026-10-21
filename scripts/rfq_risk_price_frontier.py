"""Full-RFQ price needed to fit baseline remaining risk; fixed-state diagnostic."""
import argparse
from collections import Counter
from decimal import Decimal, ROUND_CEILING
import json
from pathlib import Path
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from combos.research_capacity import CapacityReplay
from combos.fees import kalshi_fill_fee
D=Decimal


def price_terms(price, contracts, target, rate):
    q=D(str(contracts)) if contracts is not None else (D(str(target))/price).quantize(D('.01'),rounding=ROUND_CEILING)
    fee=kalshi_fill_fee(q,1-price,rate,'buy','.0001')['net_fee']
    hold=(q*(1-price)+q*rate*price*(1-price)+q*D('.01')).quantize(D('.0001'),rounding=ROUND_CEILING)
    return q,fee,int(hold*10000)


def frontier(prices, original, room, contracts, target, rate, reference, edge):
    lo=0;hi=len(prices)
    while lo<hi:
        mid=(lo+hi)//2
        if price_terms(prices[mid],contracts,target,rate)[2]<=room:hi=mid
        else:lo=mid+1
    # Risk cost is monotone; rounded per-contract edge need not be.
    for price in prices[lo:]:
        q,fee,hold=price_terms(price,contracts,target,rate)
        if q*(price-reference)-fee>=q*edge:
            assert hold<=room
            return {'ask':str(price),'quantity_bound':str(q),'hold_units':hold,
                    'additional_cents':float(100*(price-original))}
    return None


def run(a):
    policy=json.loads(a.policy.read_text());runtime=json.loads(a.runtime.read_text())
    if policy['capacity_mode']!='all_admitted_fill_no_release':raise ValueError('fixed held-capacity baseline required')
    risk=CapacityReplay(policy['capital_dollars'],policy['caps']);rows=[];checked=0
    db=sqlite3.connect(a.decisions.resolve().as_uri()+'?mode=ro&immutable=1',uri=True)
    for seq,raw in db.execute('SELECT source_seq,result FROM candidate_decisions ORDER BY source_seq'):
        decision=json.loads(raw);p=decision['pricing'];r=p.get('research_policy',{})
        if 'admission' not in r:continue
        quote=r['quote'];buckets={k:r['buckets'][k] for k in ('contract','combo','fixture')};mult=D(str(r['pricing_risk_multiplier']))
        if not r.get('pricing_risk_multiplier_applied',True):mult=D(1)
        used=sum(v['cost'] for v in risk.active.values());room=risk.capital-used
        for kind,keys in buckets.items():
            cap=int(D(risk.caps[kind])*mult)
            for key in set(keys):room=min(room,cap-sum(v['cost'] for v in risk.active.values() if key in v['buckets'][kind]))
        room=max(0,room)
        actual=risk.admit(p['rfq_id'],decision['evaluation_at'],quote['fragmentation_cash_bound'],buckets,float(mult))
        assert actual==r['admission'],seq
        checked+=1
        if actual['admitted']:continue
        original=D(quote['yes_ask']);terms=next(v for k,v in sorted(runtime['combo_terms'].items(),key=lambda kv:-len(kv[0])) if p['market_ticker'].startswith(k))
        prices=set()
        for grid in terms['price_ranges']:
            value=D(str(grid['start']));end=D(str(grid['end']));step=D(str(grid['step']))
            while value<end:
                if original<=value<1:prices.add(value)
                value+=step
        rate=D(str(terms['maker_fee_rate']))
        q,fee,hold=price_terms(original,p['requested_contracts'],p['target_cost_dollars'],rate)
        assert q==D(quote['quantity_bound']) and fee==D(quote['single_fill_fee']) and hold==int(D(quote['fragmentation_cash_bound'])*10000)
        alternative=frontier(sorted(prices),original,room,p['requested_contracts'],p['target_cost_dollars'],rate,D(quote['quote_reference']),D(str(policy['edge_per_combo'])))
        rows.append({'source_seq':seq,'room_units':room,'binding_limits':actual['binding_limits'],
            'sizing_basis':quote['sizing_basis'],'alternative':alternative})
    db.close()
    feasible=[r['alternative']['additional_cents'] for r in rows if r['alternative']]
    summary={'baseline_admissions_reproduced':checked,'risk_rejected':len(rows),
        'positive_room':sum(r['room_units']>0 for r in rows),'feasible_at_some_price':len(feasible),
        'within_additional_cents':{str(x):sum(v<=x+1e-9 for v in feasible) for x in (.1,.3,1,2,5,10)},
        'binding_counts':dict(Counter(k for r in rows for k in r['binding_limits'])),
        'limitations':['Each alternative uses its original baseline portfolio state; capacities cannot be summed.',
            'Full requested size retained, with conservative target-cost and fragmented-fee bounds.',
            'No acceptance model or alternative portfolio path; feasible does not mean competitive.']}
    a.out.mkdir(parents=True,exist_ok=False);(a.out/'rows.json').write_text(json.dumps(rows,indent=2));(a.out/'summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('decisions','policy','runtime','out'):p.add_argument('--'+k,type=Path,required=True)
    run(p.parse_args())

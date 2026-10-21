"""Read-only fixed-cohort charge, sizing and concentration diagnostics; not fills."""
import json
import math
import sqlite3
import hashlib
from collections import Counter
from decimal import Decimal, ROUND_CEILING
from pathlib import Path
from combos.shadow_engine import quote_price

ROOT = Path(__file__).resolve().parents[1]
D = ROOT / 'runs/shadow_exchange_fallback_20260909'
OUT = ROOT / 'runs/offsession_review_20260910'

def dist(xs):
    xs = sorted(xs)
    return {'n': len(xs), **{k: xs[round((len(xs)-1)*p)] for k,p in
            [('p05',.05),('median',.5),('p95',.95),('p99',.99)]}} if xs else {'n':0}

def run():
    OUT.mkdir(exist_ok=True)
    quotes = {q['quote_key']:q for q in map(json.loads,(D/'quotes.jsonl').open())}
    fills = json.loads((D/'joint_risk_fills.json').read_text())
    comparisons = json.loads((D/'active_price_comparisons.json').read_text())
    terms = {}
    for name in {q['run'] for q in quotes.values()}:
        db = sqlite3.connect((ROOT/'runs'/name/'events.sqlite').as_uri()+'?mode=ro',uri=True)
        terms[name] = json.loads(db.execute("SELECT value FROM state WHERE owner='runtime' AND key='manifest'").fetchone()[0])['config']['combo_terms']
        db.close()
    latest = {}
    for p in comparisons:
        if p['side'] != 'yes':continue
        old=latest.get(p['trade_id'])
        if old is None or quotes[p['quote_key']]['decision_completed_at']>quotes[old['quote_key']]['decision_completed_at']:
            latest[p['trade_id']]=p
    assert len(latest)==2262
    clipped=set();size_counts=Counter();requested={};prices={};latencies=[];tail=[]
    for key,q in quotes.items():
        ts=next(v for k,v in terms[q['run']].items() if q['market_ticker'].startswith(k))
        ps={str(c):quote_price(q['pricing']['joint']['point'],c/100,ts['maker_fee_rate'],ts['price_ranges']) for c in (.2,.3,.35)}
        assert math.isclose(ps['0.3'],q['yes_ask'],abs_tol=1e-10)
        prices[key]=ps
        fixed=q['request'].get('contracts_fp')
        basis='fixed_contracts' if fixed and float(fixed)>0 else 'target_cost'
        req=float(fixed) if basis=='fixed_contracts' else float((Decimal(str(q['request']['target_cost_dollars']))/Decimal(str(q['yes_ask']))).to_integral_value(rounding=ROUND_CEILING))
        requested[key]=req
        size_counts[basis]+=1
        if q['quantity']+1e-8<req:
            clipped.add(key);size_counts[basis+'_clipped']+=1
        latencies.append(1000*(q['decision_completed_at']-q['received_at']))
        tail.append(100*(q['pricing']['stressed_upper']-q['pricing']['joint']['point']))
    charge={}
    for c in (.2,.3,.35):
        bins=Counter();gaps=[]
        for p in latest.values():
            gap=p['public_minus_ask_cents']+100*(quotes[p['quote_key']]['yes_ask']-prices[p['quote_key']][str(c)])
            gaps.append(gap)
            bins['below' if gap>1e-8 else 'same' if abs(gap)<=1e-8 else 'above']+=1
        charge[str(c)]={'counts':dict(bins),'at_or_below_fraction':(bins['below']+bins['same'])/len(latest),
            'mean_print_minus_ask_cents':sum(gaps)/len(gaps),
            'changed_quotes':sum(not math.isclose(prices[k][str(c)],q['yes_ask'],abs_tol=1e-10) for k,q in quotes.items())}
    clipped_fills=[f for f in fills if f['quote_key'] in clipped]
    out={'cohort_quotes':len(quotes),'distinct_yes_prints':len(latest),'size_counts':dict(size_counts),
         'clipped_quotes':len(clipped),'funded_clipped_quotes':len({f['quote_key'] for f in clipped_fills}),
         'funded_clipped_collateral':sum(f['liability_dollars'] for f in clipped_fills),
         'funded_clipped_contracts':sum(f['quantity'] for f in clipped_fills),
         'funded_clipped_model_edge':sum(f['point_edge_dollars'] for f in clipped_fills),
         'charge_comparison':charge,'receive_to_decision_complete_ms':dist(latencies),
         'admitted_tail_score_cents':dist(tail),
         'limitations':['Fixed original candidates, clock, fair and one latest quote per print; NOT portfolio replay or acceptance forecast.',
            'Charge variants do not recompute source/fill-time eligibility, size, capacity, cancellations or new quote admission.',
            'Clipping compared against existing shadow requested-size formula, not exchange-derived target-cost contracts.',
            'Original replay baseline minimum is 0.30 cents, not exactly 0.35 cents; 0.342 cents is matched realized tick charge.']}
    (OUT/'quote_diagnostics.json').write_text(json.dumps(out,indent=2)+'\n')
    (OUT/'matched_targets.json').write_text(json.dumps(list(latest.values()))+'\n')
    (OUT/'quote_diagnostic_hashes.json').write_text(json.dumps({str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),D/'quotes.jsonl',D/'active_price_comparisons.json',D/'joint_risk_fills.json']},indent=2)+'\n')
    print(json.dumps(out,indent=2))

if __name__=='__main__':run()

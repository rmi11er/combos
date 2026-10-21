"""Audit and aggregate the corrected session for the post-session review."""
import json,math,hashlib
from collections import defaultdict,Counter
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from corrected_shadow_review import fillstats
ROOT=Path(__file__).resolve().parents[1];D=ROOT/'runs/shadow_exchange_fallback_20260909'
OUT=D/'post_session';OUT.mkdir(exist_ok=True)
def read(name):return json.loads((D/name).read_text())
summary=read('summary.json');performance=read('performance.json');risk=read('joint_risk_summary.json')
funded=read('funded_performance.json');fills=read('joint_risk_fills.json')
qs={q['quote_key']:q for q in map(json.loads,(D/'quotes.jsonl').open())}
comparisons=read('active_price_comparisons.json')
assert len(qs)==performance['quotes']==summary['counts']['quotes']
assert math.isclose(sum(f['quantity'] for f in fills),risk['contracts'],abs_tol=1e-8)
assert math.isclose(sum(f['liability_dollars'] for f in fills),risk['collateral_dollars'],abs_tol=1e-8)
assert math.isclose(risk['ending_used']['total'],risk['collateral_dollars'],abs_tol=1e-8)
c=summary['counts']
assert sum(v for k,v in c.items() if k not in ('requests','priceable'))==c['requests']
validation=read('fill_and_model_mark_validation.json')
passed={r['allocation'] for r in validation if r['horizon']==0 and r['passed']}
assert all(f['allocation'] in passed for f in fills)
trade_qty={t['trade_id']:float(t['count_fp']) for t in map(json.loads,(D/'quoted_market_trades.jsonl').open())}
used=Counter()
for f in fills:used[f['trade_id']]+=f['quantity']
assert all(qty<=trade_qty[k]+1e-8 for k,qty in used.items())
for f in fills:
    q=qs[f['quote_key']]
    assert q['decision_completed_at']<=f['at']<q['valid_until']
    assert f['public_yes_price']+1e-9>=f['hypothetical_yes_price']
assert risk['peak_used']['total']<=10000+1e-8
assert all(v<=1000+1e-8 for k,v in risk['peak_used'].items() if k.startswith('fixture:'))
assert all(v<=500+1e-8 for k,v in risk['peak_used'].items() if k.startswith(('contract:','combo:')))

# Latest eligible quote per public print; no repeated-quote inflation.
latest={}
for p in comparisons:
    previous=latest.get(p['trade_id'])
    if previous is None or qs[p['quote_key']]['decision_completed_at']>qs[previous['quote_key']]['decision_completed_at']:
        latest[p['trade_id']]=p
yes=[p for p in latest.values() if p['side']=='yes']
bins=Counter()
for p in yes:
    gap=p['public_minus_ask_cents']
    bins['Our ask below print' if gap>1e-8 else 'Same price' if abs(gap)<=1e-8 else 'Our ask above print']+=1

cohorts={}
for dimension,fn in [('legs',lambda q:str(q['leg_count'])),
    ('minimum_sources_per_leg',lambda q:str(min(len(s.split(',')) for s in q['pricing']['source_sets']))),
    ('family',lambda q:'moneyline-only' if all(l['market_ticker'].startswith('KXNFLGAME-') for l in q['request']['mve_selected_legs']) else 'other / mixed')]:
    groups=defaultdict(list)
    for f in fills:groups[fn(qs[f['quote_key']])].append(f)
    cohorts[dimension]={k:fillstats(v) for k,v in groups.items()}

timeline=[];collateral=ev=0.;fixture=defaultdict(float);first90={}
for f in sorted(fills,key=lambda f:f['at']):
    collateral+=f['liability_dollars'];ev+=f['point_edge_dollars']
    for k in set(qs[f['quote_key']]['pricing']['fixtures']):
        fixture[k]+=f['liability_dollars']
        if fixture[k]>=900 and k not in first90:first90[k]=datetime.fromtimestamp(f['at'],ZoneInfo('America/Chicago')).isoformat()
    timeline.append(dict(at=f['at'],collateral=collateral,model_ev=ev))
marketrows=sorted(funded['markets'],key=lambda m:m['collateral_dollars'],reverse=True)
marks={}
for h,row in funded['public_marks'].items():
    marks[h]={**row,'cents_per_contract':100*row['markout_dollars']/row['contracts'],
              'contract_coverage_fraction':row['contracts']/risk['contracts']}
summary_out=dict(audit='passed: counts, deduplication, validity windows, tape size, fill checks, base gross caps',
    scenario='fixed-cohort counterfactual; not actual fills and not a lower bound on live participation',
    requests=c['requests'],priceable=c['priceable'],initial_candidate_quotes=len(qs),joint_risk_responses=risk['counts']['quote_intents_admitted'],
    funded=fillstats(fills),latency_scenarios=performance['scenarios'],
    distinct_active_trades=len(latest),distinct_active_yes_trades=len(yes),latest_quote_price_comparison=dict(bins),
    distinct_active_yes_mean_gap_cents=sum(p['public_minus_ask_cents'] for p in yes)/len(yes),
    cohorts=cohorts,public_marks=marks,model_marks=funded['model_marks'],
    top_market_collateral_share=marketrows[0]['collateral_dollars']/risk['collateral_dollars'],
    top_three_market_collateral_share=sum(m['collateral_dollars'] for m in marketrows[:3])/risk['collateral_dollars'],
    top_three_market_model_ev_share=sum(m['model_edge_dollars'] for m in marketrows[:3])/risk['model_edge_dollars'],
    first_fixture_90pct_times=first90,peak_total_reserved=risk['peak_used']['total'],
    net_charge_cents=100*risk['model_edge_dollars']/risk['contracts'],
    market_edge_cents=100*risk['public_price_edge_at_quote_fair_dollars']/risk['contracts'],
    model_ev_loss_from_point_one_cent_bias=risk['contracts']*.001,
    maker_fees_on_funded_contracts=sum(f['quantity']*qs[f['quote_key']]['economics']['maker_fee']/qs[f['quote_key']]['quantity'] for f in fills))
(OUT/'analysis.json').write_text(json.dumps(summary_out,indent=2)+'\n')
(OUT/'collateral_timeline.json').write_text(json.dumps(timeline,indent=2)+'\n')
files=['summary.json','performance.json','joint_risk_summary.json','joint_risk_fills.json','funded_performance.json','active_price_comparisons.json']
(OUT/'source_hashes.json').write_text(json.dumps({f:hashlib.sha256((D/f).read_bytes()).hexdigest() for f in files},indent=2)+'\n')
print(json.dumps(summary_out,indent=2))

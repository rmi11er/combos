"""Candidate-dependent spend sizing for retained distinct-game RFQs: dry run."""
import argparse
from bisect import bisect_left
from collections import Counter
from dataclasses import replace
from decimal import Decimal
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from combos.demand_experiment import ARMS
from combos.quote_policy import QuoteRequest,FairSignal,Reserve,MakerFeeTerms,validate,candidate_ledger
from combos.research_spend_risk import target_size


def main():
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True)
    p.add_argument('--hurdles-cents',nargs='+',type=Decimal,help='Optional net hurdles in cents; defaults to original flat arms')
    a=p.parse_args()
    arms=ARMS if a.hurdles_cents is None else {f'flat_{v.normalize()}c':float(v/100) for v in a.hurdles_cents}
    if any(not v.is_finite() or v<0 for v in (a.hurdles_cents or [])):
        p.error('hurdles must be finite and nonnegative')
    source=ROOT/'runs/nfl_both_demand_scenarios_20260909/decisions.json'
    runtime_path=ROOT/'runs/nfl_both_demand_full_capture_20260909/runtime.json'
    runtime=json.loads(runtime_path.read_text());rows=[];counts=Counter()
    for r in json.loads(source.read_text()):
        if r['status']!='scenario_priced' or r.get('target_cost_dollars') is None:continue
        scenario=next(s for s in r['scenarios'] if s['assumed_usd_per_native_unit']==1)
        terms=next(v for k,v in sorted(runtime['combo_terms'].items(),key=lambda kv:-len(kv[0])) if r['market_ticker'].startswith(k))
        fair=scenario['independent_combo_point'];upper=scenario['independent_marginal_upper'];at=r['at']
        for arm,edge in arms.items():
            request=QuoteRequest(decision_id=r['rfq_id']+':'+arm,decision_at=at,quantity=1,
                fair=FairSignal(fair,at,str(source)),reserves=tuple(Reserve(k,upper-fair if k=='uncertainty' else 0,
                    at,'captured_upper' if k=='uncertainty' else 'uncalibrated_research_zero')
                    for k in ['uncertainty','dependence','adverse_selection','inventory']),
                fees=MakerFeeTerms(terms['maker_fee_rate'],terms['verified_at'],terms['fee_reference'],'.0001',terms['valid_until']),
                price_ranges=tuple(terms['price_ranges']),minimum_profit_per_contract=edge,
                policy_reference='spend_demand_dry_run_v1',policy_available_at=at)
            prices=validate(request)
            lower=Decimal(str(fair))+Decimal(str(upper-fair))+Decimal(str(edge))
            for rate in ['0','.07']:
                result={'rfq_id':r['rfq_id'],'arm':arm,'requested_budget':r['target_cost_dollars'],
                        'requester_taker_rate_scenario':rate,'excludes_fees_scenario':False,
                        'experiment_stage':'retrospective_dry_run','orders_enabled':False}
                for ask in prices[bisect_left(prices,lower):]:
                    sized=target_size(r['target_cost_dollars'],ask,rate)
                    if sized['quantity']==0:continue
                    candidate=candidate_ledger(replace(request,quantity=sized['quantity']),ask,ask,Decimal(0))
                    if candidate['eligible']:
                        result.update(status='candidate',sizing=sized,ledger=candidate);break
                else:result['status']='no_feasible_candidate'
                rows.append(result);counts[result['status']]+=1
    a.out.mkdir(parents=True,exist_ok=True)
    (a.out/'candidates.json').write_text(json.dumps(rows,indent=2,default=str)+'\n')
    summary={'distinct_rfqs':len({r['rfq_id'] for r in rows}),'counts':dict(counts),'arms_dollars':arms,
        'limitations':['Requester fee rates 0/.07 and .0001 precision are scenarios, not verified account terms.',
          'Assumes fees included, single full fill and no existing rounding accumulator; requires exchange-count reconciliation.',
          'Fair, sampled grids and zero non-uncertainty reserves remain prior dry-run assumptions.',
          'No same-game pricing or creator/portfolio risk eligibility is provided; no live exposure or assignment.']}
    (a.out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))


if __name__=='__main__':main()

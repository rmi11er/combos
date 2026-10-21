"""Prepare a fixed-size NFL RFQ demand dry run, or score real exposure records."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from combos.demand_experiment import ARMS, VERSION, assign, price_band, score, score_markouts
from combos.quote_policy import FairSignal, MakerFeeTerms, QuotePolicy, QuoteRequest, Reserve


def prepare(args):
    source=ROOT/'runs/nfl_both_demand_scenarios_20260909/decisions.json'
    runtime_path=ROOT/'runs/nfl_both_demand_full_capture_20260909/runtime.json'
    terms_path=ROOT/'runs/nfl_both_demand_terms_20260909/decisions.json'
    source_rows=json.loads(source.read_text());runtime=json.loads(runtime_path.read_text())
    creator_checks={r['rfq_id']:r for r in json.loads(terms_path.read_text()) if r['reserve_fraction']==0}
    counts=Counter(); assignments=[];seen=set()
    for r in source_rows:
        counts['observed_rfqs']+=1
        if r['status']!='scenario_priced':continue
        counts['scenario_priced']+=1
        if r['rfq_id'] in seen:raise ValueError('duplicate_rfq')
        seen.add(r['rfq_id'])
        if r.get('requested_contracts') is None:
            counts['target_cost_requires_verified_candidate_sizing']+=1;continue
        check=creator_checks.get(r['rfq_id'],{})
        if check.get('status')!='priced' or check.get('creator_status') not in ['clear','watch']:
            counts['creator_or_terms_excluded']+=1;continue
        scenario=next(s for s in r['scenarios'] if s['assumed_usd_per_native_unit']==1)
        terms=next(v for k,v in sorted(runtime['combo_terms'].items(),key=lambda kv:-len(kv[0])) if r['market_ticker'].startswith(k))
        fair=scenario['independent_combo_point'];upper=scenario['independent_marginal_upper'];at=r['at']
        candidates={}
        for arm,edge in ARMS.items():
            req=QuoteRequest(decision_id=r['rfq_id']+':'+arm,decision_at=at,quantity=float(r['requested_contracts']),
                fair=FairSignal(fair,at,str(source)),
                reserves=tuple(Reserve(name,upper-fair if name=='uncertainty' else 0,at,
                    'captured_marginal_upper' if name=='uncertainty' else 'explicit_uncalibrated_dry_run_zero')
                    for name in ['uncertainty','dependence','adverse_selection','inventory']),
                fees=MakerFeeTerms(terms['maker_fee_rate'],terms['verified_at'],terms['fee_reference'],'.0001',terms['valid_until']),
                price_ranges=tuple(terms['price_ranges']),minimum_profit_per_contract=edge,
                policy_reference=VERSION,policy_available_at=at)
            output=QuotePolicy().evaluate(req)
            floor=output['floor']
            if floor is None:break
            candidates[arm]={'yes_ask':str(floor['yes_ask']),'quantity':r['requested_contracts'],
                             'ledger':floor,'net_hurdle_dollars_per_contract':edge}
        if len(candidates)!=len(ARMS):counts['not_all_arms_feasible']+=1;continue
        same=len({c['yes_ask'] for c in candidates.values()})<len(ARMS)
        if same:counts['grid_collapsed_arms']+=1;continue
        a=assign(r['rfq_id'],args.seed)
        a.update(decision_at=at,price_band=price_band(fair),fair=fair,nlegs=r['nlegs'],
                 market_ticker=r['market_ticker'],candidates=candidates,
                 fee_rate=terms['maker_fee_rate'],grid_basis=terms['grid_validation'],
                 experiment_stage='retrospective_dry_run',customer_exposed=False)
        assignments.append(a)
    counts['assignable_fixed_size_rfqs']=len(assignments)
    summary=score(assignments,[])
    summary.update(counts=dict(counts),orders_enabled=False,experiment=VERSION,seed=args.seed,
       input_hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [source,runtime_path,terms_path]},
       limitations=['Retrospective captured scenarios, not prospective randomized exposure.',
                    'Source conversion and independence remain captured research assumptions.',
                    'Only fixed quantity; sampled grids and .0001 balance precision require account/market verification.',
                    'Uncertainty held constant across arms; other reserves explicit uncalibrated zero for dry-run only.',
                    'Candidate-dependent risk must be checked by the execution system; no runtime integration here.'])
    args.out.mkdir(parents=True,exist_ok=True)
    (args.out/'assignments.json').write_text(json.dumps(assignments,indent=2,default=str)+'\n')
    (args.out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps({'counts':dict(counts),'observed_exposures':0,'out':str(args.out)},indent=2))


def main():
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest='command',required=True)
    q=sub.add_parser('prepare');q.add_argument('--seed',default='nfl-flat-arms-20260909-v1');q.add_argument('--out',type=Path,required=True)
    q=sub.add_parser('score');q.add_argument('--assignments',type=Path,required=True);q.add_argument('--responses',type=Path,required=True);q.add_argument('--out',type=Path,required=True)
    q.add_argument('--fills',type=Path,help='Verified live fills with optional as-of horizon marks')
    a=p.parse_args()
    if a.command=='prepare':prepare(a)
    else:
        assignments=json.loads(a.assignments.read_text());responses=json.loads(a.responses.read_text())
        result=score(assignments,responses)
        if a.fills:
            result['markouts']=score_markouts(assignments,result,json.loads(a.fills.read_text()))
        a.out.parent.mkdir(parents=True,exist_ok=True)
        a.out.write_text(json.dumps(result,indent=2)+'\n');print('scored',len(responses),'response records')


if __name__=='__main__':main()

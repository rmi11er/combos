"""Label-availability audit and quote-mechanics screen, not a demand backtest."""
import argparse
from decimal import Decimal
import hashlib
import json
from pathlib import Path

import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
DEFINITIONS={'focus_5_10_20_50':{Decimal(x) for x in [5,10,20,50]},
             'broader_common_amounts':{Decimal(x) for x in [1,2,5,10,20,25,50,100]}}


def compare(baseline,candidates):
    assert len(baseline)==len(candidates) and baseline
    base_margin=sum(r['ledger']['margin_after_reserves_and_fee'] for r in baseline)
    new_margin=sum(r['ledger']['margin_after_reserves_and_fee'] for r in candidates)
    return {'rfqs':len(baseline),
        'identical_quotes':sum(a['ledger']['quote']==b['ledger']['quote'] for a,b in zip(baseline,candidates)),
        'mean_ask_change_cents':sum(100*(b['ledger']['yes_ask']-a['ledger']['yes_ask']) for a,b in zip(baseline,candidates))/len(baseline),
        'baseline_contracts_if_all_filled':sum(r['ledger']['quantity'] for r in baseline),
        'candidate_contracts_if_all_filled':sum(r['ledger']['quantity'] for r in candidates),
        'baseline_reserved_model_margin_if_all_filled':base_margin,
        'candidate_reserved_model_margin_if_all_filled':new_margin,
        'uniform_acceptance_multiplier_to_match_reserved_margin':base_margin/new_margin if new_margin>0 else None}


def main():
    p=argparse.ArgumentParser();p.add_argument('--folder',type=Path,required=True);a=p.parse_args()
    path=a.folder/'candidates.json';rows=json.loads(path.read_text())
    assert all(r['status']=='candidate' and not r['orders_enabled'] for r in rows)
    indexed={(r['rfq_id'],r['requester_taker_rate_scenario'],r['arm']):r for r in rows}
    assert len(indexed)==len(rows)
    ids=sorted({r['rfq_id'] for r in rows});results=[];grid=[]
    for rate in ['0','.07']:
        get=lambda i,arm:indexed[i,rate,'flat_'+arm+'c']
        for definition,amounts in DEFINITIONS.items():
            round_ids=[i for i in ids if Decimal(get(i,'0.3')['requested_budget']) in amounts]
            other_ids=[i for i in ids if i not in set(round_ids)]
            grid.append({'fee_scenario':rate,'definition':definition,
                         'round_rfqs':len(round_ids),'other_spend_rfqs':len(other_ids),
                         'identical_015_vs_02':sum(get(i,'0.15')['ledger']['quote']==get(i,'0.2')['ledger']['quote'] for i in round_ids)})
            for low in ['0.15','0.2']:
                for high in ['0.3','0.4']:
                    r={'fee_scenario':rate,'definition':definition,'round_hurdle_cents':low,'other_hurdle_cents':high}
                    for group,selected,arm in [('round',round_ids,low),('other_spend',other_ids,high)]:
                        r[group]=compare([get(i,'0.3') for i in selected],[get(i,arm) for i in selected]) if selected else None
                    results.append(r)
    hist_path=ROOT/'runs/combo_mid_spread_association_20260909/observations.csv.gz'
    hist=pd.read_csv(hist_path)
    report={'historical_label_audit':{'prints_by_sport':hist.sport.value_counts().to_dict(),
            'columns':hist.columns.tolist(),'requested_spend_field_present':'target_cost_dollars' in hist.columns,
            'rfq_join_key_present':'rfq_id' in hist.columns,
            'honest_round_spend_backtest_status':'not_identified'},
        'definitions':{k:sorted(map(str,v)) for k,v in DEFINITIONS.items()},'grid_collisions':grid,'comparisons':results,
        'input_sha256':{str(p):hashlib.file_digest(p.open('rb'),'sha256').hexdigest() for p in [path,hist_path]},
        'limitations':['Retrospective unexposed candidates, not fills or executable recommended quotes.',
            'Reserved model margin is after explicit research reserves and fees, not observed PnL.',
            'Break-even ratios assume a uniform acceptance probability within each group, unchanged conditional fair and the modeled candidate quantity; actual acceptance is unknown.',
            'Do not infer original target spend from price times public print quantity; partial fills, fees and fixed-size orders confound it.',
            'Other spend is not synonymous with non-round or informed flow. Fixed-size/unknown requests need their own policy.',
            'No same-game inference: candidate sample retains the prior priceable distinct-game scope.']}
    (a.folder/'comparison.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'grid_collisions':grid,'primary':results[:4]},indent=2))


if __name__=='__main__':main()

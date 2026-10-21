"""Reprice fixed-size hypothetical quotes rather than keep observed premiums.

Acceptance proxy: hypothetical ask <= historical executed YES premium. It does
not establish available RFQs, queue priority or counterfactual customer demand.
"""
import argparse
import gzip
import json
from pathlib import Path
from research_inventory_relief import replay


def run(out):
    rows=sorted([json.loads(l) for l in gzip.open(out/'nfl_panel.jsonl.gz','rt')],key=lambda r:(r['at'],r['evaluation_id']))
    results=[]
    for period,subset in [('full',rows),('later',[r for r in rows if r['at']>=1768197600])]:
        baseline=None
        for arm,trigger in [('net',.9),('relief',.8),('relief',.9),('flat01',.9)]:
            s,fills=replay(subset,arm,trigger,.001,1000,250,True,True)
            s['period']=period
            if arm=='net':baseline=s['pnl']
            s['pnl_vs_flat03']=s['pnl']-baseline
            s['gross_price_concession_vs_observed']=sum(f['quantity']*(f['observed_price']-f['charged_price']) for f in fills)
            results.append(s)
            with gzip.open(out/f'repriced_{period}_{arm}_{trigger}.json.gz','wt') as f:json.dump(fills,f,allow_nan=False)
            print(period,arm,trigger,s['fills'],s['discount_fills'],s['pnl'],flush=True)
    (out/'inventory_repricing.json').write_text(json.dumps({'results':results,'limitations':[
        'Fixed-size quote at fair plus hurdle plus modeled .035 maker fee, rounded up to a 0.1c price grid.',
        'Hypothetical fill only if quoted ask does not exceed observed executed premium. Not observed RFQ acceptance or available order flow.',
        'Lower price and fee change cash, portfolio risk, markouts and settlement PnL; eligibility recalculated chronologically.',
        'Original print quantities retained; no target-spend resizing or partial-fill inference.',
        'Discount certified at its own quoted price, not at the more favorable historical print price.',
        'Conditional observed-trade scenario only; no new unseen demand inferred.']},indent=2)+'\n')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);run(p.parse_args().out)

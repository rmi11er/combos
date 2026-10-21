"""Balanced markout curves and historical leg-hedge transaction-cost sensitivity."""
import argparse
from datetime import datetime
import gzip
import json
from pathlib import Path
from zoneinfo import ZoneInfo
import numpy as np


def deltas(points):
    return np.array([np.prod(points[:j]+points[j+1:]) for j in range(len(points))])


def summarize(values,quantities):
    return {'prints':len(values),'mean_cents':float(np.mean(values)),
        'contract_weighted_cents':float(np.average(values,weights=quantities)),
        'positive_fraction':float(np.mean(np.array(values)>0)),
        'p10_cents':float(np.quantile(values,.1)),'p90_cents':float(np.quantile(values,.9))}


def run(out):
    rows=[json.loads(l) for l in gzip.open(out/'nfl_panel.jsonl.gz','rt')]
    results=[];hedges=[]
    for period in ['train','test']:
        group=[r for r in rows if (datetime.fromtimestamp(r['at'],ZoneInfo('America/Chicago')).date().isoformat()<'2026-01-12')==(period=='train')]
        eligible=[r for r in group if r['yes_price']-r['fair_point']-r['maker_fee']/r['quantity']>=.003 and r['entry_max_age_seconds']<=180]
        balanced=[r for r in eligible if all(m['status']=='observed' and m['max_age_seconds']<=180 for m in r['marks'].values())]
        for horizon in ['60','300','900','3600','close']:
            if balanced:
                results.append({'period':period,'horizon':horizon,'cohort':'all_horizons_fresh180',
                    **summarize([r['marks'][horizon]['seller_net_markout_cents'] for r in balanced],[r['quantity'] for r in balanced]),
                    'entry_edge_cents':float(np.mean([100*(r['yes_price']-r['fair_point']-r['maker_fee']/r['quantity']) for r in balanced]))})
        for rate in [0,.035,.07]:
            netedge=[];after_entry=[];static=[];q=[]
            for r in eligible:
                mids=r['leg_mids'];delta=deltas(mids);ask=np.array(r['leg_asks'])
                edge=r['yes_price']-r['fair_point']-r['maker_fee']/r['quantity']
                friction=float(np.dot(delta,ask-np.array(mids)+rate*ask*(1-ask)))
                netedge.append(100*edge);after_entry.append(100*(edge-friction));q.append(r['quantity'])
                # Buying a full unit of any selected leg superhedges one unit of
                # the binary conjunction. Not equal to replicating its fair value.
                static.append(100*(r['yes_price']-r['maker_fee']/r['quantity']-min(ask+rate*ask*(1-ask))))
            hedges.append({'period':period,'leg_fee_coefficient':rate,'mode':'entry_delta_friction',**summarize(after_entry,q),
                'unhedged_entry_mean_cents':float(np.mean(netedge)),'single_leg_superhedge_positive_prints':int(sum(x>0 for x in static)),
                'single_leg_superhedge_mean_cents':float(np.mean(static))})
            for horizon in ['60','300','900','3600','close']:
                values=[];weights=[];unhedged=[]
                for r in balanced:
                    m=r['marks'][horizon];delta=deltas(r['leg_mids']);a=np.array(r['leg_asks']);b=np.array(m['selected_bids'])
                    hedge_pnl=float(np.dot(delta,b-a-rate*(a*(1-a)+b*(1-b))))
                    values.append(m['seller_net_markout_cents']+100*hedge_pnl);weights.append(r['quantity'])
                    unhedged.append(m['seller_net_markout_cents'])
                hedges.append({'period':period,'leg_fee_coefficient':rate,'horizon':horizon,'mode':'delta_roundtrip_mark',
                    **summarize(values,weights),'unhedged_mean_cents':float(np.mean(unhedged))})
    result={'balanced_markouts':results,'hedge_sensitivities':hedges,'limitations':[
        'Balanced cohort requires all future marks fresh: retrospective censoring sensitivity, not a deployable entry filter.',
        'Delta hedge is continuous theoretical size under independent fair, not exact combo replication.',
        'Leg roundtrip buys at archived ask and sells at future bid with modeled quadratic fees, no depth, queue, slippage, or fee rounding.',
        'Combo remains marked to fair, not executable liquidation; these are hypothetical marked returns, not realized hedged PnL.',
        'Single-leg superhedge is sufficient in ordinary binary outcomes only; it is not a claim of globally cheapest replication.',
        'Leg fee coefficients are historical scenarios; raw candle prices and 60s availability lag retained.']}
    (out/'hedge_followup.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);run(p.parse_args().out)

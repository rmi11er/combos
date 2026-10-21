#!/usr/bin/env python3
"""Plot all observed CFB seller exposure, with explicit missing-outcome bounds."""
import argparse
import csv
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
from zoneinfo import ZoneInfo

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True, type=Path)
    args = parser.parse_args(); root = args.run
    meta = json.loads((root/'summary.json').read_text())
    start, end = meta['start_at'], meta['end_at']; n = int((end-start)/1800)
    changes = {key: np.zeros(n+1) for key in ['known', 'unknown_low', 'unknown_high', 'premium', 'payout', '2', '3', '4', '5+']}
    daily = np.zeros(7)
    with gzip.open(root/'per_trade.csv.gz', 'rt') as f:
        for r in csv.DictReader(f):
            at = float(r['at']); idx = min(n, int((at-start)//1800)+1)
            q, p, fee = (float(r[k]) for k in ('quantity','yes_price','maker_fee'))
            changes['premium'][idx] += q*p; changes['payout'][idx] += q
            if r['net_pnl'] != '':
                pnl = float(r['net_pnl']); changes['known'][idx] += pnl
                key = str(min(5, int(r['nlegs']))); key = '5+' if key == '5' else key
                changes[key][idx] += pnl
                daily[min(6, int((at-start)//86400))] += pnl
            else:
                changes['unknown_low'][idx] += q*(p-1)-fee
                changes['unknown_high'][idx] += q*p-fee
    totals = {key: np.cumsum(a) for key,a in changes.items()}
    assert abs(totals['known'][-1] - meta['aggregate']['known_net_pnl']) < .01
    x = [datetime.fromtimestamp(start+i*1800, timezone.utc) for i in range(n+1)]
    returns = daily/10000; var = float(np.var(returns, ddof=1)); sharpe = float(np.mean(returns)/np.sqrt(var)*np.sqrt(365)) if var else None
    plt.style.use('dark_background'); plt.rcParams['text.parse_math'] = False
    fig, axes = plt.subplots(3, 1, figsize=(14, 11), sharex=True, gridspec_kw={'height_ratios':[2,1,1]})
    equity = 10000 + totals['known']
    axes[0].fill_between(x, (equity+totals['unknown_low'])/1e6, (equity+totals['unknown_high'])/1e6,
                         step='post', color='#a6a6a6', alpha=.22, label='Unresolved payout extremes; not a confidence interval')
    label = (f'Known P&L ${totals["known"][-1]:,.0f}; descriptive Sharpe {sharpe:.2f}; daily Var {var*1e8:.3g} bp²'
             if sharpe is not None else f'Known P&L ${totals["known"][-1]:,.0f}; Sharpe undefined')
    axes[0].step(x, equity/1e6, where='post', color='#84c9be', label=label)
    axes[0].set_ylabel('$10k base + attributed P&L ($m)')
    colors = ['#73a0c4','#e7b078','#84c9be','#b497d6']
    for key, color in zip(['2','3','4','5+'], colors):
        axes[1].step(x, totals[key]/1e6, where='post', color=color, label=f'{key} legs: ${totals[key][-1]:,.0f}')
    axes[1].set_ylabel('Known P&L by leg count ($m)')
    axes[2].step(x, totals['premium']/1e6, where='post', color='#73a0c4', label=f'YES premium ${totals["premium"][-1]:,.0f}')
    axes[2].step(x, totals['payout']/1e6, where='post', color='#e7b078', label=f'Payout notional ${totals["payout"][-1]:,.0f}')
    axes[2].set_ylabel('Observed volume ($m)')
    for ax in axes:
        ax.grid(alpha=.2); ax.legend(loc='best', fontsize=8)
        ax.set_xlim(x[0], x[-1])
    tz = ZoneInfo(meta['timezone'])
    axes[-1].xaxis.set_major_locator(mdates.AutoDateLocator(tz=tz))
    axes[-1].xaxis.set_major_formatter(mdates.DateFormatter('%b %d\n%H:%M', tz=tz))
    axes[-1].set_xlabel(meta['timezone'])
    fig.suptitle(f'Entire available CFB universe: hypothetical sellers of every YES-taker print\n{meta["benchmark_prints"]:,} prints; all leg counts and game phases; unlimited exposure', fontsize=12)
    agg = meta['aggregate']
    lo = totals['known'][-1]+totals['unknown_low'][-1]; hi = totals['known'][-1]+totals['unknown_high'][-1]
    fig.text(.07, .025, f'{int(agg["unresolved_prints"]):,} unresolved prints: total P&L could range from ${lo:,.0f} to ${hi:,.0f}; bounds need not be jointly attainable.\n'
             'Outcomes attributed to entry, displayed at half-hour right edges. No fair-value/edge filter, hedges, or RFQ acceptance model. Not actual industry P&L.\n'
             'Saturday census; other days are all retained sampled intervals. Known-outcome Sharpe/variance are provisional; $10k is a reporting base, not funding.', fontsize=8)
    fig.tight_layout(rect=(0,.10,1,.94))
    for ext in ('png','svg'): fig.savefig(root/('market_equity.'+ext), dpi=160, bbox_inches='tight')
    plt.close(fig)
    provenance = {'input_sha256': {name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in ['summary.json','per_trade.csv.gz']},
                  'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  'known_outcome_sharpe':sharpe,'daily_return_variance_bp2':var*1e8,
                  'total_pnl_loose_bounds':[lo,hi]}
    (root/'plot_manifest.json').write_text(json.dumps(provenance,indent=2)+'\n')


if __name__ == '__main__': main()

#!/usr/bin/env python3
"""Standalone performance figures for the opposite-moneyline experiment."""
import argparse
from collections import defaultdict
from datetime import datetime
import gzip
import json
from pathlib import Path
from zoneinfo import ZoneInfo


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run', type=Path, required=True)
    args = p.parse_args()
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FuncFormatter
    import matplotlib.dates as mdates
    manifest = json.loads((args.run/'manifest.json').read_text())
    summaries = json.loads((args.run/'summary.json').read_text())
    curves = defaultdict(list)
    with gzip.open(args.run/'curves.jsonl.gz', 'rt') as f:
        for line in f:
            r = json.loads(line)
            if r['cohort'] in ('paired', 'pm_complete'):
                curves[(r['cohort'], r['model'], r['constrained'], r['variant'])].append(r)
    labels = {'sell_all': 'Sell every guard-eligible print', 'point_0.3c': 'Point fair + 0.3c',
              'native_width': 'Point + native half-width + 0.3c',
              'opposite_width': 'Point + opposite half-width + 0.3c',
              'existing_stressed': 'Existing stressed floor + 0.3c',
              'opposite_plus_PM_gap': 'Opposite half-width + PM point gap + 0.3c',
              'stressed_with_pair_floor': 'Stressed + opposite floor + 0.3c'}
    colors = dict(zip(labels, ('#777777', '#0072B2', '#009E73', '#D55E00', '#CC79A7', '#8B6508', '#222222')))
    tz = ZoneInfo('America/Chicago')
    money = FuncFormatter(lambda v, _: f'${v/1e6:.1f}m' if abs(v) >= 1e6 else f'${v/1000:.1f}k' if abs(v) >= 20000 else f'${v:,.0f}')
    for cohort, model in sorted({(key[0], key[1]) for key in curves}):
        fig, axes = plt.subplots(3, 2, figsize=(16, 12), sharex='col')
        for col, constrained in enumerate((True, False)):
            records = [r for r in summaries if (r['cohort'], r['model'], r['constrained']) == (cohort, model, constrained)]
            for r in records:
                variant = r['variant']; points = curves[(cohort, model, constrained, variant)]
                # Settlement after the trading window may release cash, but the
                # requested retrospective equity / edge is already at trade time.
                points = [x for x in points if x['at'] <= manifest['source_window'][1]]
                times = [datetime.fromtimestamp(x['at'], tz) for x in points]
                label = f"{labels[variant]} · n={r['summary']['fills']:,} · P&L ${r['selected']['known_net_pnl']:,.0f}"
                axes[0, col].step(times, [(10000 if constrained else 0)+x['trade_attributed_pnl'] for x in points], where='post', label=label, color=colors[variant], lw=1.4)
                axes[1, col].step(times, [x['accepted_point_edge'] for x in points], where='post', color=colors[variant], lw=1.4)
                axes[2, col].step(times, [x['committed_cash'] for x in points], where='post', color=colors[variant], lw=1.4)
            axes[0, col].set_title('$10k funded; $100 underlying/combo; $250 fixture' if constrained else 'Unlimited funding and concentration')
            axes[0, col].legend(fontsize=7, loc='best', title='Daily Sharpe / variance: N/A (insufficient complete dates)', title_fontsize=8)
            for row, label in enumerate(('Retrospective equity ($)' if constrained else 'Cumulative known net P&L ($)', 'Cumulative point-model edge, after fees ($)', 'Simultaneous committed cash ($)')):
                axes[row, col].set_ylabel(label)
                axes[row, col].yaxis.set_major_formatter(money)
                axes[row, col].grid(alpha=.2)
                axes[row, col].axhline(10000 if row == 0 and constrained else 0, color='#999999', lw=.5)
            axes[2, col].xaxis.set_major_formatter(mdates.DateFormatter('%m-%d\n%H:%M', tz=tz))
            axes[2, col].xaxis.set_major_locator(mdates.AutoDateLocator(minticks=4, maxticks=8))
            axes[2, col].set_xlabel('Trade time · America/Chicago')
            if manifest['sport'] == 'mlb':
                axes[2, col].set_xlim(datetime(2026, 9, 5, tzinfo=tz), datetime(2026, 9, 6, tzinfo=tz))
        fig.suptitle(f"{manifest['sport'].upper()} · {model} · {cohort.replace('_', ' ')} moneyline comparison", fontsize=15)
        fig.text(.06, .025, 'Same covered prints within each model; models may have different source coverage. All curves use observed print prices, not invented RFQ fills.\n'
                 'Known settlement outcomes attributed to trade time; spendable cash releases at settlement. Unknown outcomes excluded from P&L (bounds in summary).\n'
                 'Width-only policies omit correlation reserves; existing stressed is a separate benchmark. No depth estimates. CFB other weekdays have incomplete tape.', fontsize=9)
        fig.tight_layout(rect=(0, .09, 1, .96))
        for ext in ('png', 'svg'):
            fig.savefig(args.run/f'{cohort}_{model}.{ext}', dpi=145)
        plt.close(fig)


if __name__ == '__main__':
    main()

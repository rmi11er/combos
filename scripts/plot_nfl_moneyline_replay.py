#!/usr/bin/env python3
"""Plot existing NFL replay ledgers without rerunning or changing trade decisions."""
import argparse
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

NAMES = {'kalshi': 'Kalshi', 'polymarket': 'Polymarket',
         'exchange_blend_equal': 'Equal blend', 'exchange_blend_pm75': 'PM 75%'}
COLORS = {'kalshi': '#73a0c4', 'polymarket': '#84c9be',
          'exchange_blend_equal': '#e7b078', 'exchange_blend_pm75': '#b497d6',
          'all': '#cccccc'}


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1048576), b''):
            h.update(chunk)
    return h.hexdigest()


def render(root, out, fee='0.035'):
    if out.exists():
        raise ValueError('use_a_new_plot_directory')
    out.mkdir(parents=True)
    summary_path = root / 'summary.json'
    summary = json.loads(summary_path.read_text())
    sources = {str(summary_path): digest(summary_path)}
    plt.style.use('dark_background')
    plt.rcParams['text.parse_math'] = False
    for regime in ('funded', 'unlimited'):
        results = []
        for policy in ('selection', 'sell_all'):
            path = root / f'fee{fee}_{regime}_{policy}.json.gz'
            before = digest(path)
            with gzip.open(path, 'rt') as f:
                ledger = json.load(f)
            if digest(path) != before:
                raise ValueError('input_changed')
            sources[str(path)] = before
            if policy == 'selection':
                display_config = ledger['configuration']
            for s in ledger['summaries']:
                model = s['model']
                if policy == 'sell_all' and model != 'kalshi':
                    continue
                rows = [r for r in ledger['curves'] if r['model'] == model]
                if abs(rows[-1]['trade_attributed_pnl'] - s['trade_attributed_pnl']) > 1e-7:
                    raise ValueError('curve_summary_pnl_mismatch')
                results.append((policy, model, s, rows))
        fig, axes = plt.subplots(4, 1, figsize=(15, 15), sharex=True,
                                 gridspec_kw={'height_ratios': [2, 1, 1.3, 1]})
        limited = regime == 'funded'
        for policy, model, s, rows in results:
            all_prints = policy == 'sell_all'
            label = ('No price filter (risk-limited)' if limited else 'Sell every priced print') if all_prints else NAMES[model]
            color = COLORS['all' if all_prints else model]
            style = '--' if all_prints else '-'
            x = [datetime.fromtimestamp(r['at'], timezone.utc) for r in rows]
            var = s['daily_pnl_variance_dollars2']
            var_text = 'N/A' if var is None else f'{var:,.2f}'
            legend = (f'{label}: net P&L ${s["trade_attributed_pnl"]:,.2f}; '
                      f'{s["fills"]:,}/{s["evaluations"]:,} fills; daily variance {var_text} USD²; Sharpe N/A')
            key = 'trade_attributed_equity' if limited else 'trade_attributed_pnl'
            axes[0].step(x, [r[key] for r in rows], where='post', color=color,
                         linestyle=style, label=legend)
            axes[1].step(x, [r['accepted_point_edge'] for r in rows], where='post',
                         color=color, linestyle=style,
                         label=label + (' (Kalshi fair)' if all_prints else ''))
            for key, line, suffix in [('filled_yes_premium', '-', 'premium'),
                                      ('filled_payout_notional', ':', 'payout face')]:
                axes[2].step(x, [r[key] for r in rows], where='post', color=color,
                             linestyle=line, label=f'{label}: {suffix}')
            axes[3].step(x, [r['committed_cash'] for r in rows], where='post',
                         color=color, linestyle=style,
                         label=f'{label}: peak ${s["peak_committed_cash"]:,.2f}')
        axes[0].set_ylabel('Trade-attributed equity (USD)' if limited else 'Trade-attributed net P&L (USD)')
        axes[1].set_ylabel('Cumulative point edge (USD)')
        axes[2].set_ylabel('Simulated volume (USD)')
        axes[3].set_ylabel('Committed cash (USD)')
        for i, ax in enumerate(axes):
            ax.grid(alpha=.2)
            ax.ticklabel_format(axis='y', style='plain', useOffset=False)
            ax.legend(loc='best', fontsize=8, ncol=1 if i in (0, 1) else 2)
            ax.set_xlim(datetime.fromtimestamp(summary['start_at'], timezone.utc),
                        datetime.fromtimestamp(summary['end_at'], timezone.utc))
        axes[-1].xaxis.set_major_locator(mdates.DayLocator(tz=ZoneInfo('America/Chicago')))
        axes[-1].xaxis.set_major_formatter(mdates.DateFormatter('%b %d', tz=ZoneInfo('America/Chicago')))
        axes[-1].set_xlabel('Trade date — Chicago time')
        dates = summary['completed_dates']
        cfg = display_config
        scope = (f'${cfg["capital_dollars"]:,.0f} capital; ${cfg["per_contract_dollars"]:g} underlying / '
                 f'${cfg["per_combo_dollars"]:g} combo / ${cfg["per_fixture_dollars"]:g} fixture'
                 if limited else 'Unlimited exposure; no fixed-capital financing claim')
        unit = cfg.get('minimum_net_edge_unit', 'combo_contract').replace('_', ' ')
        hurdle = cfg['minimum_net_edge_per_share'] * 100
        fig.suptitle(f'NFL moneyline combos | {dates[0]} through {dates[-1]}\n{scope}\n'
                     f'2–4 distinct fixtures; pregame; same priced cohort; selections require {hurdle:g}¢ net per {unit}', fontsize=12)
        fig.text(.06, .025,
                 f'Eventual outcome P&L attributed at trade time; cash released only at actual settlement. Maker coefficient {fee} is an unverified fee scenario.\n'
                 f'Pinnacle absent. Public-print participation is hypothetical. Sell-all is a separate portfolio under the displayed funding regime.\n'
                 f'Sharpe withheld: {len(dates)} observed dates share few fixtures. Daily P&L variance is descriptive (USD², ddof=1). Payout face is not customer winnings.', fontsize=8)
        fig.tight_layout(rect=(0, .09, 1, .94))
        for ext in ('png', 'svg'):
            fig.savefig(out / f'{regime}.{ext}', dpi=150, bbox_inches='tight')
        plt.close(fig)
    if any(digest(Path(p)) != h for p, h in sources.items()):
        raise ValueError('source_changed_during_plotting')
    manifest = {'sources': sources, 'script_sha256': digest(Path(__file__)),
                'fee_coefficient': fee, 'completed_dates': summary['completed_dates'],
                'decisions_changed': False, 'sharpe_display': 'withheld_short_shared_fixture_sample',
                'outputs': {p.name: digest(p) for p in out.iterdir() if p.suffix in ('.png', '.svg')}}
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--fee', default='0.035')
    a = p.parse_args()
    render(a.run, a.out, a.fee)

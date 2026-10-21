"""Plot frozen selected/rejected economics with explicit exposure conventions."""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter, FuncFormatter
import numpy as np


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path,
                        default=Path('runs/cfb_selection_research_20260907/forensics'))
    args = parser.parse_args()
    summaries = json.loads((args.directory/'summary.json').read_text())['summaries']
    matching = json.loads((args.directory/'matched_strata.json').read_text())
    matched = next(row for row in matching
                   if row['scope'] == 'all' and row['strata'] == 'nlegs+price_band+premium_band')
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.4))
    colors = {'selected': '#3274a1', 'rejected': '#e1812c'}
    width = .34
    for j, group in enumerate(('selected', 'rejected')):
        x = np.arange(2)+(j-.5)*width
        values = [summaries[f'{scope}:{group}']['known_net_pnl']
                  for scope in ('all', 'premium_le_50')]
        bars = axes[0].bar(x, values, width, color=colors[group], label=group.capitalize())
        axes[0].bar_label(bars, labels=[f'{v:+,.0f}' for v in values], padding=4, fontsize=10)
        returns = [summaries[f'all:{group}']['mean_per_print_NO_cash_return'],
                   matched['pooled_cell_weighted_mean_NO_cash_return'][group]]
        bars = axes[1].bar(x, returns, width, color=colors[group])
        axes[1].bar_label(bars, labels=[f'{v:.1%}' for v in returns], padding=4, fontsize=10)
    axes[0].set_xticks([0, 1], ['All observed sizes', 'YES premium ≤ $50'])
    axes[0].set_title('Observed-size seller P&L, after maker fees')
    axes[0].set_ylabel('Known-outcome P&L (USD)')
    axes[0].yaxis.set_major_formatter(FuncFormatter(lambda v, _: f'{v/1000:.0f}k'))
    axes[0].set_ylim(-62000, 105000)
    axes[0].legend(frameon=False, loc='upper left')
    axes[1].set_xticks([0, 1], ['Equal print weight', 'Matched exposure bands'])
    axes[1].set_title('Mean return on NO cash: all observed sizes')
    axes[1].set_ylabel('Net P&L / NO principal plus fee, per print')
    axes[1].yaxis.set_major_formatter(PercentFormatter(1))
    axes[1].set_ylim(-.40, .055)
    for ax in axes:
        ax.axhline(0, color='#777777', linewidth=.8)
        ax.grid(axis='y', alpha=.18)
        ax.set_axisbelow(True)
        ax.spines[['top', 'right']].set_visible(False)
    fig.suptitle('CFB blend selection audit · August 31–September 6, 2026', fontsize=15)
    fig.text(.05, .055,
             'Unlimited public-print benchmark; unresolved outcomes excluded. No inferred RFQ wins.\n'
             'Matched bands: leg count, YES price and premium; common overlap 1,596 selected / 5,994 rejected. '
             'Descriptive, not causal.', fontsize=9)
    fig.tight_layout(rect=(0, .13, 1, .94))
    for extension in ('png', 'svg'):
        fig.savefig(args.directory/f'selection_comparison.{extension}', dpi=170)
    plt.close(fig)
    print(args.directory/'selection_comparison.png')


if __name__ == '__main__':
    main()

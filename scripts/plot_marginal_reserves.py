"""Plot audited marginal-reserve portfolios with funded and unlimited panels."""
import argparse
from datetime import datetime
import json
from pathlib import Path
from zoneinfo import ZoneInfo
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
matplotlib.rcParams['text.parse_math'] = False
from mlb_disk_index import file_digest
from replay_artifact_io import text_reader


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--study', type=Path, required=True)
    p.add_argument('--audit', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    study = json.loads((a.study / 'summary.json').read_text())
    audit = json.loads(a.audit.read_text())
    assert audit['passed'] and audit['all_24_complete']
    assert audit['summary_snapshot_sha256'] == file_digest(a.study/'summary.json')
    key = lambda r: (r['model'], r['variant'], r['regime'])
    assert len(audit['checks']) == len(study['records']) == 24
    assert {key(r) for r in audit['checks']} == {key(r) for r in study['records']}
    a.out.mkdir(parents=True, exist_ok=False)
    variants = ['marginal_0_0', 'marginal_0_25', 'marginal_1_0']
    fractions = [0, .25, 1]
    regimes = ['funded', 'unlimited']
    names = dict(kalshi='Kalshi', polymarket='Polymarket', exchange_blend_equal='Equal blend', exchange_blend_pm75='PM75')
    colors = dict(zip(names, ['#2878b5', '#d97706', '#27855e', '#9063b5']))
    fields = [('trade_attributed_equity', 'Retrospective equity ($)'), ('point_edge_equity', 'Initial capital + modeled edge ($)'), ('committed_cash', 'Outstanding committed cash ($)')]
    figures = {field: plt.subplots(3, 2, figsize=(17, 13), sharex=True, sharey='col', squeeze=False) for field, _ in fields}
    evidence = []
    for r in study['records']:
        if r['variant'] not in variants:
            continue
        path = a.study / f"{r['model']}__{r['variant']}__{r['regime']}.curves.jsonl.zst"
        digest = file_digest(path)
        points, previous = [], None
        with text_reader(path) as handle:
            for line in handle:
                row = json.loads(line)
                values = tuple(row[field] for field, _ in fields)
                if values != previous:
                    points.append((row['at'], *values))
                    previous = values
            end = (row['at'], *values)
        if points[-1] != end:
            points.append(end)
        assert digest == file_digest(path)
        assert abs(points[-1][1] - r['portfolio']['ending_trade_attributed_equity']) < .01
        assert abs(max(x[3] for x in points) - r['portfolio']['peak_committed_cash']) < .01
        x = [datetime.fromtimestamp(v[0], ZoneInfo('America/Chicago')) for v in points]
        variance = r['sampled_statistics']['observed_date_pnl_variance_dollars2']
        label = names[r['model']] + '; Sharpe N/A' + (f'; sampled P&L var={variance:,.0f} $²' if variance is not None else '; variance N/A')
        panel = (variants.index(r['variant']), regimes.index(r['regime']))
        for j, (field, _) in enumerate(fields, 1):
            figures[field][1][panel].step(x, [v[j] for v in points], where='post', color=colors[r['model']], label=label if j == 1 else names[r['model']])
        evidence.append({'path': str(path), 'sha256': digest, 'economic_change_points': len(points)})
        print('plotted', r['model'], r['variant'], r['regime'], flush=True)
    for field, ylabel in fields:
        fig, axes = figures[field]
        for i in range(3):
            for col, regime in enumerate(regimes):
                ax = axes[i, col]
                ax.set_title(f"Marginal reserve fraction {fractions[i]:g} | {regime}")
                ax.set_ylabel(ylabel)
                ax.axhline(10000, color='#777777', linewidth=.8, linestyle='--')
                ax.grid(alpha=.2)
                ax.legend(fontsize=8, loc='upper left')
                ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %d', tz=ZoneInfo('America/Chicago')))
        for ax in axes[-1]:
            ax.set_xlabel('July trade time (Chicago); 15 observed dates, July 13 identity gap')
        fig.suptitle('July development • hypothetical full-print sales • 0.3¢/combo • exchange-only fair', fontsize=13)
        fig.text(.5, .012, 'Funded: $10k initial cash and outstanding ceiling; $1k underlying/combo/event caps. Unlimited: hypothetical $10k reporting base, additional funding required.\nUnverified historical .035 maker-fee scenario. Sharpe N/A: nonconsecutive dates and shared games. Variance: sampled-date P&L, $².\nEventual P&L is attributed at trade time; only actual settlements fund new trades. Independence reserve is an uncalibrated pricing assumption.', ha='center', fontsize=9)
        fig.tight_layout(rect=(0, .065, 1, .96))
        fig.savefig(a.out / (field + '.png'), dpi=150)
        fig.savefig(a.out / (field + '.svg'))
        plt.close(fig)
    (a.out / 'verification.json').write_text(json.dumps({'passed': True, 'source_sha256': file_digest(Path(__file__)), 'summary_sha256': file_digest(a.study / 'summary.json'), 'audit_sha256': file_digest(a.audit), 'artifacts': evidence}, indent=2) + '\n')


if __name__ == '__main__':
    main()

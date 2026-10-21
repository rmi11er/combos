#!/usr/bin/env python3
"""Run paired portfolio experiments from immutable normalized model opportunities."""
import argparse
import csv
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from combos.backtest import BacktestConfig, run_backtest
from combos.selection_performance import selection_performance
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

COLORS = {'kalshi': '#73a0c4', 'pinnacle': '#e7b078', 'blend': '#84c9be', 'stronger_pinnacle': '#b497d6'}
NAMES = {'kalshi': 'Kalshi', 'pinnacle': 'Pinnacle', 'blend': 'Guarded blend', 'stronger_pinnacle': 'Stronger Pinnacle'}


def csv_write(path, rows):
    if not rows:
        path.write_text(''); return
    with path.open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)


def draw(result, data, output):
    config = result['configuration']; limited = result['constrained']
    plt.style.use('dark_background')
    plt.rcParams['text.parse_math'] = False
    fig, axes = plt.subplots(4, 1, figsize=(14, 13), sharex=True, gridspec_kw={'height_ratios': [2, 1, 1, 1]})
    base = config['capital_dollars']
    subtitle = (f'${base:,.0f} funded capital; ${config["per_contract_dollars"]:g}/underlying, '
                f'${config["per_combo_dollars"]:g}/combo, ${config["per_fixture_dollars"]:g}/fixture') if limited else (
                f'Unlimited capital and concentration; ${base:,.0f} reporting base')
    title = 'Stressed reservation price' if config['entry_basis'] == 'stressed_upper' else 'POINT-PRICE DIAGNOSTIC — reserves removed'
    if config.get('maximum_yes_premium_dollars') is not None:
        subtitle += f'; observed YES premium ≤ ${config["maximum_yes_premium_dollars"]:g}'
    count = len({r['evaluation_id'] for r in data['opportunities']})
    fig.suptitle(data['display_name'] + ' | ' + title + '\n' + subtitle +
                 f'\nEligible observed trades: {data.get("candidate_prints", count):,}; priced in this report: {count:,}; model fills / evaluations below', fontsize=11)
    for i, summary in enumerate(result['summaries']):
        model = summary['model']; rows = [r for r in result['curves'] if r['model'] == model]
        x = [datetime.fromtimestamp(r['at'], timezone.utc) for r in rows]
        color = COLORS.get(model); style = ('-', '--', ':', '-.')[i % 4]
        sharpe = summary['annualized_sharpe']; var = summary['daily_return_variance_bp2']
        label = (f'{NAMES.get(model, model)}: P&L ${summary["trade_attributed_pnl"]:,.2f}; '
                 f'descriptive Sharpe {sharpe:.2f}' if sharpe is not None else
                 f'{NAMES.get(model, model)}: P&L ${summary["trade_attributed_pnl"]:,.2f}; Sharpe N/A')
        var_label = f'{var:.3g}' if var is not None and var >= 1e6 else f'{var:,.2f}' if var is not None else 'N/A'
        label += f'; daily Var {var_label} bp²' if var is not None else '; daily Var N/A'
        label += f'; {summary["fills"]}/{summary["evaluations"]} fills'
        axes[0].step(x, [r['trade_attributed_equity'] for r in rows], where='post', color=color, linestyle=style, label=label)
        for key, line, suffix in (('accepted_point_edge', '-', 'point edge'), ('accepted_stressed_edge', ':', 'stressed edge')):
            axes[1].step(x, [r[key] for r in rows], where='post', color=color, linestyle=line,
                         label=NAMES.get(model, model) + ' ' + suffix)
        for key, line, suffix in (('filled_yes_premium', '-', 'YES premium'), ('filled_payout_notional', ':', 'payout notional')):
            axes[2].step(x, [r[key] for r in rows], where='post', color=color, linestyle=line,
                         label=NAMES.get(model, model) + ' ' + suffix)
        axes[3].step(x, [r['committed_cash'] for r in rows], where='post', color=color, linestyle=style,
                     label=f'{NAMES.get(model, model)}; peak ${summary["peak_committed_cash"]:,.2f}')
    axes[0].set_ylabel('Equity with P&L at trade time ($)')
    axes[0].ticklabel_format(axis='y', style='plain', useOffset=False)
    axes[1].set_ylabel('Cumulative net edge ($)')
    axes[2].set_ylabel('Simulated volume ($)')
    axes[3].set_ylabel('Committed capital ($)')
    for ax in axes:
        ax.grid(alpha=.22); ax.legend(loc='upper left', fontsize=8, ncol=1 if ax is axes[0] else 2)
        ax.set_xlim(datetime.fromtimestamp(data['start_at'], timezone.utc), datetime.fromtimestamp(data['end_at'], timezone.utc))
    if not any(s['fills'] for s in result['summaries']):
        reasons = {d['reason'] for d in result['decisions']}
        message = 'No observed prices cleared the edge threshold' if reasons == {'insufficient_edge'} else 'No simulated fills after entry, guard and risk checks'
        axes[0].text(.5, .36, message + '\nZero variance; Sharpe undefined',
                     transform=axes[0].transAxes, ha='center', fontsize=11)
    tz = ZoneInfo(config['timezone'])
    axes[-1].xaxis.set_major_locator(mdates.AutoDateLocator(tz=tz))
    axes[-1].xaxis.set_major_formatter(mdates.DateFormatter('%b %d\n%H:%M', tz=tz))
    axes[-1].set_xlabel(config['timezone'] + ' time')
    days = min((s['full_calendar_days'] for s in result['summaries']), default=0)
    active_days = max((s['active_pnl_days'] for s in result['summaries']), default=0)
    unresolved = max((s['unresolved_outcomes'] for s in result['summaries']), default=0)
    fig.text(.08, .025,
             f'{days} full calendar days; at most {active_days} with attributed P&L per model. Sharpe = mean daily P&L / SD × √{config["annualization_days"]}; '
             'variance uses daily P&L / reporting base.\n'
             'Retrospective outcomes attributed to trade time; cash releases at settlement. Hypothetical public-print fills. '
             f'Unresolved outcomes: up to {unresolved}/model.\n'
             + data.get('cohort_description', ''), fontsize=8)
    fig.tight_layout(rect=(0, .065, 1, .94))
    for extension in ('png', 'svg'):
        fig.savefig(output.with_suffix('.' + extension), dpi=160, bbox_inches='tight')
    plt.close(fig)


def report(input_path, config_path, out):
    raw = input_path.read_bytes(); data = json.loads(raw)
    if data['schema_version'] != 1:
        raise ValueError('unsupported backtest input schema')
    config_raw = config_path.read_bytes(); settings = json.loads(config_raw)
    config = BacktestConfig(**settings)
    previous = out / 'manifest.json'
    if previous.exists():
        old = json.loads(previous.read_text())
        if old['input_sha256'] != hashlib.sha256(raw).hexdigest() or old['config_sha256'] != hashlib.sha256(config_raw).hexdigest():
            raise ValueError('input/config differs from this output directory; use a new experiment directory')
    out.mkdir(parents=True, exist_ok=True)
    summaries = []
    for constrained in (True, False):
        name = 'constrained' if constrained else 'unconstrained'
        result = run_backtest(data['opportunities'], data['start_at'], data['end_at'], config, constrained)
        for kind in ('curves', 'daily', 'fills'):
            csv_write(out / f'{name}_{kind}.csv', result[kind])
        with (out / f'{name}_decisions.jsonl').open('w') as f:
            for row in result['decisions']:
                f.write(json.dumps(row, allow_nan=False, sort_keys=True) + '\n')
        summary = {k: v for k, v in result.items() if k not in ('curves', 'daily', 'decisions', 'fills')}
        (out / f'{name}_summary.json').write_text(json.dumps(summary, indent=2, allow_nan=False) + '\n')
        summaries.extend({'regime': name, **s} for s in result['summaries'])
        draw(result, data, out / name)
        comparison = selection_performance(data['opportunities'], result['decisions'], data['start_at'], data['end_at'], config)
        csv_write(out / f'{name}_selection_curves.csv', comparison['curves'])
        (out / f'{name}_selection_summary.json').write_text(json.dumps(
            {k:v for k,v in comparison.items() if k != 'curves'}, indent=2, allow_nan=False)+'\n')
        draw_selection(comparison, data, config, constrained, out / f'{name}_selection')
    manifest = {'input': str(input_path.resolve()), 'input_sha256': hashlib.sha256(raw).hexdigest(),
                'config_sha256': hashlib.sha256(config_raw).hexdigest(), 'configuration': settings,
                'source_identity': data['identity'], 'cohort_description': data.get('cohort_description'),
                'source_run_id': data['run_id'],
                'code_sha256': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in
                                (Path(__file__), ROOT/'src/combos/backtest.py', ROOT/'src/combos/risk.py',
                                 ROOT/'src/combos/performance.py', ROOT/'src/combos/event_store.py',
                                 ROOT/'src/combos/selection_performance.py')}}
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2, allow_nan=False) + '\n')
    csv_write(out / 'summary.csv', summaries)
    print(json.dumps([{'regime': s['regime'], 'model': s['model'], 'fills': s['fills'],
                       'trade_attributed_pnl': s['trade_attributed_pnl'], 'cash_settled_pnl': s['realized_pnl'],
                       'sharpe': s['annualized_sharpe'],
                       'variance_bp2': s['daily_return_variance_bp2'], 'decisions': s['decisions']} for s in summaries], indent=2))


def draw_selection(result, data, config, constrained, output):
    models = sorted({s['model'] for s in result['summaries']})
    fig, axes = plt.subplots((len(models)+1)//2, 2, figsize=(15, 9), squeeze=False, sharex=True)
    labels = {'all_priced': 'Sell every priced print', 'selected': 'Our selected prints', 'rejected': 'Rejected prints'}
    styles = {'all_priced': ('#cccccc', '-'), 'selected': ('#84c9be', '-'), 'rejected': ('#e7b078', '--')}
    for ax, model in zip(axes.flat, models):
        for group in labels:
            rows = [r for r in result['curves'] if r['model'] == model and r['group'] == group]
            s = next(s for s in result['summaries'] if s['model'] == model and s['group'] == group)
            sh = f'{s["annualized_sharpe"]:.2f}' if s['annualized_sharpe'] is not None else 'N/A'
            var = f'{s["daily_return_variance_bp2"]:.3g}' if s['daily_return_variance_bp2'] is not None else 'N/A'
            color, style = styles[group]
            ax.step([datetime.fromtimestamp(r['at'], timezone.utc) for r in rows], [r['equity'] for r in rows],
                    where='post', color=color, linestyle=style,
                    label=f'{labels[group]}: P&L ${s["pnl"]:,.0f}; {s["prints"]:,} prints\nSharpe {sh}; Var {var} bp²; {s["unresolved"]} unknown')
        ax.set_title(NAMES.get(model, model), fontsize=11)
        ax.grid(alpha=.2); ax.legend(fontsize=8, loc='best')
        ax.set_ylabel('Reporting base + trade-attributed P&L ($)')
        ax.ticklabel_format(axis='y', style='plain', useOffset=False)
        ax.set_xlim(datetime.fromtimestamp(data['start_at'], timezone.utc), datetime.fromtimestamp(data['end_at'], timezone.utc))
        ax.xaxis.set_major_locator(mdates.AutoDateLocator(tz=ZoneInfo(config.timezone)))
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %d', tz=ZoneInfo(config.timezone)))
    for ax in list(axes.flat)[len(models):]:
        ax.set_visible(False)
    scope = 'all retained priceable prints' if config.maximum_yes_premium_dollars is None else f'observed YES premium ≤ ${config.maximum_yes_premium_dollars:g}'
    regime = '$10k and risk-limited selection' if constrained else 'unconstrained selection'
    fig.suptitle(f'Selection audit | {scope} | {regime}\n{data["display_name"]}', fontsize=12)
    fig.text(.06, .025, 'All/rejected curves assume unlimited exposure. Known-outcome P&L: all = selected + rejected. Each line starts at the same reporting base.\n'
             'Hypothetical sellers at public YES execution prices; not actual industry P&L. Provisional 7-day statistics; unknown outcomes unscored.\n'
             + data.get('cohort_description', ''), fontsize=8)
    fig.tight_layout(rect=(0, .095, 1, .93))
    for extension in ('png', 'svg'):
        fig.savefig(output.with_suffix('.'+extension), dpi=160, bbox_inches='tight')
    plt.close(fig)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(); report(args.input, args.config, args.out)

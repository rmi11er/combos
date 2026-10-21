#!/usr/bin/env python3
"""One chronological portfolio across observed MLB research dates and gaps.

Reads only completed batch outputs. Missing dates contain no simulated trading,
but positions and actual-settlement cash persist through those gaps. This is a
strategy restricted to the observed dates, not a full-calendar trading backtest.
"""
import argparse
from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import datetime, timezone
import fcntl
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from combos.backtest import BacktestConfig, run_backtest
from mlb_entry_sweep import VARIANTS, metrics, paired_day
from mlb_validation_report import bounds, purge_validation


def load(path):
    return json.loads(Path(path).read_text())


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')
    temporary.replace(path)


def gziprows(path, rows):
    with gzip.open(path, 'wt') as handle:
        for row in rows:
            handle.write(json.dumps(row, separators=(',', ':'), allow_nan=False) + '\n')


def utc():
    return datetime.now(timezone.utc).isoformat()


def discover(batch_roots, plan):
    """Completion certificates, not the presence of a half-written replay file."""
    requested = {date for date, fold in plan['dates'].items() if fold != 'previously_inspected_reference'}
    files = {}; empty = set(); states = {}
    for root in map(Path, batch_roots):
        path = root / 'batch_status.json'
        if not path.exists():
            states[str(root)] = 'awaiting_batch_status'
            continue
        state = load(path); states[str(root)] = state.get('status', 'unknown')
        for date, day in state.get('days', {}).items():
            if date not in requested:
                continue
            if day.get('status') == 'complete_empty_eligible_scope':
                certificate = load(root / date / 'cohort/summary.json')
                if certificate.get('complete_census') is not True or certificate.get('date') != date:
                    raise ValueError('invalid_complete_empty_day_certificate')
                empty.add(date)
                continue
            if day.get('status') != 'complete':
                continue
            file = root / date / 'replay/opportunities.json'
            key = date + '/replay'
            replay_stage = state.get('stages', {}).get(key, {})
            recorded = replay_stage.get('output_sha256', {})
            expected = recorded.get(str(file.resolve()), recorded.get(str(file)))
            if replay_stage.get('status') != 'complete' or expected is None or digest(file) != expected:
                raise ValueError('completed_replay_hash_certificate_missing_or_changed:' + date)
            if date in files and digest(files[date]) != expected:
                raise ValueError('conflicting_completed_replay_for_date:' + date)
            files[date] = file
    if empty.intersection(files):
        raise ValueError('conflicting_empty_and_priced_date_certificates')
    return files, sorted(empty), states


def prepare(inputs, plan, empty_dates=()):
    """Strict source pairing and fold purge before any simulated selection."""
    by_date = {}; missing = []; coverage = {}
    models = plan['primary_models']
    for date, fold in sorted(plan['dates'].items()):
        if fold == 'previously_inspected_reference':
            continue
        if date in empty_dates:
            by_date[date] = []; coverage[date] = {'complete_empty_eligible_scope': True}
            continue
        data = inputs.get(date)
        if data is None:
            missing.append({'date': date, 'fold': fold, 'reason': 'awaiting_completed_day'})
            continue
        if data.get('cohort_description') != 'Complete daily census':
            raise ValueError('longitudinal_requires_completed_daily_census')
        left, right = bounds(date, plan['timezone'])
        if data['start_at'] > left or data['end_at'] < right:
            raise ValueError('replay_does_not_cover_complete_requested_day')
        actual = {row['model'] for row in data['opportunities']}
        absent = sorted(set(models) - actual)
        if absent:
            missing.append({'date': date, 'fold': fold, 'reason': 'required_primary_models_unavailable',
                            'missing_primary_models': absent})
            continue
        subset = {**data, 'opportunities': [row for row in data['opportunities'] if row['model'] in models]}
        try:
            rows, _, _, counts = paired_day(subset, date)
        except ValueError as exc:
            if str(exc) == 'no_common_priced_complete_day_data':
                missing.append({'date': date, 'fold': fold, 'reason': 'empty_primary_source_intersection'})
                continue
            raise
        by_date[date] = rows
        coverage[date] = {'priced_by_model': counts, 'common_prints_before_purge': len(rows) // len(models),
                          'fee_scenario': data.get('identity', {}).get('fee_scenario')}
    purged = purge_validation(by_date, plan) if plan['evaluation'].get('purge_shared_fixtures_between_development_and_validation', True) else {}
    rows = sorted((row for day in by_date.values() for row in day), key=lambda row: (row['at'], row['evaluation_id'], row['model']))
    identities = set()
    for row in rows:
        key = row['model'], row['evaluation_id']
        if key in identities:
            raise ValueError('repeated_evaluation_across_dated_inputs')
        identities.add(key)
    return rows, {'observed_dates': sorted(by_date), 'empty_scope_dates': sorted(empty_dates),
                  'missing_dates': missing, 'coverage': coverage,
                  'validation_shared_fixture_purged_prints': purged,
                  'purge_status': 'provisional_missing_development_dates' if any(r['fold'] == 'development' for r in missing) else 'all_priced_development_dates_available'}


def sampled_statistics(selected, observed_dates, plan):
    """No calendar-gap zero rows or independence assumption enter statistics."""
    from zoneinfo import ZoneInfo
    buckets = {date: [] for date in observed_dates}
    for row in selected:
        date = datetime.fromtimestamp(row['at'], ZoneInfo(plan['timezone'])).date().isoformat()
        buckets[date].append(row)
    daily = [{'date': date, 'fold': plan['dates'][date], **metrics(rows)} for date, rows in sorted(buckets.items())]
    resolved = [day for day in daily if day['unknown_outcomes'] == 0]
    pnl = [day['known_net_pnl'] for day in resolved]
    variance = statistics.variance(pnl) if len(pnl) > 1 else None
    minimum = plan['evaluation']['minimum_complete_resolved_slates_for_descriptive_sharpe']
    ratio = statistics.mean(pnl) / math.sqrt(variance) if len(pnl) >= minimum and len(resolved) == len(daily) and variance else None
    fixtures = defaultdict(set)
    for date, rows in buckets.items():
        for row in rows:
            for fixture in row['buckets']['fixture']:
                fixtures[fixture].add(date)
    return {'annualized_sharpe': None, 'daily_return_variance': None,
            'sharpe_reason': 'calendar trading gaps and shared outcomes; no daily IID Sharpe inferred',
            'observed_date_pnl_variance_dollars2': variance,
            'descriptive_observed_date_pnl_mean_sd_ratio': ratio,
            'observed_dates': len(daily), 'fully_resolved_observed_dates': len(resolved),
            'fixtures_shared_across_observed_dates': sum(len(dates) > 1 for dates in fixtures.values()),
            'variance_basis': 'known trade-attributed PnL on fully resolved observed dates only; not independent-slate or calendar variance',
            'daily_contributions': daily}


def compact_curve(rows, maximum=2400):
    """Keep time ordering plus local extrema for displayed accounting curves."""
    if len(rows) <= maximum:
        return rows
    fields = ('trade_attributed_pnl', 'accepted_point_edge', 'committed_cash')
    size = max(1, math.ceil(len(rows) / max(1, maximum // (2 * len(fields) + 2))))
    selected = {0, len(rows) - 1}
    for left in range(0, len(rows), size):
        right = min(left + size, len(rows))
        selected.update((left, right - 1))
        for field in fields:
            selected.add(min(range(left, right), key=lambda index: rows[index][field]))
            selected.add(max(range(left, right), key=lambda index: rows[index][field]))
    return [rows[index] for index in sorted(selected)]


def annotate_unknown_bounds(curves, selected):
    changes = defaultdict(lambda: [0., 0.])
    for row in selected:
        if row['yes_settlement'] is None:
            changes[row['at']][0] += row['quantity'] * (row['yes_price'] - 1) - row['maker_fee']
            changes[row['at']][1] += row['quantity'] * row['yes_price'] - row['maker_fee']
    lower = upper = 0.
    for row in curves:
        deltas = changes.get(row['at'], (0., 0.))
        lower += deltas[0]; upper += deltas[1]
        row['trade_pnl_lower_bound'] = row['trade_attributed_pnl'] + lower
        row['trade_pnl_upper_bound'] = row['trade_attributed_pnl'] + upper


def evaluate(rows, coverage, plan, output, heartbeat=lambda **kwargs: None):
    if not rows:
        return {'coverage': coverage, 'records': [], 'reason': 'no_paired_priced_opportunities_yet'}, {}
    observed = coverage['observed_dates']
    start = bounds(observed[0], plan['timezone'])[0]
    end = bounds(observed[-1], plan['timezone'])[1]
    records = []; curves = {}
    for model in plan['primary_models']:
        model_rows = [row for row in rows if row['model'] == model]
        for variant, label, overrides in VARIANTS:
            config = BacktestConfig(entry_basis=plan['entry_basis'], timezone=plan['timezone'],
                                    **plan['baseline_limits'], **overrides)
            for constrained in (True, False):
                regime = 'funded' if constrained else 'unlimited'
                heartbeat(stage='simulation', model=model, variant=variant, regime=regime)
                result = run_backtest(model_rows, start, end, config, constrained)
                selected = [row for row in result['decisions'] if row['accepted']]
                annotate_unknown_bounds(result['curves'], selected)
                record = {'model': model, 'variant': variant, 'label': label, 'regime': regime,
                          'configuration': asdict(config), 'selected': metrics(selected),
                          'sampled_statistics': sampled_statistics(selected, observed, plan),
                          'rejection_counts': dict(Counter(row['reason'] for row in result['decisions'] if not row['accepted']))}
                raw_summary = result['summaries'][0]
                # Do not export the engine's all-calendar zero-filled statistics.
                keep = ('evaluations', 'fills', 'realized_pnl', 'ending_equity', 'trade_attributed_pnl',
                        'ending_trade_attributed_equity', 'ending_committed_cash', 'peak_committed_cash',
                        'minimum_starting_funding_for_path', 'additional_funding_above_reporting_base',
                        'max_settled_equity_drawdown_dollars', 'max_trade_attributed_drawdown_dollars')
                record['portfolio'] = {key: raw_summary[key] for key in keep}
                prefix = output / (model + '__' + variant + '__' + regime)
                gziprows(prefix.with_suffix('.decisions.jsonl.gz'), result['decisions'])
                gziprows(prefix.with_suffix('.curves.jsonl.gz'), result['curves'])
                gziprows(prefix.with_suffix('.fills.jsonl.gz'), result['fills'])
                curves[model, variant, regime] = compact_curve(result['curves'])
                records.append(record)
    return {'study_id': plan['study_id'], 'start_at': start, 'end_at': end, 'coverage': coverage, 'records': records,
            'interpretation': [
                'One funded ledger per model/policy from first observed date through last; no day resets.',
                'Positions and actual-settlement cash persist across observed dates and unobserved gaps.',
                'The strategy submits hypothetical trades only on the observed planned dates. Gap opportunities are unknown.',
                'Known eventual settlement PnL and expected edge are attributed to trade time for display; neither funds trades before settlement.',
                'Unlimited portfolios require their reported funding; adding a 10k display base does not make them funded accounts.',
                'Per-date/fold results are contributions of this single portfolio, not separately funded experiments.',
                'Common primary-source intersection, original public sizes and explicit fee scenarios; no RFQ acceptance inferred.',
                'Unknown outcomes remain bounded. Fee assumptions and missing dates preclude a verified stability claim.']}, curves


def plot(result, curves, output):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    plt.style.use('dark_background'); plt.rcParams['text.parse_math'] = False
    records = result['records']; models = sorted({row['model'] for row in records})
    source_colors = {'kalshi': '#73a0c4', 'polymarket': '#84c9be', 'exchange_blend_equal': '#d2bd69', 'exchange_blend_pm75': '#c78aca'}
    colors = {'sell_every_priced_print': '#b5b5b5', 'edge_0c': '#cf9c68', 'edge_0_1c': '#76a1d1',
              'edge_0_3c': '#81cbbb', 'edge_0_5c': '#c69bd9', 'edge_0_3c_per_leg': '#d886a0'}
    missing = len(result['coverage']['missing_dates']); count = len(result['coverage']['observed_dates'])
    for regime in ('funded', 'unlimited'):
        fig, axes = plt.subplots(3, len(models), figsize=(5.4 * len(models), 11), sharex=True, squeeze=False)
        for column, model in enumerate(models):
            for variant, label, _ in VARIANTS:
                series = curves[model, variant, regime]
                times = [datetime.fromtimestamp(row['at'], timezone.utc) for row in series]
                record = next(row for row in records if (row['model'], row['variant'], row['regime']) == (model, variant, regime))
                variance = record['sampled_statistics']['observed_date_pnl_variance_dollars2']
                var_text = 'N/A' if variance is None else f'{variance:,.0f}'
                axes[0, column].step(times, [row['trade_attributed_pnl'] for row in series], where='post',
                    color=colors[variant], label=f'{label} · Sharpe N/A · Var {var_text} $²', linewidth=1.25)
                axes[0, column].fill_between(times, [row['trade_pnl_lower_bound'] for row in series],
                    [row['trade_pnl_upper_bound'] for row in series], step='post', color=colors[variant], alpha=.055)
                axes[1, column].step(times, [row['accepted_point_edge'] for row in series], where='post', color=colors[variant], label=label, linewidth=1.25)
                axes[2, column].step(times, [row['committed_cash'] for row in series], where='post', color=colors[variant], label=label, linewidth=1.25)
            axes[0, column].set_title(model.replace('_', ' '), color=source_colors.get(model)); axes[0, column].legend(fontsize=7)
            for axis in axes[:, column]:
                axis.grid(alpha=.2); axis.axhline(0, color='gray', linewidth=.5)
                axis.xaxis.set_major_formatter(mdates.DateFormatter('%b %d'))
            if regime == 'funded':
                axes[2, column].axhline(records[0]['configuration']['capital_dollars'], color='white', linestyle=':', linewidth=.7)
        for axis, label in zip(axes[:, 0], ('Cumulative known P&L ($)', 'Cumulative expected net edge ($)', 'Committed cash ($)')):
            axis.set_ylabel(label)
        title = '$10k initial capital; existing risk limits; one continuing ledger' if regime == 'funded' else 'Unlimited funding and concentration; same observed print sizes'
        fig.suptitle('MLB longitudinal fixed-policy comparison · ' + title + f'\n{count} observed dates; {missing} planned dates missing', fontsize=13)
        fig.text(.045, .025, 'Trade-attributed known eventual outcomes; actual cash releases at settlement. Positions carry through gaps; no simulated trading on missing dates.\n'
                 'Variance is descriptive P&L variance across fully resolved observed dates, not calendar daily return variance. Unknown bounds and fee assumptions are in summary.json.', fontsize=9)
        fig.tight_layout(rect=(0, .075, 1, .94))
        for extension in ('png', 'svg'):
            fig.savefig(output / (regime + '.' + extension), dpi=140)
        plt.close(fig)
    for regime in ('funded', 'unlimited'):
        fig, axes = plt.subplots(1, len(models), figsize=(5.4 * len(models), 4.8), squeeze=False)
        for axis, model in zip(axes.ravel(), models):
            for variant, label in (('sell_every_priced_print', 'Sell every priced print'), ('edge_0_3c', 'Current 0.3c after-fee threshold')):
                series = curves[model, variant, regime]
                times = [datetime.fromtimestamp(row['at'], timezone.utc) for row in series]
                record = next(row for row in records if (row['model'], row['variant'], row['regime']) == (model, variant, regime))
                variance = record['sampled_statistics']['observed_date_pnl_variance_dollars2']
                variance_label = 'N/A' if variance is None else f'{variance:,.0f}'
                axis.step(times, [row['trade_attributed_pnl'] for row in series], where='post', color=colors[variant],
                          label=label + '\nSharpe N/A · Var ' + variance_label + ' $²')
                axis.fill_between(times, [row['trade_pnl_lower_bound'] for row in series],
                                  [row['trade_pnl_upper_bound'] for row in series], step='post', color=colors[variant], alpha=.12)
            axis.set_title(model.replace('_', ' '), color=source_colors.get(model)); axis.legend(fontsize=7); axis.grid(alpha=.2)
            axis.xaxis.set_major_formatter(mdates.DateFormatter('%b %d')); axis.axhline(0, color='gray', linewidth=.5)
        axes[0, 0].set_ylabel('Cumulative known P&L ($)')
        fig.suptitle(f'MLB sell-all versus current entry rule · {regime} · {count} observed dates / {missing} missing')
        fig.text(.04, .03, 'One continuing ledger per policy; trade-time attribution; fee assumptions and unknown-outcome bounds in summary.json. Gap opportunities remain unobserved.', fontsize=9)
        fig.tight_layout(rect=(0, .1, 1, .91))
        for extension in ('png', 'svg'):
            fig.savefig(output / ('selection_' + regime + '.' + extension), dpi=140)
        plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--batch-root', nargs='+', required=True, type=Path)
    parser.add_argument('--plan', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--watch', action='store_true')
    parser.add_argument('--poll-seconds', type=float, default=30)
    parser.add_argument('--max-runtime-seconds', type=float, default=172800)
    args = parser.parse_args()
    if not 1 <= args.poll_seconds <= 30 or not 0 < args.max_runtime_seconds <= 172800:
        raise ValueError('invalid_bounded_watch_parameters')
    args.out.mkdir(parents=True, exist_ok=True)
    lock = (args.out / 'watch.lock').open('a')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise SystemExit('Another longitudinal watcher owns this output directory.')
    deadline = time.monotonic() + args.max_runtime_seconds
    frozen = {str(path.resolve()): digest(path) for path in [args.plan, Path(__file__),
              ROOT/'scripts/mlb_entry_sweep.py', ROOT/'scripts/mlb_validation_report.py',
              ROOT/'src/combos/backtest.py', ROOT/'src/combos/risk.py', ROOT/'src/combos/performance.py']}
    state = {'status': 'starting', 'pid': os.getpid(), 'started_at': utc(), 'frozen_sha256': frozen}
    def heartbeat(**values):
        if time.monotonic() >= deadline:
            raise TimeoutError('longitudinal_watch_runtime_limit')
        state.update(values, updated_at=utc()); save(args.out / 'watch_status.json', state)
    previous = load(args.out / 'latest.json').get('input_identity') if (args.out / 'latest.json').exists() else None
    try:
        while True:
            for name, expected in frozen.items():
                if digest(name) != expected:
                    raise ValueError('longitudinal_code_or_plan_changed:' + name)
            plan = load(args.plan)
            files, empty, states = discover(args.batch_root, plan)
            identity = {'input_sha256': {date: digest(file) for date, file in sorted(files.items())},
                        'empty_scope_dates': empty, 'frozen_sha256': frozen}
            key = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
            heartbeat(status='watching', completed_input_dates=sorted(files), empty_scope_dates=empty, batch_states=states)
            if (files or empty) and key != previous:
                rows, coverage = prepare({date: load(file) for date, file in files.items()}, plan, empty)
                version = args.out / 'versions' / key[:20]; version.mkdir(parents=True, exist_ok=True)
                if rows:
                    result, curves = evaluate(rows, coverage, plan, version, heartbeat)
                    heartbeat(stage='rendering')
                    plot(result, curves, version)
                else:
                    result = {'coverage': coverage, 'records': [], 'reason': 'no_paired_priced_opportunities_yet'}
                result['input_identity'] = key; result['identity'] = identity
                save(version / 'summary.json', result)
                save(args.out / 'latest.json', {'input_identity': key, 'version': str(version.resolve()),
                                              'observed_dates': coverage['observed_dates'], 'updated_at': utc()})
                previous = key
                heartbeat(stage='rendered', latest_version=str(version.resolve()), observed_dates=coverage['observed_dates'],
                          missing_dates=coverage['missing_dates'])
            all_dates = {date for date, fold in plan['dates'].items() if fold != 'previously_inspected_reference'}
            if not args.watch or all_dates <= (set(files) | set(empty)):
                heartbeat(status='complete' if all_dates <= (set(files) | set(empty)) else 'snapshot_complete_waiting_for_more_dates')
                return
            time.sleep(min(args.poll_seconds, max(0, deadline - time.monotonic())))
    except BaseException as exc:
        state.update(status='stopped', reason=type(exc).__name__ + ': ' + str(exc), updated_at=utc())
        save(args.out / 'watch_status.json', state)
        raise
    finally:
        lock.close()


if __name__ == '__main__':
    main()

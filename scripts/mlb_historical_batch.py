#!/usr/bin/env python3
"""Durable research pipeline waiting for complete acquired MLB calendar days.

Plans by default. --execute runs only public metadata/exchange-history adapters
and local replays/reports. No order endpoint or Pinnacle request is invoked.
Ready days run sequentially; incomplete tape never becomes a sample backtest.
Code and study/fee policy are frozen by hash before execution. Failed stages
retain logs and bounded attempts across restarts; no automatic budget increase.
"""
import argparse
from datetime import datetime, timedelta, timezone
import gzip
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
PIPELINE_SCRIPTS = (
    'mlb_historical_batch.py', 'mlb_daily_cohort.py', 'mlb_native_cohort.py',
    'mlb_public_day_acquire.py', 'mlb_historical_fees.py', 'mlb_exchange_acquire.py',
    'mlb_model_replay.py', 'mlb_model_report.py', 'mlb_entry_sweep.py',
    'mlb_validation_report.py', 'mlb_risk_capacity.py', 'cfb_full_exchange_acquire.py', 'rate_limit.py',
)
PIPELINE_SOURCES = (
    '__init__.py', 'backtest.py', 'event_store.py', 'performance.py', 'risk.py',
    'fees.py', 'kalshi_history.py', 'historical_fair.py', 'pricing.py',
    'joint_pricing.py', 'weighted_fair.py', 'observations.py',
)


def frozen_code_paths(root=ROOT):
    """Explicit script dependency closure allows unrelated NFL research edits."""
    return ([root / 'scripts' / name for name in PIPELINE_SCRIPTS]
            + [root / 'src/combos' / name for name in PIPELINE_SOURCES])


def interpreter_path(path):
    # Resolving a venv's Python symlink selects the base interpreter and loses
    # the environment's installed packages in child stages.
    return Path(os.path.abspath(path))


def load(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')
    temp.replace(path)


def utc():
    return datetime.now(timezone.utc).isoformat()


def day_readiness(acquisition, date):
    """Cheap completeness check; the adapter verifies every page/hash/cursor."""
    start = datetime.strptime(date, '%Y-%m-%d').replace(tzinfo=ZoneInfo('America/Chicago'))
    lo, hi = start.timestamp(), (start + timedelta(days=1)).timestamp()
    paths = list((acquisition / date).glob('*/manifest.json'))
    partitions = [(p, load(p)) for p in paths]
    if not partitions or any(m.get('complete') is not True for _, m in partitions):
        return {'ready': False, 'reason': 'awaiting_complete_partitions', 'known_partitions': len(partitions)}
    cursor = lo
    for path, manifest in sorted(partitions, key=lambda item: item[1]['start_at']):
        left, right = manifest['start_at'], manifest['end_at']
        if left < cursor or not lo <= left < right <= hi:
            raise ValueError('invalid_or_overlapping_acquisition_partition:' + str(path))
        if left != cursor:
            return {'ready': False, 'reason': 'awaiting_partition_gap', 'known_partitions': len(partitions)}
        if not manifest.get('pages'):
            raise ValueError('complete_partition_has_no_pages:' + str(path))
        cursor = right
    return {'ready': cursor == hi, 'reason': 'complete' if cursor == hi else 'awaiting_day_tail',
            'known_partitions': len(partitions),
            'manifest_sha256': {str(p.resolve()): digest(p) for p, _ in partitions}}


def has_eligible_scope(cohort):
    with gzip.open(cohort / 'candidate_trades.jsonl.gz', 'rt') as handle:
        for line in handle:
            row = json.loads(line); c = row['classification']; trade = row['trade']
            side = trade.get('taker_outcome_side', trade.get('taker_side'))
            at = datetime.fromisoformat(trade['created_time'].replace('Z', '+00:00')).timestamp()
            if (c['distinct_fixtures'] and 2 <= c['nlegs'] <= 4 and side == 'yes'
                    and at < c['earliest_scheduled_start'] - 60):
                return True
    return False


def identity_scope(cohort):
    """Count whole pregame candidates; an unpriced date is not a zero return."""
    from mlb_exchange_acquire import unsupported_identity_legs, IDENTITY_POLICY_VERSION
    with gzip.open(cohort / 'combo_markets.json.gz', 'rt') as f:
        markets = json.load(f)
    result = {'policy_version': IDENTITY_POLICY_VERSION, 'candidates': 0,
              'supported': 0, 'excluded': [], 'outcomes_used': False}
    with gzip.open(cohort / 'candidate_trades.jsonl.gz', 'rt') as f:
        for line in f:
            row = json.loads(line); c = row['classification']; t = row['trade']
            at = datetime.fromisoformat(t['created_time'].replace('Z', '+00:00')).timestamp()
            if not (c['distinct_fixtures'] and 2 <= c['nlegs'] <= 4
                    and t.get('taker_outcome_side', t.get('taker_side')) == 'yes'
                    and at < c['earliest_scheduled_start'] - 60):
                continue
            result['candidates'] += 1
            bad = unsupported_identity_legs(markets[t['ticker']]['mve_selected_legs'])
            if bad:
                result['excluded'].append({'trade_id':t['trade_id'], 'legs':bad})
            else:
                result['supported'] += 1
    return result


def validate_output(stage, day, date):
    if stage == 'cohort':
        result = load(day / 'cohort/summary.json')
        if result.get('complete_census') is not True or result.get('date') != date:
            raise ValueError('cohort_is_not_complete_requested_date')
        coverage = load(day / 'cohort/metadata_coverage.json')
        underlying = load(day / 'cohort/underlying_acquisition.json')
        if coverage['missing'] or underlying['missing']:
            raise ValueError('incomplete_native_metadata')
    elif stage == 'exchange':
        result = load(day / 'exchange/acquisition.json')
        if len(result['results']) != result['plan']['jobs']:
            raise ValueError('incomplete_exchange_job_count')
        failed = [r for r in result['results'] if r.get('status') != 200]
        if failed:
            raise ValueError('failed_exchange_jobs:' + json.dumps([r.get('status') for r in failed]))
    elif stage == 'replay':
        result = load(day / 'replay/opportunities.json')
        if result.get('cohort_description') != 'Complete daily census':
            raise ValueError('replay_is_not_complete_census')
        if any(r['source']['sampling_method'] != 'census' for r in result['opportunities']):
            raise ValueError('sampled_rows_in_complete_replay')


def stage_commands(python, acquisition, day, date, fee, plan, workers, metadata_budget, seed):
    def command(script, *args):
        return [str(python), str(ROOT / 'scripts' / script), *map(str, args)]
    cohort_args = ['--acquisition', acquisition, '--date', date, '--out', day / 'cohort',
                   '--fee-scenario', fee, '--max-metadata-requests', metadata_budget]
    if seed:
        cohort_args += ['--seed-cohort', seed]
    return [
        ('cohort', command('mlb_daily_cohort.py', *cohort_args), ['cohort/summary.json', 'cohort/metadata_coverage.json',
             'cohort/underlying_acquisition.json', 'cohort/candidate_trades.jsonl.gz', 'cohort/combo_markets.json.gz',
             'cohort/underlying_markets.json.gz', 'cohort/fee_scenario.json']),
        ('exchange', command('mlb_exchange_acquire.py', '--cohort', day / 'cohort', '--out', day / 'exchange',
                             '--workers', workers, '--write-reviewed-mapping'),
             ['exchange/acquisition.json', 'exchange/polymarket_mapping_reviewed.json']),
        ('replay', command('mlb_model_replay.py', '--cohort', day / 'cohort', '--exchange', day / 'exchange',
                           '--out', day / 'replay', '--fee-scenario', fee), ['replay/opportunities.json', 'replay/coverage.json']),
        ('report', command('mlb_model_report.py', '--input', day / 'replay/opportunities.json', '--date', date,
                           '--out', day / 'common_model_report', '--common-only'),
             ['common_model_report/manifest.json', 'common_model_report/constrained_summary.json',
              'common_model_report/unconstrained_summary.json', 'common_model_report/constrained.png',
              'common_model_report/unconstrained.png']),
        ('entry_sweep', command('mlb_entry_sweep.py', '--input', day / 'replay/opportunities.json', '--date', date,
                                '--out', day / 'entry_sweep'), ['entry_sweep/manifest.json', 'entry_sweep/summary.json',
                                                           'entry_sweep/constrained.png', 'entry_sweep/unconstrained.png']),
        ('risk_capacity', command('mlb_risk_capacity.py', '--input', day / 'replay/opportunities.json', '--date', date,
                                  '--out', day / 'risk_capacity'), ['risk_capacity/manifest.json', 'risk_capacity/summary.json',
                                                                  'risk_capacity/risk_capacity.png']),
    ]


def verify_frozen(manifest):
    for file, expected in manifest['frozen_sha256'].items():
        path = Path(file)
        if not path.exists() or digest(path) != expected:
            raise ValueError('frozen_code_or_policy_changed:' + file)


def transient_failure(log):
    # Explicit data/mapping/entitlement/budget errors must not be retried merely
    # because an earlier attempt in the same log happened to mention HTTP.
    tail = log.read_text(errors='replace')[-12000:]
    permanent = ('Incomplete combo metadata', 'Incomplete underlying metadata', 'budget', 'HTTP 40',
                 'hash_or_path_mismatch', 'pagination_query_mismatch', 'invalid_fee', 'unsupported_fee',
                 'no_eligible_native_fixture_windows')
    if any(word in tail for word in permanent):
        return False
    return bool(re.search(r'HTTP (?:429|5\d\d)|transport_failure|TransportError|ConnectionError|ReadTimeout|ConnectTimeout', tail))


def run_command(command, log, timeout, heartbeat, poll_seconds):
    with log.open('w') as output:
        process = subprocess.Popen(command, cwd=ROOT, stdout=output, stderr=subprocess.STDOUT)
        deadline = time.monotonic() + timeout
        try:
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError('stage_runtime_limit')
                try:
                    return process.wait(timeout=min(poll_seconds, remaining))
                except subprocess.TimeoutExpired:
                    heartbeat(process.pid)
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill(); process.wait(timeout=10)


def run_stage(key, command, output_paths, state, state_path, manifest, args, validate=None):
    previous = state['stages'].get(key, {})
    if previous.get('status') == 'complete':
        for file, expected in previous['output_sha256'].items():
            if not Path(file).exists() or digest(Path(file)) != expected:
                raise ValueError('completed_stage_output_changed:' + file)
        return
    attempts = previous.get('attempts', 0)
    while attempts < args.max_stage_attempts:
        verify_frozen(manifest)
        attempts += 1
        log = args.out / 'logs' / (key.replace('/', '_') + f'.attempt{attempts}.log')
        log.parent.mkdir(exist_ok=True)
        stage = {'status': 'running', 'attempts': attempts, 'command': command, 'started_at': utc(), 'log': str(log)}
        state['stages'][key] = stage
        save(state_path, state)
        def heartbeat(pid):
            stage.update(heartbeat_at=utc(), child_pid=pid)
            save(state_path, state)
        code = run_command(command, log, args.stage_timeout_seconds, heartbeat, args.poll_seconds)
        stage.update(exit_code=code, ended_at=utc())
        if code == 0:
            try:
                verify_frozen(manifest)
                if validate:
                    validate()
                if any(not p.exists() for p in output_paths):
                    raise ValueError('stage_missing_success_artifact:' + key)
            except Exception as error:
                stage.update(status='failed', error=str(error)); save(state_path, state)
                prefix = 'failed_exchange_jobs:'
                if str(error).startswith(prefix):
                    statuses = json.loads(str(error)[len(prefix):])
                    if statuses and all(s is None or s == 429 or isinstance(s, int) and 500 <= s < 600 for s in statuses):
                        if attempts < args.max_stage_attempts:
                            time.sleep(min(30, args.poll_seconds))
                            continue
                        raise RuntimeError('stage_attempts_exhausted:' + key) from error
                raise
            stage.update(status='complete', output_sha256={str(p): digest(p) for p in output_paths})
            save(state_path, state)
            print(json.dumps({'stage': key, 'status': 'complete', 'at': utc()}), flush=True)
            return
        stage['status'] = 'failed'; save(state_path, state)
        if not transient_failure(log):
            raise RuntimeError('nontransient_stage_failure:' + key + '; see ' + str(log))
        if attempts < args.max_stage_attempts:
            time.sleep(min(30, args.poll_seconds))
    raise RuntimeError('stage_attempts_exhausted:' + key)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--acquisition', type=Path, default=ROOT / 'runs/mlb_historical_20260907/daily_acquisition')
    parser.add_argument('--out', type=Path, required=True, help='Separate output root for this dated fee scenario')
    fee_group = parser.add_mutually_exclusive_group(required=True)
    fee_group.add_argument('--fee-scenario', type=Path, help='One fee policy explicitly covering every requested date')
    fee_group.add_argument('--fee-scenario-dir', type=Path, help='Directory containing YYYY-MM-DD.json fee policies')
    parser.add_argument('--plan', type=Path, default=ROOT / 'config/mlb_validation_20260907.json')
    parser.add_argument('--dates', nargs='+', help='Subset of frozen study dates; default all except inspected September 5')
    parser.add_argument('--reference-input', type=Path, default=ROOT / 'runs/mlb_historical_20260907/replay/opportunities.json')
    parser.add_argument('--seed-cohort', type=Path, default=ROOT / 'runs/mlb_historical_20260907/cohort')
    parser.add_argument('--python', type=Path, default=ROOT / '.venv/bin/python')
    parser.add_argument('--workers', type=int, default=6)
    parser.add_argument('--max-metadata-requests', type=int, default=10000)
    parser.add_argument('--max-stage-attempts', type=int, default=2)
    parser.add_argument('--poll-seconds', type=float, default=20)
    parser.add_argument('--wait-timeout-seconds', type=float, default=43200)
    parser.add_argument('--stage-timeout-seconds', type=float, default=14400)
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    for name in ('acquisition', 'out', 'fee_scenario', 'fee_scenario_dir', 'plan', 'reference_input', 'seed_cohort', 'python'):
        if getattr(args, name) is not None:
            path = getattr(args, name)
            setattr(args, name, interpreter_path(path) if name == 'python' else path.resolve())
    if not (1 <= args.workers <= 6 and 1 <= args.poll_seconds <= 30 and 1 <= args.max_stage_attempts <= 3
            and args.max_metadata_requests > 0 and args.wait_timeout_seconds > 0 and args.stage_timeout_seconds > 0):
        raise ValueError('invalid_runtime_budget')
    study = load(args.plan)
    dates = sorted(set(args.dates or [d for d, role in study['dates'].items() if role != 'previously_inspected_reference']))
    if not dates or any(d not in study['dates'] for d in dates):
        raise ValueError('requested_dates_outside_frozen_study_plan')
    for date in dates:
        datetime.strptime(date, '%Y-%m-%d')
    from mlb_historical_fees import load_fee_scenario, require_coverage
    fee_paths = {date: args.fee_scenario or args.fee_scenario_dir / (date + '.json') for date in dates}
    for date in dates:
        fees = load_fee_scenario(fee_paths[date])
        day = datetime.strptime(date, '%Y-%m-%d').replace(tzinfo=ZoneInfo('America/Chicago'))
        require_coverage(fees, day.timestamp(), (day + timedelta(days=1)).timestamp())
    commands = {date: stage_commands(args.python, args.acquisition, args.out / date, date, fee_paths[date],
                                     args.plan, args.workers, args.max_metadata_requests, args.seed_cohort) for date in dates}
    identity = {'dates': dates, 'acquisition': str(args.acquisition), 'fee_scenarios': {d: str(p) for d, p in fee_paths.items()},
                'study_plan': str(args.plan), 'metadata_request_budget_per_attempt': args.max_metadata_requests,
                'max_stage_attempts': args.max_stage_attempts, 'workers': args.workers,
                'reference_input': str(args.reference_input), 'seed_cohort': str(args.seed_cohort),
                'network_scope': 'public Kalshi metadata/candles and Polymarket history only; no Pinnacle/orders',
                'risk_selection': 'unchanged baseline; new days are pipeline screening, not sufficient evidence to set limits'}
    if not args.execute:
        print(json.dumps({'configuration': identity, 'commands': commands, 'execute': False}, indent=2, default=str))
        return
    args.out.mkdir(parents=True, exist_ok=True)
    lock = (args.out / 'batch.lock').open('a+')
    try:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise RuntimeError('batch_already_running_for_output_directory') from None
    lock.seek(0); lock.truncate(); lock.write(str(os.getpid()) + '\n'); lock.flush()
    manifest_path = args.out / 'batch_manifest.json'; state_path = args.out / 'batch_status.json'
    if manifest_path.exists():
        manifest = load(manifest_path)
        if manifest['configuration'] != identity:
            raise ValueError('batch_configuration_changed_use_new_output_directory')
        verify_frozen(manifest)
    else:
        paths = frozen_code_paths()
        paths += [args.plan, *set(fee_paths.values())]
        if args.reference_input.exists():
            paths.append(args.reference_input)
        manifest = {'configuration': identity, 'created_at': utc(),
                    'frozen_sha256': {str(p): digest(p) for p in paths}, 'python': sys.version}
        save(manifest_path, manifest)
        for path in paths:
            if path.suffix == '.py' or path == args.plan or path in fee_paths.values():
                relative = path.relative_to(ROOT) if path.is_relative_to(ROOT) else Path('external') / (digest(path)[:12] + '_' + path.name)
                dest = args.out / 'code_snapshot' / relative
                dest.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(path, dest)
    state = load(state_path) if state_path.exists() else {'started_at': utc(), 'days': {}, 'stages': {}}
    for stage in state['stages'].values():
        if stage.get('status') == 'complete':
            for file, expected in stage['output_sha256'].items():
                if not Path(file).exists() or digest(Path(file)) != expected:
                    raise ValueError('completed_stage_output_changed:' + file)
    for day in state['days'].values():
        if day.get('status') in ('complete', 'complete_empty_eligible_scope', 'collected_unpriced_identity'):
            for file, expected in day.get('manifest_sha256', {}).items():
                if not Path(file).exists() or digest(Path(file)) != expected:
                    raise ValueError('completed_day_acquisition_manifest_changed:' + file)
            if day.get('status') == 'collected_unpriced_identity':
                if digest(Path(day['identity_coverage'])) != day['identity_coverage_sha256']:
                    raise ValueError('unpriced_identity_coverage_changed')
    save(state_path, state)
    deadline = time.monotonic() + args.wait_timeout_seconds
    def interrupt(signum, frame):
        raise KeyboardInterrupt('termination requested')
    signal.signal(signal.SIGTERM, interrupt)
    try:
        while True:
            verify_frozen(manifest)
            remaining = [d for d in dates if state['days'].get(d, {}).get('status') not in ('complete', 'complete_empty_eligible_scope', 'collected_unpriced_identity')]
            if not remaining:
                gaps = [d for d in dates if state['days'][d]['status'] == 'collected_unpriced_identity']
                state.update(status='complete_with_pricing_gaps' if gaps else 'complete',
                             unpriced_identity_dates=gaps, ended_at=utc()); save(state_path, state); return
            progressed = False
            for date in remaining:
                readiness = day_readiness(args.acquisition, date)
                state['days'][date] = {'status': 'ready' if readiness['ready'] else 'waiting_for_tape', **readiness, 'updated_at': utc()}
                save(state_path, state)
                if not readiness['ready']:
                    continue
                day = args.out / date
                for stage, command, artifacts in commands[date]:
                    run_stage(date + '/' + stage, command, [day / p for p in artifacts], state, state_path,
                              manifest, args, lambda s=stage: validate_output(s, day, date))
                    if stage == 'cohort' and not has_eligible_scope(day / 'cohort'):
                        state['days'][date].update(status='complete_empty_eligible_scope', ended_at=utc())
                        break
                    if stage == 'cohort':
                        coverage = identity_scope(day / 'cohort')
                        if coverage['candidates'] and not coverage['supported']:
                            path = day / 'identity_coverage.json'; save(path, coverage)
                            state['days'][date].update(status='collected_unpriced_identity',
                                identity_coverage=str(path), identity_coverage_sha256=digest(path), ended_at=utc())
                            break
                else:
                    state['days'][date].update(status='complete', ended_at=utc())
                save(state_path, state)
                inputs = [args.out / d / 'replay/opportunities.json' for d in dates
                          if state['days'].get(d, {}).get('status') == 'complete']
                if args.reference_input.exists():
                    inputs.insert(0, args.reference_input)
                if inputs:
                    version = hashlib.sha256(''.join(digest(p) for p in inputs).encode()).hexdigest()[:12]
                    report_out = args.out / 'validation' / version
                    command = [str(args.python), str(ROOT / 'scripts/mlb_validation_report.py'), '--input', *map(str, inputs),
                               '--plan', str(args.plan), '--out', str(report_out)]
                    run_stage('validation/' + version, command, [report_out / 'validation.json'], state, state_path, manifest, args)
                    state['latest_validation'] = str(report_out); save(state_path, state)
                progressed = True
            if not progressed:
                if time.monotonic() >= deadline:
                    raise TimeoutError('waiting_for_complete_acquisition_deadline')
                state.update(status='waiting_for_tape', heartbeat_at=utc()); save(state_path, state)
                time.sleep(args.poll_seconds)
    except BaseException as error:
        state.update(status='interrupted' if isinstance(error, KeyboardInterrupt) else 'failed',
                     error=type(error).__name__ + ': ' + str(error), ended_at=utc())
        save(state_path, state)
        raise


if __name__ == '__main__':
    main()

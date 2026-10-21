#!/usr/bin/env python3
"""Watch complete NFL tape days and build full native cohorts automatically."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from mlb_historical_batch import day_readiness
from nfl_playoffs_public_acquire import calendar_days
from nfl_playoffs_exchange_history import save, digest

ROOT = Path(__file__).resolve().parents[1]


def attempts_used(directory):
    path = directory / 'attempts.jsonl'
    if not path.exists():
        return 0
    with path.open() as handle:
        return sum(bool(line.strip()) for line in handle)


def validate_cohort(directory, date):
    summary = json.loads((directory / 'summary.json').read_text())
    coverage = json.loads((directory / 'metadata_coverage.json').read_text())
    if summary.get('sport') != 'NFL' or summary.get('date') != date or summary.get('complete_census') is not True:
        raise ValueError('not_complete_requested_NFL_cohort')
    if coverage['missing']:
        raise ValueError('missing_native_combo_metadata')
    return summary


def verify_frozen(plan):
    for file, expected in plan['frozen_sha256'].items():
        if digest(Path(file)) != expected:
            raise ValueError('frozen_NFL_cohort_code_or_schedule_changed:' + file)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--schedule', type=Path, default=ROOT / 'config/nfl_playoffs_history_2026.json')
    parser.add_argument('--acquisition', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--metadata-budget-per-day', type=int, default=15000)
    parser.add_argument('--poll-seconds', type=float, default=30)
    parser.add_argument('--max-hours', type=float, default=24)
    args = parser.parse_args()
    if not 0 < args.metadata_budget_per_day <= 15000 or not 5 <= args.poll_seconds <= 60 or not 0 < args.max_hours <= 48:
        raise ValueError('invalid_bounded_NFL_watcher_parameters')
    schedule = json.loads(args.schedule.read_text())
    dates = calendar_days(schedule)
    args.out.mkdir(parents=True, exist_ok=True)
    closure = [args.schedule, Path(__file__), ROOT / 'scripts/nfl_playoffs_cohort.py',
               ROOT / 'scripts/nfl_playoffs_exchange_review.py', ROOT / 'scripts/nfl_playoffs_public_acquire.py',
               ROOT / 'scripts/nfl_playoffs_exchange_history.py', ROOT / 'scripts/mlb_historical_batch.py',
               ROOT / 'scripts/mlb_daily_cohort.py', ROOT / 'scripts/mlb_public_day_acquire.py',
               ROOT / 'scripts/rate_limit.py']
    plan = {'schema_version': 1, 'sport': 'NFL', 'dates': dates, 'acquisition': str(args.acquisition.resolve()),
            'metadata_budget_per_day_across_resumes': args.metadata_budget_per_day,
            'frozen_sha256': {str(p.resolve()): digest(p) for p in closure}, 'orders_enabled': False,
            'prerequisite': 'Full calendar tape and native metadata; no sampled fallback',
            'stage': 'Native cohort only; fee/fair/line/payoff review required before net PnL',
            'maximum_stage_attempts': 2}
    path = args.out / 'plan.json'
    if path.exists() and json.loads(path.read_text()) != plan:
        raise ValueError('frozen_NFL_watcher_plan_changed')
    save(path, plan)
    if not args.execute:
        print(json.dumps(plan, indent=2))
        return
    with (args.out / '.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        state_path = args.out / 'state.json'
        state = json.loads(state_path.read_text()) if state_path.exists() else {'schema_version': 1, 'days': {}}
        state.update(status='watching', pid=os.getpid(), started_at=time.time(), orders_enabled=False)
        deadline = time.monotonic() + args.max_hours * 3600
        save(state_path, state)
        while time.monotonic() < deadline:
            verify_frozen(plan)
            for date in dates:
                stage = state['days'].get(date, {})
                directory = args.out / date / 'cohort'
                if stage.get('status') == 'complete':
                    for file, expected in stage['output_sha256'].items():
                        if digest(Path(file)) != expected:
                            raise ValueError('completed_NFL_cohort_output_changed')
                    continue
                if stage.get('status') == 'failed' and stage.get('attempts', 0) >= 2:
                    continue
                ready = day_readiness(args.acquisition, date)
                if not ready['ready']:
                    state['days'][date] = {**stage, 'status': 'waiting_for_complete_tape', 'readiness': ready}
                    continue
                remaining = args.metadata_budget_per_day - attempts_used(directory)
                if remaining < 0:
                    raise ValueError('NFL_day_metadata_budget_exceeded')
                if remaining == 0 and stage.get('status') == 'failed':
                    stage.update(attempts=2, reason='persistent_daily_metadata_budget_exhausted')
                    continue
                attempts = stage.get('attempts', 0) + 1
                command = [sys.executable, str(ROOT / 'scripts/nfl_playoffs_cohort.py'), '--schedule', str(args.schedule),
                           '--acquisition', str(args.acquisition), '--date', date, '--out', str(directory),
                           '--max-metadata-requests', str(remaining)]
                log = args.out / 'logs' / f'{date}.attempt{attempts}.log'
                log.parent.mkdir(exist_ok=True)
                stage = {'status': 'running', 'attempts': attempts, 'command': command, 'log': str(log), 'started_at': time.time()}
                state['days'][date] = stage
                save(state_path, state)
                with log.open('w') as output:
                    child = subprocess.Popen(command, cwd=ROOT, stdout=output, stderr=subprocess.STDOUT)
                    stage['child_pid'] = child.pid
                    while child.poll() is None:
                        state.update(updated_at=time.time(), active_day=date)
                        save(state_path, state)
                        if time.monotonic() >= deadline:
                            child.terminate()
                            child.wait(timeout=10)
                            break
                        time.sleep(args.poll_seconds)
                stage.update(exit_code=child.returncode, finished_at=time.time(), metadata_attempts_total=attempts_used(directory))
                if child.returncode == 0:
                    verify_frozen(plan)
                    summary = validate_cohort(directory, date)
                    files = [directory / name for name in ('summary.json', 'metadata_coverage.json', 'universe_trades.jsonl.gz',
                             'candidate_trades.jsonl.gz', 'combo_markets.json.gz', 'underlying_tickers.json')]
                    stage.update(status='complete', counts=summary['counts'], output_sha256={str(p): digest(p) for p in files})
                else:
                    # Only actual transient transport/server failures merit a
                    # second bounded attempt. Data/metadata errors need review.
                    tail = log.read_text(errors='replace')[-10000:]
                    transient = any(term in tail for term in ('HTTP 429', 'HTTP 500', 'HTTP 502', 'HTTP 503', 'transport_failure'))
                    stage.update(status='failed', attempts=attempts if transient else 2)
                state.update(updated_at=time.time(), active_day=None)
                save(state_path, state)
                print(json.dumps({'date': date, 'status': stage['status'], 'metadata_attempts_total': stage['metadata_attempts_total']}), flush=True)
            complete = [d for d in dates if state['days'].get(d, {}).get('status') == 'complete']
            union = set()
            for date in complete:
                union.update(json.loads((args.out / date / 'cohort/underlying_tickers.json').read_text()))
            save(args.out / 'candidate_underlying_union.json', {'sport': 'NFL', 'complete_days': complete,
                 'tickers': sorted(union), 'scope': 'Primary 2–4 distinct-fixture fullgame pregame candidates; exact line histories remain to acquire'})
            state.update(completed_days=len(complete), updated_at=time.time())
            if len(complete) == len(dates):
                state['status'] = 'complete'
                save(state_path, state)
                break
            save(state_path, state)
            time.sleep(args.poll_seconds)
        else:
            state.update(status='watch_deadline_reached', updated_at=time.time())
            save(state_path, state)


if __name__ == '__main__':
    main()

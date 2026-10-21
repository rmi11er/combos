#!/usr/bin/env python3
"""Bounded complete NFL-study tape collection using the shared public pager.

The public endpoint cannot filter combo sport. Preserve complete market tape;
later exact-leg metadata classification restricts the ten NFL playoff fixtures.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from datetime import datetime, timedelta
import fcntl
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from zoneinfo import ZoneInfo

from mlb_public_day_acquire import Client, collect_partition, read, routes, save, ts

ROOT = Path(__file__).resolve().parents[1]


def calendar_days(schedule):
    if schedule['sport'] != 'NFL' or len(schedule['fixtures']) != 10:
        raise ValueError('ten_fixture_NFL_schedule_required')
    first = datetime.strptime(schedule['trading_start_date'], '%Y-%m-%d').date()
    last = datetime.strptime(schedule['trading_end_date_inclusive'], '%Y-%m-%d').date()
    if first > last or (last - first).days > 31:
        raise ValueError('invalid_bounded_trading_calendar')
    return [(first + timedelta(days=i)).isoformat() for i in range((last - first).days + 1)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--schedule', type=Path, default=ROOT / 'config/nfl_playoffs_history_2026.json')
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--max-new-requests', type=int, default=0)
    parser.add_argument('--workers', type=int, default=2)
    args = parser.parse_args()
    if not 1 <= args.workers <= 2 or not 0 <= args.max_new_requests <= 150000:
        raise ValueError('bounded_NFL_public_budget_or_workers_invalid')
    schedule = read(args.schedule)
    dates = calendar_days(schedule)
    args.out.mkdir(parents=True, exist_ok=True)
    code = [Path(__file__), ROOT / 'scripts/mlb_public_day_acquire.py', ROOT / 'scripts/rate_limit.py']
    plan = {'schema_version': 1, 'study_id': schedule['study_id'], 'sport': 'NFL', 'schedule': schedule,
            'schedule_sha256': hashlib.sha256(args.schedule.read_bytes()).hexdigest(), 'dates': dates,
            'timezone': schedule['timezone'], 'full_calendar_days': len(dates),
            'date_selection': 'All trading dates January5–18 for the first two playoff rounds; user specified before this study.',
            'retention_scope': 'All public market prints required for full pagination; later restrict exact ten NFL fixtures.',
            'shared_Kalshi_pacing_seconds': .18, 'maximum_parallel_workers': 2,
            'paid_odds_requests': 0, 'orders_enabled': False,
            'code_sha256': {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in code}}
    plan_path = args.out / 'plan.json'
    if plan_path.exists() and read(plan_path) != plan:
        raise ValueError('frozen_NFL_collection_plan_or_code_changed')
    save(plan_path, plan)
    if not args.execute:
        print(json.dumps(plan, indent=2))
        return
    if not args.max_new_requests:
        raise ValueError('execution_requires_explicit_public_request_budget')
    with (args.out / '.collector.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        client = Client(args.out, args.max_new_requests)
        started = time.time()
        state = {'schema_version': 1, 'status': 'running', 'pid': os.getpid(), 'started_at': started,
                 'max_new_requests': args.max_new_requests, 'workers': args.workers,
                 'completed_partitions': 0, 'new_GETs': 0, 'orders_enabled': False}
        save(args.out / 'progress.json', state)
        try:
            cutoff = client.get('/historical/cutoff', {})
            save(args.out / ('cutoff_' + str(time.time_ns()) + '.json'), cutoff)
            boundary = ts(cutoff['payload']['trades_created_ts'])
            tasks = []
            for date in dates:
                left = datetime.fromisoformat(date).replace(tzinfo=ZoneInfo(schedule['timezone']))
                at, end = int(left.timestamp()), int((left + timedelta(days=1)).timestamp())
                while at < end:
                    stop = min(at + 3600, end)
                    for lo, hi, endpoint in routes(at, stop, boundary):
                        tasks.append((client, args.out / date / f'{int(lo)}_{int(hi)}', lo, hi, endpoint))
                    at = stop
            state['total_partitions'] = len(tasks)
            results = []
            with ThreadPoolExecutor(max_workers=args.workers) as pool:
                pending = {pool.submit(collect_partition, *task) for task in tasks}
                while pending:
                    done, pending = wait(pending, timeout=30, return_when=FIRST_COMPLETED)
                    for future in done:
                        results.append(future.result())
                    state.update(new_GETs=client.count, completed_partitions=sum(r['complete'] for r in results),
                                 returned_partitions=len(results), updated_at=time.time())
                    save(args.out / 'progress.json', state)
                    if done:
                        print(json.dumps({key: state[key] for key in ('new_GETs', 'completed_partitions', 'total_partitions')}), flush=True)
            state.update(status='complete' if all(r['complete'] for r in results) else 'request_budget_exhausted',
                         all_partitions_complete=all(r['complete'] for r in results), finished_at=time.time())
        except Exception as exc:
            state.update(status='failed', error_type=type(exc).__name__, error=str(exc), finished_at=time.time())
            raise
        finally:
            state.update(new_GETs=client.count, updated_at=time.time())
            save(args.out / 'progress.json', state)


if __name__ == '__main__':
    main()

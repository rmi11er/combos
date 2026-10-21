#!/usr/bin/env python3
"""Durably queue the expanded public-tape collection after the five-date screen.

Uses only the existing public GET collector. This process never reads odds keys,
changes subscriptions, or submits orders. A file lock prevents duplicate queues.
"""
import argparse
from datetime import datetime, timedelta
import fcntl
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]


def write(path, data):
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(data, indent=2)+'\n'); tmp.replace(path)


def complete_day(root, day):
    start = datetime.fromisoformat(day).replace(tzinfo=ZoneInfo('America/Chicago'))
    cursor, end = start.timestamp(), (start+timedelta(days=1)).timestamp()
    parts = [json.loads(p.read_text()) for p in (root/day).glob('*/manifest.json')]
    for p in sorted(parts, key=lambda item: item['start_at']):
        if not p.get('complete') or p['start_at'] != cursor or not cursor < p['end_at'] <= end:
            return False
        cursor = p['end_at']
    return cursor == end


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, default=ROOT/'config/mlb_validation_20260907_expanded.json')
    parser.add_argument('--acquisition', type=Path, default=ROOT/'runs/mlb_historical_20260907/daily_acquisition')
    parser.add_argument('--screen-plan', type=Path, default=ROOT/'config/mlb_validation_20260907.json')
    parser.add_argument('--max-new-requests', type=int, default=400000)
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    if args.max_new_requests < 1:
        raise ValueError('positive_request_budget_required')
    plan = json.loads(args.plan.read_text()); screen = json.loads(args.screen_plan.read_text())
    screening = sorted(d for d, fold in screen['dates'].items() if fold != 'previously_inspected_reference')
    expansion = sorted(d for d, fold in plan['dates'].items() if fold != 'previously_inspected_reference' and d not in screening)
    args.acquisition.mkdir(parents=True, exist_ok=True)
    identity = {'plan_sha256': hashlib.sha256(args.plan.read_bytes()).hexdigest(),
                'screen_plan_sha256': hashlib.sha256(args.screen_plan.read_bytes()).hexdigest(),
                'collector_sha256': hashlib.sha256((ROOT/'scripts/mlb_public_day_acquire.py').read_bytes()).hexdigest(),
                'screen_dates': screening, 'expansion_dates': expansion,
                'max_new_requests': args.max_new_requests}
    if not args.execute:
        print(json.dumps(identity, indent=2)); return
    with (args.acquisition/'expanded_queue.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SystemExit('another_expanded_queue_is_active')
        manifest = args.acquisition/'expanded_queue_manifest.json'
        if manifest.exists() and json.loads(manifest.read_text()) != identity:
            raise ValueError('frozen_expanded_queue_identity_changed')
        write(manifest, identity)
        status_path = args.acquisition/'expanded_queue_status.json'
        while True:
            pending = [d for d in screening if not complete_day(args.acquisition, d)]
            if not pending:
                break
            write(status_path, {'status': 'waiting_for_screen_collection', 'updated_at': time.time(), 'pending_screen_dates': pending})
            time.sleep(30)
        pending = [d for d in expansion if not complete_day(args.acquisition, d)]
        if not pending:
            write(status_path, {'status': 'complete', 'updated_at': time.time(), 'expansion_dates': expansion}); return
        # Keep the frozen full expansion date list even when some dates are cached.
        cmd = [sys.executable, str(ROOT/'scripts/mlb_public_day_acquire.py'), '--out', str(args.acquisition),
               '--dates', *expansion, '--execute', '--workers', '6', '--max-new-requests', str(args.max_new_requests),
               '--plan-file', 'expanded_plan.json', '--date-selection', plan['date_selection']]
        with (args.acquisition/'expanded_acquire.log').open('a') as log:
            child = subprocess.Popen(cmd, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
            while child.poll() is None:
                write(status_path, {'status': 'collecting_expansion', 'updated_at': time.time(), 'collector_pid': child.pid,
                                    'complete_dates': [d for d in expansion if complete_day(args.acquisition, d)],
                                    'expansion_dates': expansion})
                time.sleep(30)
        complete = all(complete_day(args.acquisition, d) for d in expansion)
        write(status_path, {'status': 'complete' if complete else 'incomplete_requires_resume', 'updated_at': time.time(),
                            'collector_exit_code': child.returncode, 'complete_dates': [d for d in expansion if complete_day(args.acquisition, d)],
                            'expansion_dates': expansion})
        if child.returncode or not complete:
            raise SystemExit(child.returncode or 2)


if __name__ == '__main__':
    main()

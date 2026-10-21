#!/usr/bin/env python3
"""Acquire complete requested moneyline-history windows for the NFL study.

Coverage of a successful query and existence of a price state are distinct.
Empty windows before listing stay empty. All output is historical-only.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
import fcntl
import gzip
import hashlib
import json
import os
from pathlib import Path
import sys
import threading
import time
from zoneinfo import ZoneInfo

import requests
from rate_limit import pace

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    if path.suffix == '.gz':
        with gzip.open(temp, 'wt') as handle:
            json.dump(value, handle, separators=(',', ':'), allow_nan=False)
    else:
        temp.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')
    temp.replace(path)


def plan_jobs(review, schedule):
    if review['sport'] != 'NFL' or review['fixture_identity_count'] != 10 or review['moneyline_identity_candidates'] != 20:
        raise ValueError('ten_fixture_twenty_moneyline_review_required')
    target_start = datetime.fromisoformat(schedule['trading_start_date']).replace(tzinfo=ZoneInfo(schedule['timezone'])).timestamp()
    # Retain a full prior day as a PM seed search window. Kalshi additionally
    # requests its documented latest-before-start candle. A missing prior PM
    # state stays unavailable; the collector never backfills with a future price.
    capture_start = int(target_start - 86400)
    jobs, identities = [], []
    for fixture in review['fixtures']:
        official = datetime.fromisoformat(fixture['fixture']['scheduled_start']).timestamp()
        pm_start = datetime.fromisoformat(fixture['polymarket_startTime'].replace('Z', '+00:00')).timestamp()
        end = int(min(official, pm_start) - schedule['pregame_cutoff_seconds'])
        for mapping in fixture['moneyline_identity_candidates']:
            if mapping.get('normal_game_identity_matched') is not True:
                raise ValueError('normal_game_moneyline_identity_required')
            identities.append({**mapping, 'fixture': fixture['fixture'], 'target_start_at': target_start,
                               'capture_start_at': capture_start, 'capture_end_at': end,
                               'polymarket_feesEnabled': fixture['polymarket_moneyline_feesEnabled'],
                               'historical_fee_effective_date_verified': False})
            for index, left in enumerate(range(capture_start, end, 3 * 86400)):
                right = min(end, left + 3 * 86400)
                ticker, token = mapping['kalshi_ticker'], mapping['polymarket_token']
                jobs.append({'venue': 'kalshi', 'identity': ticker, 'part': index,
                    'file': f'kalshi_parts/{ticker}.part{index}.json.gz',
                    'url': f'https://external-api.kalshi.com/trade-api/v2/historical/markets/{ticker}/candlesticks',
                    'params': {'start_ts': left, 'end_ts': right, 'period_interval': 1, 'include_latest_before_start': 'true'},
                    'start_at': left, 'end_at': right})
                jobs.append({'venue': 'polymarket', 'identity': token, 'part': index,
                    'file': f'polymarket_parts/{token}.part{index}.json.gz',
                    'url': 'https://clob.polymarket.com/prices-history',
                    'params': {'market': token, 'startTs': left, 'endTs': right, 'fidelity': 1},
                    'start_at': left, 'end_at': right})
    return identities, jobs


def inspect_response(job, env):
    if env.get('status') != 200 or env.get('params') != job['params'] or env.get('url') != job['url']:
        raise ValueError('unsuccessful_or_mismatched_history_response')
    key = 'candlesticks' if job['venue'] == 'kalshi' else 'history'
    rows = env['payload'].get(key)
    if not isinstance(rows, list):
        raise ValueError('invalid_history_row_container')
    if job['venue'] == 'kalshi' and env['payload'].get('ticker', job['identity']) != job['identity']:
        raise ValueError('historical_candle_ticker_mismatch')
    stamps = [float(row['end_period_ts'] if job['venue'] == 'kalshi' else row['t']) for row in rows]
    if any(t > job['end_at'] for t in stamps):
        raise ValueError('history_contains_later_than_requested_timestamp')
    return {'rows': len(rows), 'first_source_timestamp': min(stamps) if stamps else None,
            'last_source_timestamp': max(stamps) if stamps else None,
            'query_coverage_complete': True, 'contains_price_states': bool(rows)}


class ArchiveClient:
    def __init__(self, out, max_requests):
        self.out, self.max_requests = out, max_requests
        self.lock = threading.Lock()
        self.attempt_path = out / 'attempts.jsonl'
        self.count = sum(1 for line in self.attempt_path.open() if line.strip()) if self.attempt_path.exists() else 0

    def get(self, job):
        path = self.out / job['file']
        if path.exists():
            with gzip.open(path, 'rt') as handle:
                env = json.load(handle)
            details = inspect_response(job, env)
            return {**job, **details, 'status': 200, 'sha256': digest(path), 'cached': True}
        for attempt in range(4):
            with self.lock:
                if self.count >= self.max_requests:
                    return {**job, 'status': None, 'reason': 'persistent_public_request_budget_exhausted'}
                self.count += 1
                with self.attempt_path.open('a') as handle:
                    handle.write(json.dumps({'at': time.time(), 'job': job['file'], 'url': job['url'], 'params': job['params']}) + '\n')
            pace()
            session = requests.Session()
            session.trust_env = False
            env = {'url': job['url'], 'params': job['params'], 'request_started_at': time.time(), 'status': None}
            try:
                response = session.get(job['url'], params=job['params'], timeout=45, allow_redirects=False)
                env.update(status=response.status_code, response_sha256=hashlib.sha256(response.content).hexdigest(),
                           payload=response.json(), retrieved_at=time.time())
            except (requests.RequestException, ValueError):
                env.update(error='public_history_transport_or_JSON_failure', retrieved_at=time.time())
            finally:
                session.close()
            if env['status'] == 200:
                details = inspect_response(job, env)
                save(path, env)
                return {**job, **details, 'status': 200, 'sha256': digest(path), 'cached': False}
            save(self.out / 'failures' / (str(time.time_ns()) + '.json.gz'), env)
            if env['status'] is not None and env['status'] < 500 and env['status'] != 429:
                break
            time.sleep(min(8, 2 ** attempt))
        return {**job, 'status': env['status'], 'reason': 'history_request_failed'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--review', type=Path, required=True)
    parser.add_argument('--schedule', type=Path, default=ROOT / 'config/nfl_playoffs_history_2026.json')
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--max-public-requests', type=int, default=800)
    parser.add_argument('--workers', type=int, default=2)
    args = parser.parse_args()
    if not 1 <= args.max_public_requests <= 800 or not 1 <= args.workers <= 2:
        raise ValueError('invalid_bounded_history_request_budget_or_workers')
    review, schedule = json.loads(args.review.read_text()), json.loads(args.schedule.read_text())
    identities, jobs = plan_jobs(review, schedule)
    args.out.mkdir(parents=True, exist_ok=True)
    plan = {'schema_version': 1, 'sport': 'NFL', 'family_scope': 'full_game_moneyline_only',
            'identities': identities, 'jobs': jobs, 'input_sha256': {str(p): digest(p) for p in (args.review, args.schedule)},
            'code_sha256': {str(p): digest(p) for p in (Path(__file__), ROOT / 'scripts/rate_limit.py')},
            'maximum_public_requests_across_resumes': args.max_public_requests, 'orders_enabled': False,
            'fees': 'Native January market metadata retained; effective-date fee model not yet verified',
            'clock_basis': 'Raw exchange timestamps retained; no availability time inferred from September retrieval time',
            'causal_replay_policy': 'Only prior observations within successful request coverage; conservative sixty-second publication allowance is a model assumption',
            'missing_seed_behavior': 'Unavailable until first past state; never insert a later price into an earlier decision',
            'other_markets': 'Exact spread/total history deferred to candidate-leg union after complete native cohort collection'}
    plan_path = args.out / 'plan.json'
    if plan_path.exists() and json.loads(plan_path.read_text()) != plan:
        raise ValueError('frozen_NFL_history_plan_changed')
    save(plan_path, plan)
    if not args.execute:
        print(json.dumps({'moneyline_identities': len(identities), 'history_jobs': len(jobs), 'executed': False}))
        return
    with (args.out / '.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        client = ArchiveClient(args.out, args.max_public_requests)
        state = {'status': 'running', 'pid': os.getpid(), 'started_at': time.time(), 'total_jobs': len(jobs), 'results': []}
        save(args.out / 'progress.json', state)
        try:
            with ThreadPoolExecutor(max_workers=args.workers) as pool:
                futures = [pool.submit(client.get, job) for job in jobs]
                for future in as_completed(futures):
                    state['results'].append(future.result())
                    state.update(completed_jobs=len(state['results']), public_attempts=client.count, updated_at=time.time())
                    save(args.out / 'progress.json', state)
            success = len(state['results']) == len(jobs) and all(r['status'] == 200 for r in state['results'])
            state.update(status='complete' if success else 'incomplete', completed_at=time.time(),
                         full_requested_query_coverage=success, nonempty_jobs=sum(r.get('rows', 0) > 0 for r in state['results']))
            save(args.out / 'coverage.json', {**state, 'plan_sha256': digest(plan_path),
                 'coverage_interpretation': 'Successful bounded queries, including empty pre-listing windows; not proof of a price at every decision time',
                 'net_PnL_or_live_pricing_ready': False})
        except Exception as exc:
            state.update(status='failed', error=str(exc), error_type=type(exc).__name__)
            raise
        finally:
            state.update(public_attempts=client.count, updated_at=time.time())
            save(args.out / 'progress.json', state)
    print(json.dumps({key: state.get(key) for key in ('status', 'completed_jobs', 'public_attempts', 'nonempty_jobs')}))


if __name__ == '__main__':
    main()

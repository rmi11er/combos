#!/usr/bin/env python3
"""Resume full-cohort exchange history capture without sampling fixtures or legs.

Additional Kalshi-only legs may be supplied using --kalshi-only: a JSON list of
{ticker, start_time} objects, a {tickers: [...]} object, or ticker→metadata mapping.
start_time (or startTime) is the game kickoff; strings alone capture the full week.
"""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
import gzip
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time

import requests
from rate_limit import pace

ROOT = Path(__file__).resolve().parents[1]
START = 1788152400
END = 1788757200


def timestamp(value):
    return int(datetime.fromisoformat(value.replace('Z', '+00:00')).timestamp()) if isinstance(value, str) else int(value)


def atomic_json(path, record, compressed=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=path.name + '.', suffix='.tmp', dir=path.parent)
    os.close(fd)
    try:
        opener = gzip.open if compressed else open
        with opener(temporary, 'wt') as stream:
            json.dump(record, stream, separators=(',', ':') if compressed else None, indent=None if compressed else 2)
            stream.write('\n')
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


@dataclass(frozen=True)
class Job:
    venue: str
    key: str
    url: str
    params: dict

    @property
    def filename(self):
        return self.key + '.json.gz'


def valid_record(record, job):
    if record.get('status') != 200 or record.get('params') != job.params:
        return False
    payload = record.get('payload')
    field = 'candlesticks' if job.venue == 'kalshi_parts' else 'history'
    return isinstance(payload, dict) and isinstance(payload.get(field), list)


def read_cache(path, job):
    try:
        with gzip.open(path, 'rt') as stream:
            record = json.load(stream)
        return record if valid_record(record, job) else None
    except (OSError, ValueError, EOFError):
        return None


def fetch(job, output, reuse, attempts):
    path = output / job.venue / job.filename
    base = {'venue': job.venue, 'key': job.key, 'params': job.params}
    existing = read_cache(path, job)
    if existing is not None:
        return dict(base, status=200, cached=True, source=str(path))
    for directory in reuse:
        candidate = directory / job.venue / job.filename
        record = read_cache(candidate, job)
        if record is not None:
            # Copy parsed data atomically so a killed collector never creates a
            # successful-looking truncated gzip; retain original retrieval time.
            atomic_json(path, record, compressed=True)
            return dict(base, status=200, cached=True, source=str(candidate))
    last = None
    for attempt in range(attempts):
        if job.venue == 'kalshi_parts':
            pace()
        try:
            response = requests.get(job.url, params=job.params, timeout=(10, 45))
            try:
                payload = response.json()
            except ValueError:
                payload = {'invalid_json': True, 'response_excerpt': response.text[:250]}
            record = {'url': response.url, 'status': response.status_code,
                      'retrieved_at': time.time(), 'params': job.params, 'payload': payload}
            atomic_json(path, record, compressed=True)
            if valid_record(record, job):
                field = 'candlesticks' if job.venue == 'kalshi_parts' else 'history'
                return dict(base, status=200, cached=False, rows=len(payload[field]), attempts=attempt + 1)
            last = dict(base, status=response.status_code, error='http_error' if response.status_code != 200 else 'invalid_payload', attempts=attempt + 1)
            if response.status_code not in (429, 408) and response.status_code < 500:
                return last
            delay = min(30, 2 ** (attempt + 1))
            if response.status_code == 429:
                try:
                    delay = min(30, max(delay, float(response.headers.get('Retry-After', 0))))
                except ValueError:
                    pass
        except requests.RequestException as exc:
            last = dict(base, error='transport', exception_type=type(exc).__name__, attempts=attempt + 1)
            delay = min(30, 2 ** (attempt + 1))
        if attempt + 1 < attempts:
            time.sleep(delay)
    return last


def additional_tickers(path, end):
    if path is None:
        return {}
    data = json.loads(path.read_text())
    if isinstance(data, dict) and 'tickers' in data:
        data = data['tickers']
    if isinstance(data, dict):
        data = [dict(v, ticker=k) if isinstance(v, dict) else {'ticker': k, 'start_time': v} for k, v in data.items()]
    result = {}
    for row in data:
        if isinstance(row, str):
            result[row] = None
        else:
            result[row.get('ticker', row.get('market_ticker'))] = timestamp(row.get('start_time', row.get('startTime', end)))
    if None in result:
        raise ValueError('Additional ticker object lacks ticker or market_ticker')
    return result


def build_jobs(selection, mappings, start, end, extra=None):
    tickers = {}
    tokens = set()
    for item in selection['selected']:
        kickoff = timestamp(item['fixture']['startTime'])
        for ticker in item['kalshi_tickers']:
            if ticker in tickers and tickers[ticker] != kickoff:
                raise ValueError('Conflicting fixture start times for ' + ticker)
            tickers[ticker] = kickoff
            mapping = mappings.get(ticker, {})
            if mapping.get('status') == 'matched' and mapping.get('token'):
                tokens.add(str(mapping['token']))
    for ticker, kickoff in (extra or {}).items():
        if kickoff is None:
            kickoff = tickers.get(ticker, end)
        if ticker in tickers and tickers[ticker] != kickoff:
            raise ValueError('Additional ticker has conflicting kickoff: ' + ticker)
        tickers[ticker] = kickoff
    jobs = []
    for ticker, kickoff in sorted(tickers.items()):
        cutoff = min(end, kickoff)
        for part, lo in enumerate(range(start, cutoff, 3 * 86400)):
            jobs.append(Job('kalshi_parts', ticker + '.part' + str(part),
                'https://external-api.kalshi.com/trade-api/v2/series/' + ticker.split('-')[0] + '/markets/' + ticker + '/candlesticks',
                {'start_ts': lo, 'end_ts': min(lo + 3 * 86400, cutoff), 'period_interval': 1, 'include_latest_before_start': 'true'}))
    for token in sorted(tokens):
        jobs.append(Job('polymarket', token, 'https://clob.polymarket.com/prices-history',
                        {'market': token, 'startTs': start, 'endTs': end, 'fidelity': 1}))
    return jobs, tickers, tokens


def build_window_jobs(rows, start, end, merge_gap_seconds=120):
    """Capture supplied decision gaps, merging nearby spans and limiting chunk size.

    The caller supplies its causal lookback (normally first decision minus 120s).
    include_latest_before_start also requests the preceding published candle.
    """
    if isinstance(rows, dict):
        rows = rows['windows']
    by_ticker = {}
    for row in rows:
        ticker = row.get('ticker', row.get('market_ticker'))
        lo, hi = int(row['start_ts']), int(row['end_ts'])
        if not ticker or lo >= hi:
            raise ValueError('Each gap needs a ticker and start_ts < end_ts')
        lo, hi = max(start, lo), min(end, hi)
        if lo < hi:
            by_ticker.setdefault(ticker, []).append((lo, hi))
    jobs = []
    for ticker, windows in sorted(by_ticker.items()):
        merged = []
        for lo, hi in sorted(windows):
            if merged and lo <= merged[-1][1] + merge_gap_seconds:
                merged[-1] = (merged[-1][0], max(merged[-1][1], hi))
            else:
                merged.append((lo, hi))
        for lo, hi in merged:
            for chunk_start in range(lo, hi, 3 * 86400):
                chunk_end = min(chunk_start + 3 * 86400, hi)
                jobs.append(Job('kalshi_parts', f'{ticker}.gap{chunk_start}-{chunk_end}',
                    'https://external-api.kalshi.com/trade-api/v2/series/' + ticker.split('-')[0] + '/markets/' + ticker + '/candlesticks',
                    {'start_ts': chunk_start, 'end_ts': chunk_end, 'period_interval': 1,
                     'include_latest_before_start': 'true'}))
    return jobs, by_ticker


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-run', type=Path, default=ROOT / 'runs/cfb_full_week_20260907')
    parser.add_argument('--selection', type=Path)
    parser.add_argument('--pm-mapping', type=Path, default=ROOT / 'data/derived/polymarket_mapping.json')
    parser.add_argument('--kalshi-only', type=Path)
    parser.add_argument('--kalshi-windows', type=Path,
                        help='Capture only this JSON list of {ticker,start_ts,end_ts} gaps, instead of selection jobs')
    parser.add_argument('--report-name', help='Optional JSON report filename within --data-run, for separate gap cohorts')
    parser.add_argument('--reuse-run', type=Path, action='append', default=[])
    parser.add_argument('--start-ts', type=int, default=START)
    parser.add_argument('--end-ts', type=int, default=END)
    parser.add_argument('--workers', type=int, default=6)
    parser.add_argument('--attempts', type=int, default=4)
    parser.add_argument('--plan-only', action='store_true')
    args = parser.parse_args()
    if not 1 <= args.workers <= 6 or args.attempts < 1 or args.start_ts >= args.end_ts:
        parser.error('Require 1–6 workers, positive attempts, and start before end')
    if args.report_name and (Path(args.report_name).name != args.report_name or not args.report_name.endswith('.json')):
        parser.error('--report-name must be a JSON filename without directories')
    selection_path = args.selection or args.data_run / 'selection.json'
    if args.kalshi_windows:
        if args.kalshi_only:
            parser.error('--kalshi-windows is exclusive with --kalshi-only')
        jobs, tickers = build_window_jobs(json.loads(args.kalshi_windows.read_text()), args.start_ts, args.end_ts)
        tokens = set()
        selection = {'selected': []}
    else:
        selection = json.loads(selection_path.read_text())
        mappings = json.loads(args.pm_mapping.read_text())
        jobs, tickers, tokens = build_jobs(selection, mappings, args.start_ts, args.end_ts,
                                         additional_tickers(args.kalshi_only, args.end_ts))
    reuse = [ROOT / 'runs/cfb_fair_pilot_20260907', *args.reuse_run]
    report = {'schema_version': 1, 'started_at': time.time(), 'selection': str(selection_path),
              'selection_sha256': hashlib.sha256(selection_path.read_bytes()).hexdigest() if not args.kalshi_windows else None,
              'mapping_sha256': hashlib.sha256(args.pm_mapping.read_bytes()).hexdigest() if not args.kalshi_windows else None,
              'window': {'start_ts': args.start_ts, 'end_ts': args.end_ts},
              'selected_fixtures': len(selection['selected']), 'kalshi_tickers': len(tickers),
              'polymarket_tokens': len(tokens), 'jobs': len(jobs), 'workers': args.workers,
              'sampling': 'none; every supplied ticker and exact requested candle interval',
              'coverage_note': 'HTTP/schema success confirms requested interval capture, not continuous traded prices or order-book depth.',
              'results': []}
    if args.kalshi_windows:
        report.update(selection=None, window_file=str(args.kalshi_windows),
                      window_file_sha256=hashlib.sha256(args.kalshi_windows.read_bytes()).hexdigest(),
                      sampling='none within supplied decision-gap windows; nearby gaps merged at <=120s')
    print(json.dumps({k: v for k, v in report.items() if k != 'results'}), flush=True)
    if args.plan_only:
        return
    report_path = args.data_run / (args.report_name or ('exchange_window_acquisition.json' if args.kalshi_windows else 'exchange_acquisition.json'))
    atomic_json(report_path, report)
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(fetch, job, args.data_run, reuse, args.attempts): job for job in jobs}
        for future in as_completed(futures):
            job = futures[future]
            try:
                result = future.result()
            except Exception as exc:
                result = {'venue': job.venue, 'key': job.key, 'error': 'worker_failure', 'exception_type': type(exc).__name__}
            report['results'].append(result)
            completed = len(report['results'])
            if completed % 50 == 0:
                report['completed'] = completed
                report['failed'] = sum('error' in x for x in report['results'])
                atomic_json(report_path, report)
                print(json.dumps({'completed': completed, 'total': len(jobs), 'failed': report['failed']}), flush=True)
    report['finished_at'] = time.time()
    report['completed'] = len(report['results'])
    report['failed'] = sum('error' in x for x in report['results'])
    report['cached'] = sum(x.get('cached', False) for x in report['results'])
    report['status_counts'] = dict(Counter(str(x.get('status', 'transport')) for x in report['results']))
    report['results'].sort(key=lambda row: (row['venue'], row['key']))
    atomic_json(report_path, report)
    print(json.dumps({k: v for k, v in report.items() if k != 'results'}), flush=True)
    return 1 if report['failed'] else 0


if __name__ == '__main__':
    raise SystemExit(main())

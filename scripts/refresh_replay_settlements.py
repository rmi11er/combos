#!/usr/bin/env python3
"""Refresh unresolved combo outcomes without repricing or modifying old evidence."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import gzip
import hashlib
import json
import math
from pathlib import Path
import time

import requests
from rate_limit import pace

ROOT = Path(__file__).resolve().parents[1]


def read_gz(path):
    with gzip.open(path, 'rt') as f:
        return json.load(f)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-run', type=Path, default=ROOT/'runs/cfb_full_week_20260907')
    parser.add_argument('--source', type=Path)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--max-requests', type=int, default=30)
    args = parser.parse_args(); source = args.source or args.data_run/'replay'
    out = args.out or args.data_run/'replay_settlement_refreshed'
    out.mkdir(parents=True, exist_ok=True); rawdir = out/'raw'; rawdir.mkdir(exist_ok=True)
    cohort_path = args.data_run/'cohort/combo_cohort.json.gz'; cohort = read_gz(cohort_path)
    unknown = sorted(t for t,m in cohort['markets'].items() if not m.get('settlement_ts'))
    records = {}; failures = []; new_requests = 0; session = requests.Session(); session.trust_env = False
    for offset in range(0, len(unknown), 100):
        batch = unknown[offset:offset+100]; digest = hashlib.sha256(','.join(batch).encode()).hexdigest()
        dest = rawdir/(digest+'.json.gz')
        env = read_gz(dest) if dest.exists() else None
        for attempt in range(4):
            if env and env.get('status') == 200 and isinstance(env.get('payload', {}).get('markets'), list):
                break
            if new_requests >= args.max_requests:
                break
            if attempt:
                time.sleep(min(8, 2**attempt))
            pace(); new_requests += 1
            query = {'tickers': ','.join(batch), 'limit': 1000}
            env = {'requested': batch, 'request_started_at': time.time(), 'params': query}
            try:
                r = session.get('https://external-api.kalshi.com/trade-api/v2/markets', params=query,
                                timeout=30, allow_redirects=False)
                env.update(url=r.url, status=r.status_code, retrieved_at=time.time(),
                           response_sha256=hashlib.sha256(r.content).hexdigest())
                try: env['payload'] = r.json()
                except ValueError: env['payload'] = {'invalid_json': True}
            except requests.RequestException as exc:
                env.update(status=None, error=type(exc).__name__, retrieved_at=time.time())
            if dest.exists():
                dest.rename(rawdir/(digest+'.attempt'+str(time.time_ns())+'.json.gz'))
            with gzip.open(dest, 'wt') as f:
                json.dump(env, f, separators=(',', ':'))
        if not env or env.get('status') != 200 or env.get('payload', {}).get('cursor'):
            failures.extend(batch); continue
        for market in env['payload'].get('markets', []):
            if market['ticker'] not in batch:
                raise ValueError('unexpected returned ticker')
            records[market['ticker']] = market
        failures.extend(t for t in batch if t not in records)
        print(json.dumps({'batch': offset//100+1, 'requested': min(offset+100, len(unknown)),
                          'markets_returned': len(records), 'new_GETs': new_requests}), flush=True)
    session.close()
    outcomes = {}
    for ticker, market in records.items():
        if market.get('settlement_ts'):
            at = datetime.fromisoformat(market['settlement_ts'].replace('Z', '+00:00')).timestamp()
            value = float(market['settlement_value_dollars'])
            if not math.isfinite(at) or not math.isfinite(value) or not 0 <= value <= 1:
                raise ValueError('invalid settlement metadata')
            outcomes[ticker] = (at, value)
    source_names = ('opportunities.json', 'common_opportunities.json')
    provenance = {'operation': 'update unresolved native combo settlements only; all forecasts and trade terms frozen',
                  'source_sha256': {name: sha(source/name) for name in source_names},
                  'cohort_sha256': sha(cohort_path), 'raw_sha256': {p.name: sha(p) for p in sorted(rawdir.glob('*.gz'))},
                  'script_sha256': sha(Path(__file__)), 'requested_unresolved_combos': len(unknown),
                  'newly_settled_combos': len(outcomes)}
    identifier = hashlib.sha256(json.dumps(provenance, sort_keys=True).encode()).hexdigest()[:12]
    exports = {}
    for name in source_names:
        payload = json.loads((source/name).read_text()); before = Counter(); updated = Counter(); after = Counter()
        for row in payload['opportunities']:
            model = row['model']; ticker = row['source_context']['combo_ticker']
            if row.get('settled_at') is None:
                before[model] += 1
                if ticker in outcomes:
                    at, value = outcomes[ticker]
                    if at <= row['at']:
                        raise ValueError('native settlement is not after decision: '+ticker)
                    row.update(settled_at=at, yes_settlement=value); updated[model] += 1
                else:
                    after[model] += 1
        payload['identity'] = {**payload['identity'], 'settlement_refresh': provenance}
        payload['run_id'] += ':settlements:'+identifier
        payload['display_name'] += ' — refreshed settlements'
        (out/name).write_text(json.dumps(payload, separators=(',', ':'), allow_nan=False)+'\n')
        exports[name] = {'previously_unresolved_rows': dict(before), 'newly_resolved_rows': dict(updated),
                         'still_unresolved_rows': dict(after), 'evaluations_unchanged': len(payload['opportunities'])}
    (out/'settlement_snapshot.json').write_text(json.dumps(records, separators=(',', ':'))+'\n')
    report = {**provenance, 'new_GET_attempts': new_requests, 'records_returned': len(records),
              'remaining_unknown_combos': len(unknown)-len(outcomes), 'request_failures': failures,
              'exports': exports, 'finished_at': datetime.now(timezone.utc).isoformat()}
    (out/'refresh_summary.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ('raw_sha256','source_sha256')}, indent=2))


if __name__ == '__main__':
    main()

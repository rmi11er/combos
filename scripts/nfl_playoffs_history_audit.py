#!/usr/bin/env python3
"""Offline, hash-checked NFL source-state audit; no fee or profitability claims."""
import argparse
from collections import Counter, defaultdict
import gzip
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from combos.kalshi_history import KalshiHistory
from nfl_playoffs_exchange_history import digest, inspect_response, save


def audit(directory):
    plan_path, coverage_path = directory / 'plan.json', directory / 'coverage.json'
    plan, coverage = json.loads(plan_path.read_text()), json.loads(coverage_path.read_text())
    if plan.get('sport') != 'NFL' or coverage.get('plan_sha256') != digest(plan_path):
        raise ValueError('unverified_NFL_history_plan')
    results = {row['file']: row for row in coverage['results']}
    if len(results) != len(plan['jobs']) or not coverage.get('full_requested_query_coverage'):
        raise ValueError('incomplete_history_queries')
    venues = defaultdict(lambda: {'jobs': 0, 'raw_rows': 0, 'nonempty_jobs': 0})
    pm = defaultdict(dict)
    raw_hashes = {}
    for job in plan['jobs']:
        path = directory / job['file']
        expected = results[job['file']]['sha256']
        if digest(path) != expected:
            raise ValueError('history_capture_hash_mismatch')
        raw_hashes[job['file']] = expected
        with gzip.open(path, 'rt') as handle:
            env = json.load(handle)
        details = inspect_response(job, env)
        venue = venues[job['venue']]
        venue['jobs'] += 1
        venue['raw_rows'] += details['rows']
        venue['nonempty_jobs'] += details['rows'] > 0
        if job['venue'] == 'polymarket':
            for row in env['payload']['history']:
                at, price = float(row['t']), float(row['p'])
                if not math.isfinite(at) or not math.isfinite(price) or not 0 <= price <= 1:
                    raise ValueError('invalid_polymarket_history_point')
                if not job['start_at'] <= at <= job['end_at']:
                    raise ValueError('polymarket_point_outside_request_bounds')
                old = pm[job['identity']].get(at)
                if old is not None and old != price:
                    raise ValueError('conflicting_polymarket_point')
                pm[job['identity']][at] = price
    # Loading states alone does not apply a fee assumption. In particular, do
    # not call at(), whose interval requires an effective-date taker fee.
    history = KalshiHistory(directory, fallback_dirs=[])
    identities = []
    for mapping in plan['identities']:
        ticker, token = mapping['kalshi_ticker'], mapping['polymarket_token']
        loaded = history.load(ticker)
        valid, missing, invalid = [], 0, 0
        parse_errors = Counter()
        for source in loaded['sources']:
            parse_errors.update(source['quote_parse_errors'])
        for segment in loaded['segments']:
            for at, bid, ask in zip(segment['times'], segment['bids'], segment['asks']):
                if not math.isfinite(bid) or not math.isfinite(ask):
                    missing += 1
                elif not 0 <= bid <= ask <= 1:
                    invalid += 1
                else:
                    valid.append(at)
        pm_times = sorted(pm[token])
        identities.append({'kalshi_ticker': ticker, 'polymarket_token': token,
            'target_start_at': mapping['target_start_at'], 'capture_end_at': mapping['capture_end_at'],
            'kalshi': {'valid_unique_book_states': len(valid), 'missing_quote_states': missing,
                'invalid_or_crossed_quote_states': invalid, 'parse_errors': dict(parse_errors),
                'first_source_at': min(valid) if valid else None, 'last_source_at': max(valid) if valid else None,
                'request_intervals': [[s['lo'], s['hi']] for s in loaded['segments']]},
            'polymarket': {'valid_unique_price_points': len(pm_times),
                'first_source_at': pm_times[0] if pm_times else None, 'last_source_at': pm_times[-1] if pm_times else None}})
    venues['kalshi']['identities_with_valid_states'] = sum(row['kalshi']['valid_unique_book_states'] > 0 for row in identities)
    venues['kalshi']['valid_unique_book_states'] = sum(row['kalshi']['valid_unique_book_states'] for row in identities)
    venues['kalshi']['missing_quote_states'] = sum(row['kalshi']['missing_quote_states'] for row in identities)
    venues['kalshi']['invalid_or_crossed_quote_states'] = sum(row['kalshi']['invalid_or_crossed_quote_states'] for row in identities)
    venues['polymarket']['identities_with_valid_states'] = sum(row['polymarket']['valid_unique_price_points'] > 0 for row in identities)
    venues['polymarket']['valid_unique_price_points'] = sum(row['polymarket']['valid_unique_price_points'] for row in identities)
    return {'sport': 'NFL', 'family_scope': 'fullgame_moneyline_only', 'complete_query_coverage': True,
        'venues': dict(venues), 'identities': identities, 'public_attempts': coverage['public_attempts'],
        'input_sha256': {str(plan_path): digest(plan_path), str(coverage_path): digest(coverage_path)},
        'raw_capture_sha256': raw_hashes,
        'audit_code_sha256': {str(p): digest(p) for p in (Path(__file__), ROOT / 'src/combos/kalshi_history.py')},
        'clock_policy': 'Only prior states within successful query intervals; a 60-second publication allowance is a replay assumption, not observed source latency.',
        'coverage_caveat': 'Complete queries include empty pre-listing windows. Source availability must still be checked separately at each trade timestamp.',
        'fee_model_applied': False, 'source_data_only_not_net_pnl': True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    result = audit(args.input)
    save(args.out or args.input / 'availability_review.json', result)
    print(json.dumps({'venues': result['venues'], 'source_data_only_not_net_pnl': True}))


if __name__ == '__main__':
    main()

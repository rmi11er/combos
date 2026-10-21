#!/usr/bin/env python3
"""Acquire all cached CFB fixtures with exact exchange mappings; no sample cap."""
import argparse
from collections import Counter, defaultdict
from datetime import datetime
import fcntl
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import time
import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from combos.matching import norm
from combos.football_identity import provider_team_key, provider_team_identity
from combos.oddspapi import OddsPapi
from oddspapi_baseball_history import scrub, write_json, history_summary, account_counters, counter_delta


def build_selection(fixtures, mappings):
    by = defaultdict(set)
    for ticker, row in mappings.items():
        if row.get('status') == 'matched':
            start = datetime.fromisoformat(row['start_time'].replace('Z', '+00:00'))
            by[(tuple(sorted(row['teams'])), start)].add(ticker)
    selected, excluded = [], []
    seen = set()
    for fixture in fixtures:
        fid = fixture['fixtureId']
        if fid in seen:
            raise ValueError('duplicate fixture ID in discovery')
        seen.add(fid)
        teams = tuple(sorted(provider_team_key(fixture, i) for i in (1, 2)))
        start = datetime.fromisoformat(fixture['startTime'].replace('Z', '+00:00'))
        tickers = sorted(by.get((teams, start), []))
        if tickers:
            selected.append({'fixture': fixture, 'kalshi_tickers': tickers,
                             'provider_team_identities': [provider_team_identity(fixture, i) for i in (1, 2)]})
        else:
            excluded.append({'fixture_id': fid, 'reason': 'no_exact_existing_exchange_fixture_mapping',
                             'teams': teams, 'start_time': fixture['startTime']})
    selected.sort(key=lambda row: (row['fixture']['startTime'], row['fixture']['fixtureId']))
    selected_tickers = {t for row in selected for t in row['kalshi_tickers']}
    fixture_teams = defaultdict(list)
    for fixture in fixtures:
        teams = tuple(sorted(provider_team_key(fixture, i) for i in (1, 2)))
        fixture_teams[teams].append({'fixture_id': fixture['fixtureId'], 'start_time': fixture['startTime']})
    unjoined = []
    for ticker, row in mappings.items():
        if row.get('status') != 'matched' or ticker in selected_tickers:
            continue
        candidates = fixture_teams.get(tuple(sorted(row['teams'])), [])
        unjoined.append({'ticker': ticker, 'teams': row['teams'], 'mapping_start_time': row['start_time'],
                         'reason': 'fixture_start_time_disagreement' if candidates else 'no_exact_provider_team_pair',
                         'provider_team_pair_candidates': candidates})
    return {'selection': 'ALL cached fixtures with exact existing Kalshi/Polymarket team and start-time mapping; no minimum line count, hash sampling or fixture cap',
            'candidate_fixtures': len(selected), 'selected': selected, 'excluded_fixtures': excluded,
            'source_fixture_count': len(fixtures),
            'unjoined_exchange_mappings': unjoined,
            'mapped_tickers': len({t for row in selected for t in row['kalshi_tickers']}),
            'cohort_limitation': 'Complete among supplied exact exchange mappings, not all week-wide exchange markets; mapping coverage is separately reported'}


class Acquirer:
    def __init__(self, out, key, max_requests):
        self.out, self.key, self.max_requests = out, key, max_requests
        self.session = requests.Session(); self.previous = 0.; self.attempts = []
        (out / 'raw').mkdir(exist_ok=True)

    def get_once(self, endpoint, params=None):
        if len(self.attempts) >= self.max_requests:
            raise ValueError('declared acquisition request bound reached')
        if endpoint not in ('account', 'historical-odds', 'fixtures'):
            raise ValueError('unexpected acquisition endpoint')
        time.sleep(max(0., 5.05 - (time.monotonic() - self.previous)))
        self.previous = time.monotonic()
        started = time.time(); params = params or {}
        envelope = {'request': {'endpoint': endpoint, 'params': params},
                    'request_started_at': started, 'http_status': None}
        item = {'endpoint': endpoint, 'params': params, 'started_at': started}
        self.attempts.append(item)
        write_json(self.out / 'request_attempts.json', self.attempts)
        try:
            response = self.session.get(OddsPapi.BASE + '/' + endpoint,
                params={**params, 'apiKey': self.key}, timeout=45, allow_redirects=False)
            envelope['http_status'] = response.status_code
            try:
                payload = response.json()
            except ValueError:
                payload = {'non_json_body': response.text}
            envelope['payload'] = scrub(payload, self.key)
        except requests.RequestException:
            envelope['transport_error'] = 'transport failure; private request details suppressed'
        envelope['retrieved_at'] = time.time()
        self.previous = time.monotonic()  # Pace from completion: server-side latency can exceed the 50ms margin.
        filename = f'{time.time_ns()}_{endpoint}.json.gz'
        with gzip.open(self.out / 'raw' / filename, 'wt') as f:
            json.dump(envelope, f, separators=(',', ':'))
        item.update(http_status=envelope['http_status'], file='raw/' + filename)
        write_json(self.out / 'request_attempts.json', self.attempts)
        return envelope

    def get(self, endpoint, params=None):
        for _ in range(3):
            envelope = self.get_once(endpoint, params)
            status = envelope['http_status']
            if status is not None and status != 429 and status < 500:
                return envelope
        return envelope


def extend_fixtures(args, prior, key):
    """One discovery call: tournament filter permits a date span above ten days."""
    capture = args.out / f'fixture_extension_{time.time_ns()}'
    capture.mkdir()
    client = Acquirer(capture, key, 3)
    time.sleep(5.05)
    before = client.get_once('account')
    env = client.get_once('fixtures', {'sportId': 14, 'tournamentId': 27653,
        'from': args.extend_fixtures_from + 'T00:00:00Z',
        'to': args.extend_fixtures_through + 'T00:00:00Z', 'language': 'en'})
    after = client.get_once('account')
    extension_report = {'http_status': env['http_status'], 'request_counter_delta': counter_delta(
        account_counters(before.get('payload')), account_counters(after.get('payload')))}
    write_json(capture / 'summary.json', extension_report)
    if env['http_status'] != 200 or not isinstance(env.get('payload'), list):
        raise ValueError('additional fixture discovery failed; redacted evidence retained')
    merged = {row['fixtureId']: row for row in prior['payload']}
    conflicts = []
    for row in env['payload']:
        if row.get('sportId') != 14 or row.get('tournamentId') != 27653:
            raise ValueError('fixture extension contains unexpected sport or tournament')
        fid = row['fixtureId']; old = merged.get(fid)
        if old is not None and old != row:
            def updated(value):
                try:
                    return datetime.fromisoformat(value.get('updatedAt', '').replace('Z', '+00:00')).timestamp()
                except ValueError:
                    return float('-inf')
            use_new = updated(row) >= updated(old)
            conflicts.append({'fixture_id': fid, 'selected': 'extension' if use_new else 'prior',
                              'prior_updated_at': old.get('updatedAt'), 'extension_updated_at': row.get('updatedAt')})
            if not use_new:
                continue
        merged[fid] = row
    result = {**prior, 'payload': sorted(merged.values(), key=lambda row: (row['startTime'], row['fixtureId']))}
    result['extensions'] = prior.get('extensions', []) + [{'capture': str(capture),
        'request': env['request'], 'retrieved_at': env['retrieved_at'],
        'fixture_count': len(env['payload']), 'conflicts': conflicts}]
    write_json(args.out / 'fixtures.json', result)
    print(json.dumps({'extension_fixtures': len(env['payload']), 'merged_fixture_count': len(merged),
                      'conflicts': len(conflicts), 'capture': str(capture)}), flush=True)
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--key-file', type=Path)
    p.add_argument('--source', type=Path, default=ROOT / 'runs/cfb_fair_pilot_20260907')
    p.add_argument('--mapping', type=Path, default=ROOT / 'data/derived/polymarket_mapping.json')
    p.add_argument('--out', type=Path, default=ROOT / 'runs/cfb_full_week_20260907')
    p.add_argument('--plan-only', action='store_true')
    p.add_argument('--retry-unavailable', action='store_true', help='Retry archived404histories; otherwise retain explicit cached unavailability')
    p.add_argument('--extend-fixtures-from', default='2026-09-07')
    p.add_argument('--extend-fixtures-through', help='Optional final UTC date; one CFB fixture-discovery request')
    p.add_argument('--fixtures-only', action='store_true', help='Extend discovery then stop before rewriting selection')
    args = p.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    with (args.out / '.history_acquire.lock').open('a') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fixtures_path = args.out / 'fixtures.json'
        if not fixtures_path.exists():
            shutil.copy2(args.source / 'fixtures.json', fixtures_path)
        fixtures_envelope = json.loads(fixtures_path.read_text())
        if args.extend_fixtures_through:
            for value in (args.extend_fixtures_from, args.extend_fixtures_through):
                datetime.strptime(value, '%Y-%m-%d')
            if args.extend_fixtures_through <= args.extend_fixtures_from:
                raise ValueError('fixture extension end must follow start')
            key = args.key_file.read_text().strip() if args.key_file else os.getenv('ODDSPAPI_API_KEY', '').strip()
            if not key:
                raise ValueError('API key unavailable; no requests made')
            fixtures_envelope = extend_fixtures(args, fixtures_envelope, key)
        if args.fixtures_only:
            if not args.extend_fixtures_through:
                raise ValueError('fixtures-only requires an extension end')
            return 0
        mappings = json.loads(args.mapping.read_text())
        plan = build_selection(fixtures_envelope['payload'], mappings)
        plan['mapping_reference'] = str(args.mapping)
        plan['mapping_sha256'] = hashlib.sha256(args.mapping.read_bytes()).hexdigest()
        plan['fixtures_sha256'] = hashlib.sha256(fixtures_path.read_bytes()).hexdigest()
        write_json(args.out / 'selection.json', plan)
        (args.out / 'history').mkdir(exist_ok=True)
        print(json.dumps({'selected_fixtures': len(plan['selected']), 'mapped_tickers': plan['mapped_tickers'],
                          'excluded_fixtures': len(plan['excluded_fixtures'])}), flush=True)
        if args.plan_only:
            return 0
        key = args.key_file.read_text().strip() if args.key_file else os.getenv('ODDSPAPI_API_KEY', '').strip()
        if not key:
            raise ValueError('API key unavailable; no requests made')
        report = {'complete': False, 'history': [], 'errors': [], 'reused': 0,
                  'selection_reference': str(args.out / 'selection.json'),
                  'key_file_retained': bool(args.key_file)}
        previous_report = json.loads((args.out / 'acquisition.json').read_text()) if (args.out / 'acquisition.json').exists() else {}
        prior_unavailable = {row['fixture_id']: row for row in previous_report.get('errors', [])
                             if row.get('error', '').startswith('HTTP 404;')}
        report['reused_unavailable'] = 0
        missing = []
        for item in plan['selected']:
            fid = item['fixture']['fixtureId']; dest = args.out / 'history' / f'{fid}.json.gz'
            existing = dest if dest.exists() else args.source / 'history' / f'{fid}.json.gz'
            if existing.exists():
                try:
                    with gzip.open(existing, 'rt') as f:
                        envelope = json.load(f)
                    stats = history_summary(envelope['payload'], fid)
                    if stats['row_count'] <= 0:
                        raise ValueError('cached history empty')
                    if existing != dest:
                        shutil.copy2(existing, dest)
                    report['history'].append({'fixture_id': fid, 'source': 'cached', **stats})
                    report['reused'] += 1
                    continue
                except (ValueError, KeyError, TypeError, OSError):
                    report['errors'].append({'fixture_id': fid, 'stage': 'cache_validation',
                                             'error': 'invalid cache; attempting fresh history'})
            if fid in prior_unavailable and not args.retry_unavailable:
                report['errors'].append({'fixture_id': fid, 'stage': 'cached_unavailable',
                    'error': prior_unavailable[fid]['error'],
                    'source': 'prior acquisition; use --retry-unavailable to refresh'})
                report['reused_unavailable'] += 1
                continue
            missing.append(fid)
        report['missing_at_start'] = len(missing)
        for prior_name in ('acquisition.json', 'request_attempts.json'):
            prior = args.out / prior_name
            if prior.exists():
                archive_dir = args.out / 'acquisition_versions'
                archive_dir.mkdir(exist_ok=True)
                shutil.copy2(prior, archive_dir / f'{time.time_ns()}_{prior_name}')
        client = Acquirer(args.out, key, 3 * (len(missing) + 2))
        try:
            before = client.get('account')
            report['account_before'] = account_counters(before.get('payload')) if before['http_status'] == 200 else None
            for i, fid in enumerate(missing):
                env = client.get('historical-odds', {'fixtureId': fid, 'bookmakers': 'pinnacle+30'})
                try:
                    if env['http_status'] != 200:
                        raise ValueError(f'HTTP {env["http_status"]}; see redacted archive')
                    stats = history_summary(env['payload'], fid)
                    if not stats['row_count']:
                        raise ValueError('empty historical response')
                    with gzip.open(args.out / 'history' / f'{fid}.json.gz', 'wt') as f:
                        json.dump(env, f, separators=(',', ':'))
                    report['history'].append({'fixture_id': fid, 'source': 'downloaded', **stats})
                    message = {'fixture_id': fid, 'rows': stats['row_count']}
                except (ValueError, KeyError, TypeError, AttributeError) as exc:
                    error = str(exc) if isinstance(exc, ValueError) else 'historical response structure error'
                    report['errors'].append({'fixture_id': fid, 'stage': 'download', 'error': error})
                    message = {'fixture_id': fid, 'error': error}
                write_json(args.out / 'acquisition.json', report)
                print(json.dumps({**message, 'download_progress': f'{i + 1}/{len(missing)}'}), flush=True)
            report['complete'] = True
        finally:
            after = client.get('account')
            report['account_after'] = account_counters(after.get('payload')) if after['http_status'] == 200 else None
            report['request_counter_delta'] = counter_delta(report.get('account_before'), report['account_after'])
            report['requests_attempted'] = len(client.attempts)
            report['available_fixtures'] = len(report['history'])
            available_ids = {row['fixture_id'] for row in report['history']}
            report['selected_fixtures'] = len(plan['selected'])
            report['unavailable_fixture_ids'] = [row['fixture']['fixtureId'] for row in plan['selected']
                                                if row['fixture']['fixtureId'] not in available_ids]
            report['all_selected_have_history'] = not report['unavailable_fixture_ids']
            report['total_history_rows'] = sum(row['row_count'] for row in report['history'])
            write_json(args.out / 'acquisition.json', scrub(report, key))
        print(json.dumps({k: report[k] for k in ('complete', 'available_fixtures', 'reused', 'requests_attempted', 'request_counter_delta')}), flush=True)
        return 0 if report['complete'] else 1


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as exc:
        print(json.dumps({'error': str(exc) if isinstance(exc, ValueError) else type(exc).__name__}), file=sys.stderr)
        sys.exit(1)

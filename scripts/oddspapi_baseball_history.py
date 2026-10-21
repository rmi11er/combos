#!/usr/bin/env python3
"""Bounded, resumable read-only MLB history access probe (no live odds calls)."""
import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
import fcntl
import gzip
import json
import os
from pathlib import Path
import re
import sys
import time
from urllib.parse import quote, quote_plus

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from combos.oddspapi import OddsPapi, iter_history, redact_credentials

MAX_REQUESTS = 6
PACE_SECONDS = 5.05


def scrub(value, key):
    """Redact structured secrets and literal/URL-encoded echoes in any text."""
    variants = {key, quote(key, safe=''), quote_plus(key)}
    def walk(item):
        if isinstance(item, dict):
            return {walk(k): walk(v) for k, v in item.items()}
        if isinstance(item, list):
            return [walk(v) for v in item]
        if isinstance(item, str):
            for token in variants:
                if token:
                    item = item.replace(token, '[REDACTED]')
            return re.sub(r'(?i)(api[_-]?key|access[_-]?token|authorization)=([^&\s"<>]+)',
                          r'\1=[REDACTED]', item)
        return item
    return walk(redact_credentials(value))


def write_json(path, value):
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')
    temp.replace(path)


def history_summary(payload, fixture_id):
    if not isinstance(payload, dict) or payload.get('fixtureId') != fixture_id:
        raise ValueError('history fixture shape or identity mismatch')
    counts = Counter(); books = Counter(); stamps = []; missing_times = 0
    for row in iter_history(payload):
        snapshot = row['snapshot']
        if not isinstance(snapshot, dict):
            raise ValueError('history snapshot is not an object')
        active = snapshot.get('active')
        counts['active' if active is True else 'inactive' if active is False else 'unknown_activity'] += 1
        books[row['venue']] += 1
        try:
            dt = datetime.fromisoformat(snapshot['createdAt'].replace('Z', '+00:00'))
            if dt.tzinfo is None:
                raise ValueError('naive timestamp')
            stamps.append(dt.astimezone(timezone.utc))
        except (KeyError, TypeError, ValueError, AttributeError):
            missing_times += 1
    return {'row_count': sum(counts.values()), 'activity_counts': dict(counts),
            'rows_by_bookmaker': dict(books), 'missing_or_invalid_timestamps': missing_times,
            'earliest_created_at': min(stamps).isoformat() if stamps else None,
            'latest_created_at': max(stamps).isoformat() if stamps else None,
            'created_at_semantics': 'archive creation time; delayed availability not yet verified'}


def choose_fixture(payload):
    if not isinstance(payload, list):
        raise ValueError('fixture discovery is not an array')
    eligible = []
    for row in payload:
        if not isinstance(row, dict) or row.get('sportId') != 13 or row.get('statusId') != 2:
            continue
        labels = [re.sub(r'[^a-z0-9]', '', str(row.get(k, '')).lower())
                  for k in ('tournamentSlug', 'tournamentName')]
        if any(label in ('mlb', 'majorleaguebaseball', 'usamlb') for label in labels):
            if row.get('fixtureId'):
                eligible.append(row)
    if not eligible:
        raise ValueError('no completed MLB fixture in the bounded discovery window')
    return min(eligible, key=lambda row: (row.get('startTime', ''), str(row['fixtureId'])))


def account_counters(payload):
    if not isinstance(payload, dict):
        return None
    result = {}
    for row in payload.get('subscriptions', []):
        if not isinstance(row, dict):
            continue
        identity = row.get('subscription_id') or json.dumps(
            {k: row.get(k) for k in ('valid_from', 'sport_ids', 'bookmakers')}, sort_keys=True)
        result[str(identity)] = {k: row.get(k) for k in
            ('request_count', 'request_limit', 'sport_ids', 'bookmakers', 'is_active')}
    return result


def counter_delta(before, after):
    if before is None or after is None:
        return None
    result = {}
    for identity in sorted(set(before) | set(after)):
        a = before.get(identity, {}).get('request_count')
        b = after.get(identity, {}).get('request_count')
        result[identity] = b - a if isinstance(a, (int, float)) and isinstance(b, (int, float)) else None
    return result


class Probe:
    def __init__(self, out, key, config, session=None):
        self.out, self.key = Path(out), key
        self.out.mkdir(parents=True, exist_ok=True)
        self.state_path = self.out / 'probe_state.json'
        self.session = session or requests.Session()
        if self.state_path.exists():
            self.state = json.loads(self.state_path.read_text())
            if self.state['config'] != config:
                raise ValueError('existing probe configuration differs; use a new output directory')
        else:
            self.state = {'schema_version': 1, 'config': config, 'requests': []}
            write_json(self.state_path, self.state)

    def get(self, label, endpoint, params=None, fresh=False, reserve_after=True):
        if endpoint not in ('account', 'fixtures', 'historical-odds'):
            raise ValueError('probe endpoint is not allowed')
        params = dict(params or {})
        if any('key' in k.lower() or 'token' in k.lower() for k in params):
            raise ValueError('credential parameters are not allowed')
        prior = [r for r in self.state['requests'] if r['label'] == label]
        if prior and not fresh and prior[-1].get('file'):
            with gzip.open(self.out / prior[-1]['file'], 'rt') as f:
                cached = json.load(f)
            if cached['http_status'] is not None:
                return cached
        ceiling = MAX_REQUESTS - int(reserve_after)
        if len(self.state['requests']) >= ceiling:
            raise ValueError('bounded probe request ceiling reached')
        if self.state['requests']:
            elapsed = time.time() - self.state['requests'][-1]['started_at']
            time.sleep(max(0., PACE_SECONDS - elapsed))
        started = time.time()
        item = {'label': label, 'endpoint': endpoint, 'params': params, 'started_at': started}
        self.state['requests'].append(item)
        write_json(self.state_path, self.state)  # Count uncertain/failed attempts before sending.
        envelope = {'request': {'endpoint': endpoint, 'params': params},
                    'request_started_at': started, 'http_status': None}
        try:
            response = self.session.get(OddsPapi.BASE + '/' + endpoint,
                params={**params, 'apiKey': self.key}, timeout=25, allow_redirects=False)
            envelope['http_status'] = response.status_code
            try:
                payload = response.json()
            except ValueError:
                payload = {'non_json_body': response.text}
            envelope['payload'] = scrub(payload, self.key)
            envelope['response_headers'] = scrub({k: response.headers[k]
                for k in ('Date', 'Content-Type', 'Retry-After') if k in response.headers}, self.key)
        except requests.RequestException:
            envelope['transport_error'] = 'request failed; credential-bearing details suppressed'
        envelope['retrieved_at'] = time.time()
        envelope['elapsed_seconds'] = envelope['retrieved_at'] - started
        name = f'{len(self.state["requests"]):02d}_{label}.json.gz'
        temp = self.out / (name + '.tmp')
        with gzip.open(temp, 'wt') as f:
            json.dump(envelope, f, separators=(',', ':'), allow_nan=False)
        temp.replace(self.out / name)
        item.update(file=name, http_status=envelope['http_status'])
        write_json(self.state_path, self.state)
        print(json.dumps({'endpoint': endpoint, 'status': envelope['http_status'],
                          'requests_attempted': len(self.state['requests'])}), flush=True)
        return envelope


def run(probe):
    report = {'complete': False, 'historical_access': 'unverified', 'sport_id': 13,
              'history_attempts': [], 'subscription_precheck': 'not applied to history',
              'request_limit': MAX_REQUESTS, 'pace_seconds': PACE_SECONDS}
    before = after = None
    try:
        before_env = probe.get('account_before', 'account')
        before = account_counters(before_env.get('payload')) if before_env['http_status'] == 200 else None
        config = probe.state['config']
        fixture_id = config['fixture_id']
        if not fixture_id:
            start = datetime.fromisoformat(config['start']).replace(tzinfo=timezone.utc)
            env = probe.get('fixtures', 'fixtures', {'sportId': 13, 'statusId': 2,
                'from': start.isoformat().replace('+00:00', 'Z'),
                'to': (start + timedelta(days=1)).isoformat().replace('+00:00', 'Z'), 'language': 'en'})
            if env['http_status'] != 200:
                raise ValueError('fixture discovery unavailable; supply a native MLB fixture ID in a new probe')
            fixture = choose_fixture(env['payload'])
            fixture_id = fixture['fixtureId']
            report['fixture'] = fixture
        else:
            report['fixture'] = {'fixtureId': fixture_id, 'identity_source': 'caller supplied; MLB identity not independently checked'}
        for slug in ('pinnacle', 'pinnacle+30'):
            env = probe.get('history_' + slug.replace('+', '_'), 'historical-odds',
                            {'fixtureId': fixture_id, 'bookmakers': slug})
            result = {'requested_bookmaker': slug, 'http_status': env['http_status']}
            report['history_attempts'].append(result)
            if env['http_status'] == 200:
                try:
                    result.update(history_summary(env.get('payload'), fixture_id))
                except (ValueError, KeyError, TypeError, AttributeError):
                    result['parse_error'] = 'unexpected historical response structure; inspect redacted archive'
                if result.get('row_count', 0) > 0:
                    report['historical_access'] = 'confirmed_nonempty_history'
                    report['successful_bookmaker'] = slug
                    break
            # Explicitly probe +30 after a denied, empty or malformed undelayed response.
        report['complete'] = True
        if report['historical_access'] == 'unverified':
            report['historical_access'] = 'not_confirmed_by_this_fixture_probe'
    except (ValueError, OSError) as exc:
        report['error'] = str(exc) if isinstance(exc, ValueError) else type(exc).__name__
    finally:
        # Resume can retain a prior after snapshot only if nothing newer was requested.
        latest = probe.state['requests'][-1] if probe.state['requests'] else {}
        try:
            after_env = probe.get('account_after', 'account', fresh=latest.get('label') != 'account_after',
                                  reserve_after=False)
            after = account_counters(after_env.get('payload')) if after_env['http_status'] == 200 else None
        except (ValueError, OSError):
            report['account_after_error'] = 'after-counter unavailable within bounded request budget'
        report.update(account_before=before, account_after=after,
                      request_counter_delta=counter_delta(before, after),
                      counter_delta_caveat='account-wide change may include concurrent clients',
                      requests_attempted=len(probe.state['requests']), requests=probe.state['requests'])
        write_json(probe.out / 'summary.json', scrub(report, probe.key))
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--key-file', type=Path, help='Otherwise reads ODDSPAPI_API_KEY; never prints either')
    p.add_argument('--out', type=Path, required=True, help='Reusing the same directory resumes the same bounded probe')
    p.add_argument('--fixture-id', help='Optional native completed MLB fixture ID; avoids discovery')
    p.add_argument('--start', default='2026-07-01', help='UTC discovery date, YYYY-MM-DD; one day only')
    args = p.parse_args()
    try:
        start = datetime.strptime(args.start, '%Y-%m-%d').date().isoformat()
        key = args.key_file.read_text().strip() if args.key_file else os.getenv('ODDSPAPI_API_KEY', '').strip()
        if not key:
            raise ValueError('API key unavailable; no requests made')
        if args.fixture_id and not re.fullmatch(r'[A-Za-z0-9_-]+', args.fixture_id):
            raise ValueError('invalid fixture ID')
        args.out.mkdir(parents=True, exist_ok=True)
        with (args.out / '.probe.lock').open('a') as handle:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            probe = Probe(args.out, key, {'fixture_id': args.fixture_id, 'start': start})
            report = run(probe)
        print(json.dumps({k: report[k] for k in ('complete', 'historical_access', 'requests_attempted')}, indent=2))
        return 0 if report['historical_access'] == 'confirmed_nonempty_history' else 1
    except Exception as exc:
        # File/transport exceptions can carry private paths or credential URLs.
        print(json.dumps({'error': str(exc) if isinstance(exc, ValueError) else type(exc).__name__}), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())

#!/usr/bin/env python3
"""Bounded, redacted, resumable January NFL Pinnacle historical acquisition."""
import argparse
from collections import Counter
from datetime import datetime
import fcntl
import gzip
import hashlib
import json
from pathlib import Path
import re
import sys
import time
from zoneinfo import ZoneInfo

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from combos.oddspapi import OddsPapi, iter_history
from oddspapi_baseball_history import account_counters, counter_delta, history_summary, scrub, write_json


def stamp(value):
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('timezone_required')
    return parsed.timestamp()


def normalized(value):
    return re.sub('[^a-z0-9]', '', value.lower())


def match_fixtures(schedule, rows):
    matched = []
    for fixture in schedule['fixtures']:
        names = {normalized(fixture['home']), normalized(fixture['away'])}
        choices = [row for row in rows if row.get('sportId') == schedule['sport_id']
                   and row.get('tournamentId') == schedule['tournament_id']
                   and row.get('statusId') == 2
                   and {normalized(row.get('participant1Name', '')), normalized(row.get('participant2Name', ''))} == names
                   and datetime.fromtimestamp(stamp(row['startTime']), ZoneInfo('America/New_York')).date()
                   == datetime.fromtimestamp(stamp(fixture['scheduled_start']), ZoneInfo('America/New_York')).date()]
        if len(choices) != 1:
            raise ValueError('exact_NFL_fixture_match_not_unique:' + fixture['away_code'] + '-' + fixture['home_code'])
        provider = choices[0]
        delta = stamp(provider['startTime']) - stamp(fixture['scheduled_start'])
        matched.append({**fixture, 'provider_fixture': provider,
                        'identity_basis': 'Unique exact participant names, NFL tournament and Eastern calendar date',
                        'provider_minus_official_start_seconds': delta,
                        'start_clock_discrepancy_requires_review': delta != 0,
                        'conservative_original_schedule_cutoff': min(stamp(provider['startTime']), stamp(fixture['scheduled_start']))})
    if len({row['provider_fixture']['fixtureId'] for row in matched}) != len(matched):
        raise ValueError('duplicate_provider_fixture')
    return matched


class ProviderArchive:
    def __init__(self, out, key, max_requests=20):
        self.out, self.key, self.max_requests = out, key, max_requests
        self.out.mkdir(parents=True, exist_ok=True)
        self.path = out / 'requests.json'
        self.requests = json.loads(self.path.read_text()) if self.path.exists() else []
        self.session = requests.Session()

    def get(self, label, endpoint, params=None):
        if endpoint not in ('account', 'fixtures', 'historical-odds', 'markets'):
            raise ValueError('read_endpoint_not_allowed')
        params = dict(params or {})
        if any('key' in key.lower() or 'token' in key.lower() for key in params):
            raise ValueError('credential_parameter_forbidden')
        prior = [r for r in self.requests if r['label'] == label]
        if prior:
            record = prior[-1]
            if record['endpoint'] != endpoint or record['params'] != params:
                raise ValueError('cached_request_configuration_mismatch')
            if not record.get('file'):
                raise ValueError('uncertain_prior_request_requires_review')
            path = self.out / record['file']
            if hashlib.sha256(path.read_bytes()).hexdigest() != record['sha256']:
                raise ValueError('cached_response_hash_mismatch')
            with gzip.open(path, 'rt') as handle:
                cached = json.load(handle)
            if cached['http_status'] != 429:
                return cached
            if len(prior) >= 3:
                raise ValueError('bounded_rate_limit_retries_exhausted')
        if len(self.requests) >= self.max_requests:
            raise ValueError('bounded_provider_request_budget_exhausted')
        if self.requests:
            # Space from the preceding response, so different network transit
            # times cannot violate the server's five-second request cooldown.
            previous = self.requests[-1].get('retrieved_at', self.requests[-1]['started_at'])
            time.sleep(max(0., 5.5 - (time.time() - previous)))
        item = {'label': label, 'endpoint': endpoint, 'params': params, 'started_at': time.time()}
        self.requests.append(item)
        write_json(self.path, self.requests)
        result = {'request': {'endpoint': endpoint, 'params': params}, 'request_started_at': item['started_at'], 'http_status': None}
        try:
            response = self.session.get(OddsPapi.BASE + '/' + endpoint,
                                        params={**params, 'apiKey': self.key}, timeout=60, allow_redirects=False)
            result['http_status'] = response.status_code
            result['response_sha256'] = hashlib.sha256(response.content).hexdigest()
            try:
                payload = response.json()
            except ValueError:
                payload = {'non_json_body': response.text}
            result['payload'] = scrub(payload, self.key)
            result['response_headers'] = scrub({key: response.headers[key] for key in
                ('Date', 'ETag', 'Cache-Control', 'Content-Type', 'Retry-After') if key in response.headers}, self.key)
        except requests.RequestException:
            result['transport_error'] = 'credential_bearing_transport_details_suppressed'
        result['retrieved_at'] = time.time()
        name = f'{len(self.requests):02d}_{label}.json.gz'
        path = self.out / name
        with gzip.open(path.with_suffix('.tmp'), 'wt') as handle:
            json.dump(result, handle, separators=(',', ':'), allow_nan=False)
        path.with_suffix('.tmp').replace(path)
        item.update(file=name, sha256=hashlib.sha256(path.read_bytes()).hexdigest(), http_status=result['http_status'],
                    retrieved_at=result['retrieved_at'])
        write_json(self.path, self.requests)
        print(json.dumps({'endpoint': endpoint, 'status': result['http_status'], 'requests': len(self.requests)}), flush=True)
        return result


def run(client, schedule, limit_fixtures):
    result = {'schema_version': 1, 'study_id': schedule['study_id'], 'sport': 'NFL',
              'complete': False, 'history_status': 'unverified', 'history': [], 'orders_enabled': False}
    before = None
    try:
        env = client.get('account_before', 'account')
        if env['http_status'] != 200:
            raise ValueError('account_unavailable')
        before = account_counters(env['payload'])
        env = client.get('fixtures', 'fixtures', {'sportId': 14, 'tournamentId': 31, 'statusId': 2,
            'from': '2026-01-10T00:00:00Z', 'to': '2026-01-19T23:59:59Z', 'language': 'en'})
        if env['http_status'] != 200:
            raise ValueError('historical_fixture_discovery_unavailable')
        fixtures = match_fixtures(schedule, env['payload'])
        result['fixtures'] = fixtures
        write_json(client.out / 'matched_fixtures.json', fixtures)
        for fixture in fixtures[:limit_fixtures]:
            identifier = fixture['provider_fixture']['fixtureId']
            env = client.get('history_all_' + identifier, 'historical-odds',
                             {'fixtureId': identifier, 'bookmakers': schedule['historical_pinnacle_bookmaker']})
            summary = {'fixture_id': identifier, 'http_status': env['http_status'], 'away': fixture['away_code'], 'home': fixture['home_code']}
            result['history'].append(summary)
            if env['http_status'] == 404:
                summary['availability'] = 'provider_reports_no_history'
                continue
            if env['http_status'] != 200:
                result['history_status'] = 'access_denied' if env['http_status'] == 403 else 'request_unavailable'
                raise ValueError('history_stopped_on_HTTP_' + str(env['http_status']))
            summary.update(history_summary(env['payload'], identifier))
            market_counts = Counter(row['market_id'] for row in iter_history(env['payload']))
            summary['rows_by_market_id'] = dict(market_counts)
            if summary['row_count'] == 0:
                result['history_status'] = 'empty_history'
                raise ValueError('nonempty_NFL_history_not_confirmed')
            result['history_status'] = 'nonempty_history_confirmed'
            write_json(client.out / 'summary.json', result)
        result['complete'] = limit_fixtures >= len(fixtures)
        result['requested_history_fixtures'] = min(limit_fixtures, len(fixtures))
        result['nonempty_history_fixtures'] = sum(row.get('row_count', 0) > 0 for row in result['history'])
        result['all_target_history_available'] = result['nonempty_history_fixtures'] == len(fixtures)
        if not result['nonempty_history_fixtures']:
            result['history_status'] = 'no_history_on_requested_fixtures'
    except (ValueError, TypeError, KeyError) as exc:
        result['error'] = str(exc)
    finally:
        try:
            env = client.get('account_after_' + str(len(client.requests)), 'account')
            after = account_counters(env.get('payload')) if env['http_status'] == 200 else None
            result['account_counter_delta'] = counter_delta(before, after)
        except (ValueError, TypeError, KeyError):
            result['account_after_unavailable'] = True
        result.update(requests_attempted=len(client.requests), archive_inventory=client.requests,
                      schedule_sha256=hashlib.sha256(json.dumps(schedule, sort_keys=True).encode()).hexdigest(),
                      historical_timestamp_semantics='createdAt archive creation time; underlying information time and +30 availability require validation',
                      historical_payoff_and_fee_review_complete=False,
                      counter_caveat='Account-wide request deltas may include concurrent clients')
        write_json(client.out / 'summary.json', scrub(result, client.key))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--key-file', type=Path, required=True)
    parser.add_argument('--schedule', type=Path, default=ROOT / 'config/nfl_playoffs_history_2026.json')
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--limit-fixtures', type=int, default=1)
    args = parser.parse_args()
    if not 1 <= args.limit_fixtures <= 10:
        raise ValueError('fixture_limit_must_be_one_through_ten')
    key = args.key_file.read_text().strip()
    if not key:
        raise ValueError('empty_key_file')
    args.out.mkdir(parents=True, exist_ok=True)
    with (args.out / '.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        client = ProviderArchive(args.out, key)
        try:
            schedule = json.loads(args.schedule.read_text())
            summary_path = args.out / 'summary.json'
            previous = json.loads(summary_path.read_text()) if summary_path.exists() else {}
            expected = hashlib.sha256(json.dumps(schedule, sort_keys=True).encode()).hexdigest()
            if previous.get('complete') is True and previous.get('schedule_sha256') == expected:
                result = previous  # Completed missing-history evidence is cacheable too.
            else:
                result = run(client, schedule, args.limit_fixtures)
        finally:
            client.session.close()
    print(json.dumps({key: result.get(key) for key in ('complete', 'history_status', 'requests_attempted', 'error')}))


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        # Never expose a credential-bearing transport exception or URL.
        print(json.dumps({'error_type': type(exc).__name__}), file=sys.stderr)
        sys.exit(1)

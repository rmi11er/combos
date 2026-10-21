#!/usr/bin/env python3
"""Collect all week CFB exchange fixtures and map every retained native leg.

No September-5-only event index, game sample or minimum mapped-line requirement.
Only exact fixture/period/line matches receive a pricing token.
"""
import argparse
from collections import Counter, defaultdict
from datetime import datetime
import gzip
import hashlib
import json
from pathlib import Path
import re
import sys
import time
import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from combos.matching import match_market, fixture_teams, norm


def read_gz(path):
    with gzip.open(path, 'rt') as f:
        return json.load(f)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=ROOT/'runs/cfb_full_week_20260907')
    args = parser.parse_args(); args.out.mkdir(parents=True, exist_ok=True)
    cache = args.out/'gamma_events_aug29_sep21'; cache.mkdir(exist_ok=True)
    events = {}; refs = {}
    for offset in range(0, 10000, 100):
        path = cache/f'{offset:05d}.json.gz'
        params = {'limit': 100, 'offset': offset, 'tag_id': 100351,
                  'end_date_min': '2026-08-29T00:00:00Z', 'end_date_max': '2026-09-21T00:00:00Z'}
        if path.exists():
            response = read_gz(path)
            if response['params'] != params or response['status'] != 200:
                raise ValueError('invalid cached Gamma page; use a new range-specific cache directory')
        else:
            for attempt in range(5):
                try:
                    r = requests.get('https://gamma-api.polymarket.com/events', params=params, timeout=30)
                    if r.status_code == 429 or r.status_code >= 500:
                        time.sleep(2**attempt); continue
                    r.raise_for_status()
                    response = {'params': params, 'status': r.status_code, 'retrieved_at': time.time(), 'payload': r.json()}
                    break
                except requests.RequestException:
                    if attempt == 4: raise
            else:
                raise RuntimeError('Gamma retries exhausted')
            with gzip.open(path.with_suffix('.tmp'), 'wt') as f:
                json.dump(response, f, separators=(',', ':'))
            path.with_suffix('.tmp').replace(path)
        refs[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
        rows = response['payload']
        for event in rows:
            if event['id'] in events and events[event['id']] != event:
                raise ValueError('conflicting paginated event')
            events[event['id']] = event
        if len(rows) < 100:
            break
    else:
        raise ValueError('Gamma pagination safety boundary reached before completion')
    by_teams = defaultdict(list)
    for event in events.values():
        ml = [m for m in event['markets'] if m.get('sportsMarketType') == 'moneyline']
        if len(ml) != 1: continue
        teams = frozenset(norm(t) for t in json.loads(ml[0]['outcomes']))
        by_teams[teams].append(event)
    mappings = {}; dates = Counter()
    for path in sorted((ROOT/'data/raw/legs').glob('*.json.gz')):
        market = read_gz(path)['payload'].get('market')
        if not market or not market['ticker'].startswith(('KXNCAAFGAME-', 'KXNCAAFSPREAD-', 'KXNCAAFTOTAL-')):
            continue
        native_date = re.search(r'-(\d{2}[A-Z]{3}\d{2})', market['event_ticker'])
        if not native_date: continue
        day = datetime.strptime(native_date[1], '%y%b%d').date().isoformat()
        teams = fixture_teams(market)
        candidates = [e for e in by_teams[teams] if e['slug'].endswith(day)]
        if len(candidates) != 1:
            mappings[market['ticker']] = {'status': 'fixture_unmatched' if not candidates else 'ambiguous_fixture',
                                         'teams': sorted(teams or []), 'fixture_date': day}
            continue
        match = match_market(market, {teams: candidates[0]})
        mappings[market['ticker']] = match
        if match['status'] == 'matched': dates[day] += 1
    output = args.out/'polymarket_mapping.json'
    output.write_text(json.dumps(mappings, indent=2, allow_nan=False)+'\n')
    report = {'event_count': len(events), 'mapping_count': len(mappings),
              'status_counts': dict(Counter(m['status'] for m in mappings.values())),
              'matched_legs_by_fixture_date': dict(sorted(dates.items())), 'input_pages': refs,
              'mapping_sha256': hashlib.sha256(output.read_bytes()).hexdigest(),
              'method': 'All paginated CFB events in week; exact teams, native fixture date, full-game period and payoff line. No fixture sample.'}
    (args.out/'mapping_summary.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k != 'input_pages'}, indent=2))


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Rebuild all cached CFB opportunities before any fixture/price-source selection.

No network requests. Saturday is a census; other days retain observed sampled
prints at weight one and explicitly do not constitute complete portfolio paths.
"""
import argparse
from collections import Counter, defaultdict
from datetime import datetime
import gzip
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import time
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from combos.cfb_market_scope import classify_combo


def gz(path):
    with gzip.open(path, 'rt') as f:
        return json.load(f)


def stamp(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00')).timestamp()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=ROOT/'runs/cfb_full_week_20260907/cohort')
    parser.add_argument('--mapping', type=Path, default=ROOT/'data/derived/polymarket_mapping.json')
    parser.add_argument('--fetch-missing-leg-metadata', action='store_true')
    parser.add_argument('--metadata-only', action='store_true')
    parser.add_argument('--max-metadata-requests', type=int, default=20)
    parser.add_argument('--leg-metadata-tickers', type=Path,
                        help='Additional explicit ticker JSON list to fetch, including period/team-total legs')
    args = parser.parse_args(); args.out.mkdir(parents=True, exist_ok=True)
    mapping_path = args.mapping
    mappings = json.loads(mapping_path.read_text())
    start_by_fixture = {}
    for ticker, row in mappings.items():
        if row.get('start_time'):
            key = ticker.split('-')[1]; value = stamp(row['start_time'])
            if key in start_by_fixture and start_by_fixture[key] != value:
                raise ValueError('conflicting cached fixture start: '+key)
            start_by_fixture[key] = value
    original = sqlite3.connect(f'file:{ROOT}/data/raw/cfb_week_20260831/metadata.sqlite?mode=ro', uri=True)
    known = set(); cfb = {}
    for ticker, raw in original.execute('SELECT ticker,classification FROM markets'):
        known.add(ticker); c = json.loads(raw)
        if c['pure_cfb']:
            cfb[ticker] = c['nlegs']
    original.close()
    required = {t for t,n in cfb.items() if 2 <= n <= 4}
    database = sqlite3.connect(args.out/'metadata_index.sqlite')
    database.execute('CREATE TABLE IF NOT EXISTS metadata(ticker TEXT PRIMARY KEY, data TEXT NOT NULL, classification TEXT NOT NULL)')
    database.execute('CREATE TABLE IF NOT EXISTS files(path TEXT PRIMARY KEY, sha256 TEXT NOT NULL)')
    print(json.dumps({'stage': 'metadata', 'all_known': len(known), 'all_cfb': len(cfb), 'cfb_2to4': len(required)}), flush=True)
    paths = sorted((ROOT/'data/raw/metadata').glob('*.json.gz'))
    for i, path in enumerate(paths):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        prior = database.execute('SELECT sha256 FROM files WHERE path=?', (str(path),)).fetchone()
        if prior and prior[0] == digest:
            continue
        rows = []
        for market in gz(path)['payload']['markets']:
            ticker = market['ticker']
            if ticker not in required:
                continue
            legs = market.get('mve_selected_legs') or []
            fixtures = [l['market_ticker'].split('-')[1] for l in legs]
            try:
                classification = classify_combo(market)
                classification['nonplayer_reviewed'] = not classification['has_player_prop']
            except ValueError as exc:
                classification = {'nonplayer_reviewed': False, 'taxonomy_error': str(exc)}
            starts = [start_by_fixture.get(f) for f in fixtures]
            classification.update(distinct_fixtures=len(set(fixtures)) == len(fixtures),
                                  fixture_tokens=fixtures, start_times=starts,
                                  earliest_start=min(starts) if all(x is not None for x in starts) else None,
                                  start_basis='cached exchange fixture start; no price-match eligibility required')
            rows.append((ticker, json.dumps(market, separators=(',', ':')), json.dumps(classification)))
        with database:
            database.executemany('INSERT OR REPLACE INTO metadata VALUES(?,?,?)', rows)
            database.execute('INSERT OR REPLACE INTO files VALUES(?,?)', (str(path), digest))
        if i % 500 == 0:
            print(json.dumps({'stage': 'metadata', 'files': i+1, 'total': len(paths)}), flush=True)
    classes = {}; all_candidate_legs = set()
    for ticker, raw, c_raw in database.execute('SELECT ticker,data,classification FROM metadata'):
        c = json.loads(c_raw)
        # Mapping may be expanded independently; never reuse cached old start coverage.
        starts = [start_by_fixture.get(f) for f in c['fixture_tokens']]
        c.update(start_times=starts, earliest_start=min(starts) if all(x is not None for x in starts) else None)
        classes[ticker] = c
        if c['nonplayer_reviewed'] and c['distinct_fixtures'] and c.get('scope') == 'full_game_only':
            all_candidate_legs.update(l['market_ticker'] for l in json.loads(raw)['mve_selected_legs'])
    (args.out/'all_candidate_fullgame_legs.json').write_text(json.dumps(sorted(all_candidate_legs), indent=2)+'\n')
    metadata_candidates = set(all_candidate_legs)
    if args.leg_metadata_tickers:
        extra = json.loads(args.leg_metadata_tickers.read_text())
        if not isinstance(extra, list) or any(not isinstance(t, str) or not t.startswith('KXNCAAF') or '/' in t for t in extra):
            raise ValueError('additional metadata requires a CFB ticker list')
        metadata_candidates.update(extra)
    missing_legs = [t for t in sorted(metadata_candidates) if not (ROOT/'data/raw/legs'/(t+'.json.gz')).exists()]
    (args.out/'missing_candidate_leg_metadata.json').write_text(json.dumps(missing_legs, indent=2)+'\n')
    print(json.dumps({'stage': 'candidate_legs', 'fullgame_legs': len(all_candidate_legs), 'missing_metadata': len(missing_legs)}), flush=True)
    if args.fetch_missing_leg_metadata:
        import requests
        from rate_limit import pace
        session = requests.Session(); session.trust_env = False
        rawdir = args.out/'leg_metadata_batches'; rawdir.mkdir(exist_ok=True)
        requests_used = 0
        for offset in range(0, len(missing_legs), 100):
            batch = missing_legs[offset:offset+100]
            name = hashlib.sha256(','.join(batch).encode()).hexdigest()
            dest = rawdir/(name+'.json.gz')
            env = gz(dest) if dest.exists() else None
            attempts = 0
            while env is None or env['status'] == 429 or env['status'] >= 500:
                if requests_used >= args.max_metadata_requests:
                    break
                if attempts >= 4:
                    break
                if env is not None:
                    time.sleep(min(8, 2**attempts))
                pace(); attempts += 1
                requests_used += 1
                response = session.get('https://external-api.kalshi.com/trade-api/v2/markets',
                                       params={'tickers': ','.join(batch), 'limit': 1000}, timeout=30,
                                       allow_redirects=False)
                env = {'url': response.url, 'status': response.status_code, 'retrieved_at': time.time(),
                       'requested': batch, 'payload': response.json()}
                if dest.exists():
                    prior = rawdir/(name+'.attempt'+str(time.time_ns())+'.json.gz')
                    dest.rename(prior)
                with gzip.open(dest, 'wt') as f:
                    json.dump(env, f, separators=(',', ':'))
            if env is None:
                break
            if env['status'] != 200 or env['payload'].get('cursor'):
                raise ValueError('missing leg metadata batch failed/truncated: '+str(dest))
            for market in env['payload'].get('markets', []):
                ticker = market['ticker']
                if ticker not in batch:
                    raise ValueError('unexpected market in requested batch')
                target = ROOT/'data/raw/legs'/(ticker+'.json.gz')
                if not target.exists():
                    with gzip.open(target, 'wt') as f:
                        json.dump({'status': 200, 'retrieved_at': env['retrieved_at'], 'source_batch': str(dest),
                                   'payload': {'market': market}}, f, separators=(',', ':'))
            print(json.dumps({'stage': 'leg_metadata', 'batch': offset//100+1,
                              'retrieved': len(env['payload'].get('markets', [])), 'new_GETs': requests_used}), flush=True)
        session.close()
        remaining = [t for t in missing_legs if not (ROOT/'data/raw/legs'/(t+'.json.gz')).exists()]
        (args.out/'missing_candidate_leg_metadata.json').write_text(json.dumps(remaining, indent=2)+'\n')
    if args.metadata_only:
        database.close(); return
    stages = defaultdict(lambda: {'prints': 0, 'yes_premium': 0., 'payout_notional': 0.})
    by_day = defaultdict(lambda: defaultdict(lambda: {'prints': 0, 'yes_premium': 0., 'payout_notional': 0.}))
    eligible = []; seen = {}; missing = Counter(); missing_start = Counter(); rejected = Counter(); sources = []
    zone = ZoneInfo('America/Chicago'); lo = stamp('2026-08-31T05:00:00Z'); hi = stamp('2026-09-07T05:00:00Z')
    def add(stage, day, q, p):
        for target in (stages[stage], by_day[day][stage]):
            target['prints'] += 1; target['yes_premium'] += q*p; target['payout_notional'] += q
    def ingest(path, data, census, start, end):
        sources.append({'path': str(path.relative_to(ROOT)), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                        'start': start, 'end': end, 'census': census})
        for trade in data['combos']:
            at = stamp(trade['created_time'])
            if not lo <= at < hi:
                continue
            if not start <= at < end:
                raise ValueError('source print outside documented observation interval')
            identifier = trade['trade_id']; fingerprint = hashlib.sha256(json.dumps(trade, sort_keys=True).encode()).digest()
            if identifier in seen:
                if seen[identifier] != fingerprint:
                    raise ValueError('conflicting duplicate print')
                rejected['duplicate_source_print'] += 1; continue
            seen[identifier] = fingerprint
            q = float(trade['count_fp']); p = float(trade['yes_price_dollars'])
            if q <= 0 or not 0 <= p <= 1:
                raise ValueError('invalid public trade economics')
            ticker = trade['ticker']; day = datetime.fromtimestamp(at, zone).date().isoformat()
            add('all_observed_combos', day, q, p)
            if ticker not in known:
                missing[ticker] += 1; continue
            add('definition_known', day, q, p)
            if ticker not in cfb:
                continue
            add('pure_cfb_all_legs', day, q, p)
            if not 2 <= cfb[ticker] <= 4:
                continue
            add('cfb_2to4_legs', day, q, p)
            c = classes.get(ticker)
            if c is None:
                missing[ticker] += 1; continue
            if not c['nonplayer_reviewed']:
                rejected['unreviewed_or_player_family'] += 1; continue
            add('nonplayer_2to4', day, q, p)
            if c.get('scope') == 'full_game_only':
                add('fullgame_nonplayer_2to4', day, q, p)
            if not c['distinct_fixtures']:
                rejected['same_fixture'] += 1; continue
            add('distinct_fixture_nonplayer_2to4', day, q, p)
            if c.get('scope') == 'full_game_only':
                add('distinct_fixture_fullgame_2to4', day, q, p)
            if c['earliest_start'] is None:
                for fixture, time in zip(c['fixture_tokens'], c['start_times']):
                    if time is None:
                        missing_start[fixture] += 1
                rejected['unknown_start'] += 1; continue
            add('known_start', day, q, p)
            if at >= c['earliest_start']-60:
                rejected['in_play_or_60s_cutoff'] += 1; continue
            add('eligible_pregame', day, q, p)
            if c.get('scope') == 'full_game_only':
                add('eligible_pregame_fullgame', day, q, p)
            side = trade.get('taker_outcome_side', trade.get('taker_side'))
            if side == 'yes':
                add('eligible_pregame_yes_taker', day, q, p)
                if c.get('scope') == 'full_game_only':
                    add('eligible_pregame_fullgame_yes_taker', day, q, p)
            eligible.append({'trade': trade, 'sampling_weight': 1., 'original_volume_estimation_weight': 1. if census else 60.,
                             'source_file': str(path.relative_to(ROOT)), 'source_interval': [start, end],
                             'complete_trade_day': census, 'earliest_game_start': c['earliest_start']})
    manifest_path = ROOT/'data/raw/trades/manifest.json'; manifest = json.loads(manifest_path.read_text())
    if len(manifest['partitions']) != 24 or not all(p['complete'] for p in manifest['partitions']):
        raise ValueError('Saturday census incomplete')
    for part in manifest['partitions']:
        path = ROOT/'data/derived/tape'/f'hour_{part["hour"]:02d}.json.gz'
        ingest(path, gz(path), True, part['start'], part['end'])
        print(json.dumps({'stage': 'tape', 'census_hour': part['hour'], 'observed': len(seen), 'eligible': len(eligible)}), flush=True)
    plan_path = ROOT/'runs/cfb_week_20260831/sampling_plan.json'; plan = json.loads(plan_path.read_text())
    for start, end in plan['windows']:
        path = ROOT/'data/raw/cfb_week_20260831'/str(start)/'complete.json'
        if not path.exists():
            raise ValueError('saved sampled window incomplete: '+str(path))
        data = json.loads(path.read_text())
        if (data['start'], data['end']) != (start, end):
            raise ValueError('sample window boundaries mismatch')
        ingest(path, data, False, start, end)
    eligible.sort(key=lambda r: (r['trade']['created_time'], r['trade']['trade_id']))
    selected = {r['trade']['ticker'] for r in eligible}
    markets = {t: json.loads(m) for t,m in database.execute('SELECT ticker,data FROM metadata') if t in selected}
    required_legs = sorted({l['market_ticker'] for m in markets.values() for l in m['mve_selected_legs']})
    with gzip.open(args.out/'combo_cohort.json.gz', 'wt') as f:
        json.dump({'markets': markets, 'trades': eligible}, f, separators=(',', ':'))
    result = {'scope': 'All available Aug31-Sep6 public combo prints, CFB2–4 nonplayer distinct-fixture pregame; no20-fixture filter',
              'start_at': lo, 'end_at': hi, 'timezone': 'America/Chicago', 'minimum_seconds_before_start': 60,
              'stages': dict(stages), 'by_day': {d: dict(v) for d,v in sorted(by_day.items())},
              'rejections': dict(rejected), 'eligible_combo_definitions': len(markets), 'required_underlying_legs': len(required_legs),
              'missing_metadata': dict(missing), 'missing_start_fixtures': dict(missing_start),
              'limitations': ['Saturday is a complete public-print census; otherdays are observed sampled intervals only.',
                             'Every observed print has execution weight1. Never scale fills by original volume weight60.',
                             'Incomplete days omit intervening fills and cannot reproduce full-day funding/positions.',
                             'All three-venue price availability, payoff review and fair-model selection happen downstream.',
                             'Pregame classification uses saved schedule metadata; as-of schedule changes are not reconstructed.']}
    (args.out/'summary.json').write_text(json.dumps(result, indent=2)+'\n')
    (args.out/'required_legs.json').write_text(json.dumps(required_legs, indent=2)+'\n')
    (args.out/'missing_metadata.json').write_text(json.dumps(sorted(missing), indent=2)+'\n')
    provenance = {'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), 'sources': sources,
                  'metadata_files': dict(database.execute('SELECT path,sha256 FROM files')),
                  'mapping_sha256': hashlib.sha256(mapping_path.read_bytes()).hexdigest(),
                  'sampling_plan_sha256': hashlib.sha256(plan_path.read_bytes()).hexdigest(),
                  'census_manifest_sha256': hashlib.sha256(manifest_path.read_bytes()).hexdigest()}
    (args.out/'manifest.json').write_text(json.dumps(provenance, indent=2)+'\n')
    database.close()
    print(json.dumps({k:v for k,v in result.items() if k not in ('by_day', 'missing_metadata', 'missing_start_fixtures')}, indent=2))


if __name__ == '__main__':
    main()

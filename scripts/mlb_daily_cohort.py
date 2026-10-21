#!/usr/bin/env python3
"""Convert a fully acquired public day into the reusable MLB research schema.

All partition hashes and pagination chains must validate before any metadata
collection. Metadata requests are resumable, cached and bounded. Incomplete
metadata never becomes a complete MLB cohort. Fee assumptions are explicit,
dated inputs; this adapter never silently copies the September fee schedule.
"""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from decimal import Decimal
import gzip
import hashlib
import json
from pathlib import Path
import sqlite3
from zoneinfo import ZoneInfo

from mlb_native_cohort import classify, stamp
from mlb_public_day_acquire import Client, BudgetExhausted, read, save
from mlb_historical_fees import load_fee_scenario, require_coverage, fee_basis, kalshi_rate
from combos.fees import kalshi_fill_fee


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verified_partitions(day_root, date):
    start = datetime.fromisoformat(date).replace(tzinfo=ZoneInfo('America/Chicago'))
    lo, hi = start.timestamp(), (start + timedelta(days=1)).timestamp()
    partitions = []
    for path in sorted(day_root.glob('*/manifest.json')):
        manifest = read(path)
        if not manifest.get('complete'):
            raise ValueError('incomplete_public_tape_partition')
        partitions.append((path, manifest))
    partitions.sort(key=lambda item: item[1]['start_at'])
    cursor = lo
    for path, manifest in partitions:
        if manifest['start_at'] != cursor or not cursor < manifest['end_at'] <= hi:
            raise ValueError('public_tape_partition_gap_or_overlap')
        cursor = manifest['end_at']
    if cursor != hi:
        raise ValueError('public_tape_day_is_not_complete')
    return lo, hi, partitions


def verified_rows(path, manifest):
    """The capture buffers overlap; strict half-open trimming occurs here."""
    cursor = ''
    seen_cursors = set()
    pages = manifest.get('pages', [])
    if not pages:
        raise ValueError('complete_partition_has_no_response_pages')
    total = 0
    for index, page in enumerate(pages):
        file = path.parent / page['path']
        if file.parent != path.parent or sha(file) != page['sha256']:
            raise ValueError('public_tape_page_hash_or_path_mismatch')
        env = read(file)
        params = {'min_ts': int(manifest['start_at']) - 1,
                  'max_ts': int(manifest['end_at']) + 1, 'limit': 1000}
        if cursor:
            params['cursor'] = cursor
        if env.get('http_status') != 200 or env.get('request') != {'endpoint': manifest['endpoint'], 'params': params}:
            raise ValueError('public_tape_pagination_query_mismatch')
        rows = env['payload'].get('trades')
        if not isinstance(rows, list) or len(rows) != page['rows']:
            raise ValueError('public_tape_page_count_mismatch')
        total += len(rows)
        for row in rows:
            if manifest['start_at'] <= stamp(row['created_time']) < manifest['end_at']:
                yield row
        cursor = env['payload'].get('cursor') or ''
        if index < len(pages) - 1 and not cursor:
            raise ValueError('public_tape_pages_after_terminal_response')
        if cursor and cursor in seen_cursors:
            raise ValueError('public_tape_repeated_cursor')
        seen_cursors.add(cursor)
    if cursor or total != manifest['raw_rows']:
        raise ValueError('public_tape_manifest_not_terminal_or_count_mismatch')


def index_tape(day_root, date, out):
    lo, hi, partitions = verified_partitions(day_root, date)
    db = sqlite3.connect(out / 'tape_index.sqlite')
    db.execute('CREATE TABLE IF NOT EXISTS trades(id TEXT PRIMARY KEY, ticker TEXT NOT NULL, data TEXT NOT NULL)')
    db.execute('DELETE FROM trades')
    counts = Counter()
    for path, manifest in partitions:
        with db:
            for row in verified_rows(path, manifest):
                counts['public_prints'] += 1
                if not row['ticker'].startswith('KXMVE'):
                    continue
                data = json.dumps(row, sort_keys=True, separators=(',', ':'))
                old = db.execute('SELECT data FROM trades WHERE id=?', (row['trade_id'],)).fetchone()
                if old:
                    if old[0] != data:
                        raise ValueError('conflicting_public_trade_id')
                    counts['duplicate_combo_prints'] += 1
                    continue
                db.execute('INSERT INTO trades VALUES(?,?,?)', (row['trade_id'], row['ticker'], data))
                counts['unique_combo_prints'] += 1
    sources = [{'path': str(path.resolve()), 'sha256': sha(path), 'start_at': m['start_at'],
                'end_at': m['end_at'], 'method': 'census', 'sample_weight_in_replay': 1}
               for path, m in partitions]
    return db, lo, hi, sources, counts


def recover_metadata(tickers, cache, client, seed=None, workers=1, historical_first=False):
    """Recover disjoint batches with one shared strict request budget.

    Existing callers retain current-first sequential defaults. Parallel callers
    must use a thread-safe client, such as the shared public collector Client.
    Historical-first changes only probe order; both routes remain available.
    """
    if type(workers) is not int or not 1 <= workers <= 4:
        raise ValueError('metadata_workers_must_be_between_one_and_four')
    cache.mkdir(parents=True, exist_ok=True)
    wanted = set(tickers)
    result = {key: value for key, value in (seed or {}).items() if key in wanted}
    for file in sorted(cache.glob('*.json.gz')):
        env = read(file)
        if env.get('http_status') == 200:
            for market in env['payload'].get('markets', []):
                if market['ticker'] in wanted:
                    result[market['ticker']] = market
    missing = sorted(wanted - result.keys())
    endpoints = ('/historical/markets', '/markets') if historical_first else ('/markets', '/historical/markets')
    def recover_batch(batch):
        recovered = {}; exhausted = False
        for endpoint in endpoints:
            remaining = [ticker for ticker in batch if ticker not in recovered]
            if not remaining:
                break
            params = {'tickers': ','.join(remaining), 'limit': 1000}
            key = hashlib.sha256(json.dumps([endpoint, params], sort_keys=True).encode()).hexdigest()
            file = cache / (key + '.json.gz')
            if file.exists():
                env = read(file)
            else:
                try:
                    env = client.get(endpoint, params)
                except BudgetExhausted:
                    exhausted = True
                    break
                save(file, env)
            if env.get('http_status') != 200 or env['payload'].get('cursor'):
                raise ValueError('metadata_response_failed_or_truncated')
            for market in env['payload'].get('markets', []):
                if market['ticker'] not in remaining:
                    raise ValueError('metadata_response_unrequested_ticker')
                recovered[market['ticker']] = market
        return recovered, exhausted
    batches = [missing[offset:offset + 100] for offset in range(0, len(missing), 100)]
    stopped = False
    def consume(recovered_batches):
        nonlocal stopped
        for index, (recovered, exhausted) in enumerate(recovered_batches):
            result.update(recovered); stopped = stopped or exhausted
            if index % 10:
                continue
            print(json.dumps({'stage': 'metadata', 'requested': len(tickers), 'recovered': len(result),
                              'new_GETs': client.count, 'workers': workers,
                              'preferred_route': endpoints[0]}), flush=True)
    if workers == 1:
        consume(map(recover_batch, batches))
    else:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(recover_batch, batch) for batch in batches]
            consume(future.result() for future in as_completed(futures))
    return result, sorted(wanted - result.keys()), stopped


def write_cohort(db, markets, native, out, lo, hi, sources, counts, scenario, date):
    mlb = {key: market for key, market in markets.items() if classify(market)['pure_mlb']}
    required = set()
    all_legs = set()
    n_universe = n_candidates = 0
    with gzip.open(out / 'universe_trades.jsonl.gz', 'wt') as universe, \
            gzip.open(out / 'candidate_trades.jsonl.gz', 'wt') as candidates:
        for ticker, raw in db.execute('SELECT ticker,data FROM trades ORDER BY id'):
            if ticker not in mlb:
                continue
            trade = json.loads(raw)
            market = mlb[ticker]
            classification = classify(market)
            at = stamp(trade['created_time'])
            require_coverage(scenario, at)
            q, price = Decimal(trade['count_fp']), Decimal(trade['yes_price_dollars'])
            if not q.is_finite() or not price.is_finite() or q <= 0 or not 0 <= price <= 1:
                raise ValueError('invalid_trade_economics')
            settlement = market.get('settlement_value_dollars')
            settlement = float(settlement) if settlement not in (None, '') else {'yes': 1., 'no': 0.}.get(market.get('result'))
            rate, rate_basis = kalshi_rate(scenario, ticker, at, 'combo_maker')
            fee = float(kalshi_fill_fee(q, 1 - price, str(rate))['net_fee'])
            start = classification['earliest_scheduled_start']
            pregame = None if start is None else at < start
            row = {'trade': trade, 'classification': classification, 'sampling_method': 'census',
                   'pregame_scheduled_proxy': pregame, 'settlement_value': settlement,
                   'settlement_at': stamp(market['settlement_ts']) if market.get('settlement_ts') else None,
                   'native_status': market.get('status'), 'maker_fee_dollars': fee,
                   'seller_pnl_dollars': None if settlement is None else float(q) * (float(price) - settlement) - fee,
                   'fee_rate': rate, 'fee_basis': fee_basis(scenario), 'fee_rate_provenance': rate_basis,
                   'source_window': [lo, hi]}
            universe.write(json.dumps(row, separators=(',', ':')) + '\n')
            n_universe += 1
            all_legs.update(leg['market_ticker'] for leg in market['mve_selected_legs'])
            if classification['fullgame_core'] and pregame is True:
                candidates.write(json.dumps(row, separators=(',', ':')) + '\n')
                n_candidates += 1
                required.update(leg['market_ticker'] for leg in market['mve_selected_legs'])
    save(out / 'combo_markets.json.gz', mlb)
    save(out / 'underlying_markets.json.gz', native)
    save(out / 'underlying_tickers.json', sorted(required))
    save(out / 'all_universe_underlying_tickers.json', sorted(all_legs))
    save(out / 'fee_scenario.json', scenario)
    summary = {'schema_version': 1, 'date': date, 'start_at': lo, 'end_at': hi,
               'complete_census': True, 'counts': dict(counts), 'pure_mlb_prints': n_universe,
               'pure_mlb_definitions': len(mlb), 'fullgame_pregame_proxy_prints': n_candidates,
               'candidate_underlying_tickers': len(required), 'sources': sources,
               'fee_scenario': scenario, 'script_sha256': sha(Path(__file__)),
               'limits': ['Public printed-price capacity scenario, not observed own RFQ acceptance.',
                          'Pregame is native original schedule proxy; exceptional settlement parity unverified.',
                          'All candidate leg counts and same-game structures retained for universe audit; model replay selects 2–4 distinct fixtures.',
                          'Unverified fee scenarios are sensitivity results, not a date-verified net P&L claim.']}
    save(out / 'summary.json', summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--acquisition', required=True, type=Path)
    parser.add_argument('--date', required=True)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--fee-scenario', required=True, type=Path)
    parser.add_argument('--max-metadata-requests', type=int, default=0)
    parser.add_argument('--metadata-workers', type=int, default=4)
    parser.add_argument('--seed-cohort', type=Path)
    args = parser.parse_args()
    if args.max_metadata_requests < 0 or not 1 <= args.metadata_workers <= 4:
        raise ValueError('invalid_metadata_budget_or_worker_count')
    args.out.mkdir(parents=True, exist_ok=True)
    scenario = load_fee_scenario(args.fee_scenario)
    # A interrupted replacement must not retain an earlier success certificate.
    (args.out / 'summary.json').unlink(missing_ok=True)
    db, lo, hi, sources, counts = index_tape(args.acquisition / args.date, args.date, args.out)
    require_coverage(scenario, lo, hi)
    tickers = [row[0] for row in db.execute('SELECT DISTINCT ticker FROM trades ORDER BY ticker')]
    client = Client(args.out, args.max_metadata_requests)
    historical_first = all(read(Path(source['path'])).get('endpoint') == '/historical/trades' for source in sources)
    seed = read(args.seed_cohort / 'combo_markets.json.gz') if args.seed_cohort else None
    markets, missing, stopped = recover_metadata(tickers, args.out / 'combo_metadata', client, seed,
                                                 args.metadata_workers, historical_first)
    save(args.out / 'metadata_coverage.json', {'requested': len(tickers), 'recovered': len(markets),
                                            'missing': missing, 'budget_exhausted': stopped, 'new_GETs': client.count,
                                            'workers': args.metadata_workers, 'historical_first': historical_first})
    if missing:
        raise SystemExit('Incomplete combo metadata; resume with a larger explicit metadata request budget.')
    required = set()
    for market in markets.values():
        c = classify(market)
        if c['pure_mlb'] and c['fullgame_core']:
            required.update(leg['market_ticker'] for leg in market['mve_selected_legs'])
    native_seed = read(args.seed_cohort / 'underlying_markets.json.gz') if args.seed_cohort else None
    native, missing, stopped = recover_metadata(sorted(required), args.out / 'underlying_metadata', client, native_seed,
                                                args.metadata_workers, historical_first)
    save(args.out / 'underlying_acquisition.json', {'requested': len(required), 'recovered': len(native),
                                                 'missing': missing, 'budget_exhausted': stopped, 'new_GETs': client.count})
    if missing:
        raise SystemExit('Incomplete underlying metadata; resume with a larger explicit metadata request budget.')
    summary = write_cohort(db, markets, native, args.out, lo, hi, sources, counts, scenario, args.date)
    db.close()
    print(json.dumps({key: value for key, value in summary.items() if key != 'sources'}, indent=2))


if __name__ == '__main__':
    main()

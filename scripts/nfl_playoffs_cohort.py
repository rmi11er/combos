#!/usr/bin/env python3
"""Build full-day NFL native cohorts without assuming unverified January fees."""
import argparse
from collections import Counter
from datetime import datetime
import gzip
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from mlb_daily_cohort import index_tape, recover_metadata
from mlb_public_day_acquire import Client, read, save
from nfl_playoffs_exchange_review import native_event

CORE = {'KXNFLGAME', 'KXNFLSPREAD', 'KXNFLTOTAL'}


def classify(market, schedule):
    lookup = {native_event(f).split('-', 1)[1]: f for f in schedule['fixtures']}
    legs = market.get('mve_selected_legs') or []
    tickers = [leg.get('market_ticker', '') for leg in legs]
    series = sorted({ticker.split('-')[0] for ticker in tickers})
    tokens = [ticker.split('-')[1] if '-' in ticker else '' for ticker in tickers]
    fixtures = [lookup.get(token) for token in tokens]
    starts = [datetime.fromisoformat(f['scheduled_start']).timestamp() if f else None for f in fixtures]
    return {'nlegs': len(legs), 'pure_nfl': len(legs) >= 2 and all(t.startswith('KXNFL') for t in tickers),
            'series': series, 'fullgame_core': bool(legs) and set(series) <= CORE,
            'target_fixtures_only': bool(legs) and all(f is not None for f in fixtures),
            'fixture_tokens': tokens, 'distinct_fixtures': len(tokens) == len(set(tokens)),
            'earliest_scheduled_start': min(starts) if starts and all(v is not None for v in starts) else None,
            'start_basis': 'Original NFL published playoff schedule; conservative when provider later shifts kickoff',
            'other_or_unmatched_fixture_tokens': sorted({t for t in tokens if t not in lookup})}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--schedule', type=Path, default=ROOT / 'config/nfl_playoffs_history_2026.json')
    parser.add_argument('--acquisition', type=Path, required=True)
    parser.add_argument('--date', required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--max-metadata-requests', type=int, default=0)
    args = parser.parse_args()
    if not 0 <= args.max_metadata_requests <= 20000:
        raise ValueError('bounded_metadata_budget_required')
    schedule = read(args.schedule)
    if not schedule['trading_start_date'] <= args.date <= schedule['trading_end_date_inclusive']:
        raise ValueError('date_outside_NFL_study')
    args.out.mkdir(parents=True, exist_ok=True)
    db, lo, hi, sources, counts = index_tape(args.acquisition / args.date, args.date, args.out)
    client = Client(args.out, args.max_metadata_requests)
    try:
        tickers = [r[0] for r in db.execute('SELECT DISTINCT ticker FROM trades ORDER BY ticker')]
        markets, missing, stopped = recover_metadata(tickers, args.out / 'metadata', client,
                                                     workers=2, historical_first=True)
        save(args.out / 'metadata_coverage.json', {'requested': len(tickers), 'recovered': len(markets),
                                                'missing': missing, 'stopped': stopped, 'new_GETs': client.count})
        if missing:
            raise ValueError('complete_native_metadata_required_before_NFL_cohort')
        native = {ticker: m for ticker, m in markets.items() if classify(m, schedule)['pure_nfl']}
        classes = {ticker: classify(m, schedule) for ticker, m in native.items()}
        required = set()
        totals = Counter()
        with gzip.open(args.out / 'universe_trades.jsonl.gz', 'wt') as universe, gzip.open(args.out / 'candidate_trades.jsonl.gz', 'wt') as candidates:
            for ticker, raw in db.execute('SELECT ticker,data FROM trades ORDER BY id'):
                if ticker not in native:
                    continue
                trade = json.loads(raw)
                c, m = classes[ticker], native[ticker]
                at = datetime.fromisoformat(trade['created_time'].replace('Z', '+00:00')).timestamp()
                start = c['earliest_scheduled_start']
                pregame = start is not None and at < start - schedule['pregame_cutoff_seconds']
                row = {'trade': trade, 'classification': c, 'sampling_method': 'census', 'source_window': [lo, hi],
                       'pregame_scheduled_proxy': pregame, 'native_status': m.get('status'),
                       'settlement_value_dollars': m.get('settlement_value_dollars'), 'result': m.get('result'),
                       'settlement_ts': m.get('settlement_ts'), 'maker_fee_dollars': None,
                       'fee_status': 'January_effective_fee_schedule_requires_review_before_net_PnL'}
                universe.write(json.dumps(row, separators=(',', ':')) + '\n')
                totals['pure_nfl_prints'] += 1
                totals['target_fixture_prints'] += c['target_fixtures_only']
                if c['target_fixtures_only'] and c['fullgame_core'] and c['distinct_fixtures'] and 2 <= c['nlegs'] <= 4 and pregame:
                    candidates.write(json.dumps(row, separators=(',', ':')) + '\n')
                    totals['primary_candidate_prints'] += 1
                    required.update(leg['market_ticker'] for leg in m['mve_selected_legs'])
        save(args.out / 'combo_markets.json.gz', native)
        save(args.out / 'underlying_tickers.json', sorted(required))
        save(args.out / 'summary.json', {'schema_version': 1, 'sport': 'NFL', 'date': args.date,
             'complete_census': True, 'start_at': lo, 'end_at': hi, 'public_counts': dict(counts),
             'counts': dict(totals), 'sources': sources, 'net_PnL_ready': False,
             'scope': schedule, 'orders_enabled': False})
        print(json.dumps(dict(totals)))
    finally:
        db.close()


if __name__ == '__main__':
    main()

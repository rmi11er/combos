#!/usr/bin/env python3
"""Bounded, resumable public MLB history availability probe; never a backtest.

No authentication, provider subscription endpoints, retries or order mutations.
Raw requests are keyed by exact URL/parameters and counted across resumptions.
"""
import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
from urllib.parse import urlparse

import requests

ROOT = Path(__file__).resolve().parents[1]
BASE = 'https://external-api.kalshi.com/trade-api/v2'


def timestamp(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00')).timestamp()


class PublicProbe:
    def __init__(self, folder, budget):
        self.folder = folder
        self.raw = folder / 'raw'
        self.raw.mkdir(parents=True, exist_ok=True)
        self.budget = budget
        self.calls = 0
        self.requests = []

    def get(self, label, url, params=None):
        if urlparse(url).netloc not in {'external-api.kalshi.com', 'gamma-api.polymarket.com', 'clob.polymarket.com'}:
            raise ValueError('public exchange host allowlist')
        query = {'url': url, 'params': params or {}}
        key = hashlib.sha256(json.dumps(query, sort_keys=True).encode()).hexdigest()
        dest = self.raw / (key + '.json')
        if dest.exists():
            env = json.loads(dest.read_text())
        else:
            if len(list(self.raw.glob('*.json'))) >= self.budget:
                self.requests.append({'label': label, 'status': 'budget_exhausted', 'query': query})
                return None
            env = {'query': query, 'retrieved_at': datetime.now(timezone.utc).isoformat()}
            # A fresh Session disables requests' automatic .netrc authentication.
            session = requests.Session(); session.trust_env = False
            self.calls += 1
            try:
                response = session.get(url, params=params, timeout=30, allow_redirects=False)
                env.update(status=response.status_code, response_url=response.url,
                           response_sha256=hashlib.sha256(response.content).hexdigest())
                try:
                    env['payload'] = response.json()
                except ValueError:
                    env['payload'] = response.text
            except requests.RequestException as exc:
                env.update(status=None, error=type(exc).__name__)
            finally:
                session.close()
            dest.write_text(json.dumps(env, indent=2) + '\n')
        self.requests.append({'label': label, 'raw_file': str(dest.relative_to(self.folder)),
                              'status': env.get('status'), 'query': query})
        print(json.dumps({'label': label, 'status': env.get('status'), 'new_GETs': self.calls}), flush=True)
        return env.get('payload') if env.get('status') == 200 else None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--date', default='2026-07-01')
    parser.add_argument('--out', type=Path, default=ROOT/'runs/mlb_history_probe_20260701')
    parser.add_argument('--max-requests', type=int, default=10)
    args = parser.parse_args()
    if not 1 <= args.max_requests <= 10:
        raise ValueError('probe supports at most ten public GETs')
    probe = PublicProbe(args.out, args.max_requests)
    report = {'date': args.date, 'purpose': 'Availability probe, not representative volume or strategy returns',
              'authenticated_requests': 0, 'oddspapi_requests': 0,
              'limits': ['Three fixed 15-second UTC windows; metadata limited to first 100 sorted combo tickers.',
                         'No extrapolation from probe; exact MLB payoff matching remains unreviewed.'],
              'windows': []}
    try:
        cutoff = probe.get('kalshi_cutoff', BASE+'/historical/cutoff')
        report['cutoff'] = cutoff
        if not cutoff:
            raise RuntimeError('historical cutoff unavailable; cannot confidently route history')
        collected = {}
        for hour in (17, 20, 23):
            start = int(timestamp(f'{args.date}T{hour:02d}:00:00Z')); end = start+15
            boundary = cutoff['trades_created_ts']
            boundary = timestamp(boundary) if isinstance(boundary, str) else boundary
            endpoint = '/historical/trades' if end <= boundary else '/markets/trades'
            payload = probe.get(f'trades_{hour:02d}UTC', BASE+endpoint,
                                {'min_ts': start-1, 'max_ts': end+1, 'limit': 1000})
            rows = [r for r in (payload or {}).get('trades', []) if start <= timestamp(r['created_time']) < end]
            combos = [r for r in rows if r['ticker'].startswith('KXMVE')]
            for row in combos:
                identifier = row['trade_id']
                if identifier in collected and collected[identifier] != row:
                    raise ValueError('conflicting duplicate print')
                collected[identifier] = row
            report['windows'].append({'start_at': start, 'end_at': end, 'endpoint': endpoint,
                                      'all_prints': len(rows), 'combo_prints': len(combos),
                                      'complete': payload is not None and not payload.get('cursor'),
                                      'next_cursor': (payload or {}).get('cursor')})
        tickers = sorted({r['ticker'] for r in collected.values()})[:100]
        markets = {}
        if tickers:
            # Metadata tier is determined by settlement, not the print timestamp.
            # Query the live tier first; look up missing tickers individually in history.
            payload = probe.get('combo_metadata_live', BASE+'/markets',
                                {'tickers': ','.join(tickers), 'limit': 100})
            markets.update((m['ticker'], m) for m in (payload or {}).get('markets', []))
            missing = [t for t in tickers if t not in markets]
            if missing:
                payload = probe.get('combo_metadata_historical_batch', BASE+'/historical/markets',
                                    {'tickers': ','.join(missing), 'limit': 100})
                markets.update((m['ticker'], m) for m in (payload or {}).get('markets', []))
        classifications = {}
        for ticker, market in markets.items():
            legs = market.get('mve_selected_legs') or []
            flags = [l.get('market_ticker', '').startswith('KXMLB') for l in legs]
            classifications[ticker] = {'legs': len(legs), 'any_mlb': any(flags),
                                       'pure_mlb': len(legs) >= 2 and all(flags),
                                       'series': sorted({l['market_ticker'].split('-')[0] for l in legs}),
                                       'core_fullgame_families': bool(legs) and all(l['market_ticker'].split('-')[0] in
                                           {'KXMLBGAME', 'KXMLBSPREAD', 'KXMLBTOTAL'} for l in legs),
                                       'distinct_fixture_tokens': len({l['market_ticker'].split('-')[1] for l in legs}) == len(legs)}
        pure = [r for r in collected.values() if classifications.get(r['ticker'], {}).get('pure_mlb')]
        report.update(combo_prints=len(collected), unique_combo_tickers=len({r['ticker'] for r in collected.values()}),
                      metadata_requested=len(tickers), metadata_recovered=len(markets),
                      unclassified_combo_prints=sum(r['ticker'] not in classifications for r in collected.values()),
                      pure_mlb_prints=len(pure), pure_mlb_leg_counts=dict(Counter(classifications[r['ticker']]['legs'] for r in pure)),
                      pure_mlb_yes_premium=sum(float(r['count_fp'])*float(r['yes_price_dollars']) for r in pure),
                      pure_mlb_payout_notional=sum(float(r['count_fp']) for r in pure))
        candidates = [r for r in pure if 2 <= classifications[r['ticker']]['legs'] <= 4
                      and classifications[r['ticker']]['core_fullgame_families']
                      and classifications[r['ticker']]['distinct_fixture_tokens']]
        required_legs = sorted({l['market_ticker'] for r in candidates for l in markets[r['ticker']]['mve_selected_legs']})
        report['core_distinct_fixture_2to4_candidate_prints'] = len(candidates)
        report['candidate_required_underlying_legs'] = len(required_legs)
        (args.out/'candidate_cohort.json').write_text(json.dumps({'trades': candidates,
            'required_leg_tickers': required_legs,
            'scope_warning': 'Candidate identities only: pregame, exact payoff and both venue histories still require validation.'}, indent=2)+'\n')
        (args.out/'combo_sample.json').write_text(json.dumps({'trades': list(collected.values()), 'markets': markets,
                                                            'classifications': classifications}, indent=2)+'\n')
        if pure:
            chosen = sorted(pure, key=lambda r: (classifications[r['ticker']]['legs'], r['trade_id']))[0]
            leg = markets[chosen['ticker']]['mve_selected_legs'][0]['market_ticker']
            payload = probe.get('underlying_market', BASE+'/markets/'+leg)
            leg_market = (payload or {}).get('market')
            if leg_market:
                at = int(timestamp(chosen['created_time']))
                candles = probe.get('underlying_candles', BASE+'/series/'+leg.split('-')[0]+'/markets/'+leg+'/candlesticks',
                                    {'start_ts': at-3600, 'end_ts': at, 'period_interval': 1})
                report['underlying_probe'] = {'ticker': leg, 'market_recovered': True,
                                              'candles': len((candles or {}).get('candlesticks', [])),
                                              'settlement_ts_present': bool(leg_market.get('settlement_ts'))}
        tomorrow = (datetime.fromisoformat(args.date)+timedelta(days=1)).date().isoformat()
        events = probe.get('polymarket_mlb_events', 'https://gamma-api.polymarket.com/events',
                           {'tag_slug': 'mlb', 'closed': 'true', 'end_date_min': args.date+'T00:00:00Z',
                            'end_date_max': tomorrow+'T23:59:59Z', 'limit': 100})
        events = events if isinstance(events, list) else []
        mlb_events = [e for e in events if e.get('slug', '').startswith('mlb-')]
        report['polymarket_probe'] = {'returned_events': len(events), 'mlb_slug_events': len(mlb_events),
                                     'matching_is_unreviewed': True}
        date_events = [e for e in mlb_events if args.date in e.get('slug', '')]
        report['polymarket_probe']['date_slug_events'] = len(date_events)
        candidates = [m for e in date_events for m in e.get('markets', []) if m.get('clobTokenIds')]
        if candidates:
            market = candidates[0]; tokens = market['clobTokenIds']
            tokens = json.loads(tokens) if isinstance(tokens, str) else tokens
            at = int(timestamp(args.date+'T17:00:00Z'))
            payload = probe.get('polymarket_price_history', 'https://clob.polymarket.com/prices-history',
                                {'market': tokens[0], 'startTs': at-3600, 'endTs': at, 'fidelity': 1})
            report['polymarket_probe'].update(price_rows=len(payload.get('history', [])) if payload is not None else None,
                                             token=tokens[0], market_slug=market.get('slug'))
    except (RuntimeError, KeyError, ValueError) as exc:
        report['stopped_reason'] = str(exc)
    finally:
        report.update(requests=probe.requests, new_public_GETs=probe.calls,
                      persisted_public_GETs=len(list(probe.raw.glob('*.json'))),
                      raw_inventory={p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in probe.raw.glob('*.json')},
                      script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
        (args.out/'summary.json').write_text(json.dumps(report, indent=2)+'\n')
        print(json.dumps({k: v for k,v in report.items() if k != 'requests'}, indent=2))


if __name__ == '__main__':
    main()

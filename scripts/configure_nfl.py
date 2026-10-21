#!/usr/bin/env python3
"""Capture public NFL definitions and build a reproducible collection config."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
from datetime import datetime
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from combos.nfl_matching import SERIES, build_mappings, kalshi_rates, FEE_SCHEDULE

KALSHI = 'https://api.elections.kalshi.com/trade-api/v2'
GAMMA = 'https://gamma-api.polymarket.com'
COMBO_SERIES = ('KXMVECROSSCATEGORY-SHARD1', 'KXMVECROSSCATEGORY0-SHARD1')


def save_response(directory, name, url, params=None):
    import requests
    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()
    record = {'url': response.url, 'status': response.status_code, 'retrieved_at': time.time(), 'payload': response.json()}
    (directory / (name + '.json')).write_text(json.dumps(record, indent=2) + '\n')
    return record['payload']


def refresh(directory, season, week, combo_samples):
    directory.mkdir(parents=True, exist_ok=False)
    found = save_response(directory, 'pm_season_discovery', GAMMA + '/series', {'slug': f'nfl-{season}'})
    found = [s for s in found if s.get('slug') == f'nfl-{season}']
    if len(found) != 1:
        raise ValueError('NFL season series must match exactly once')
    # Sports index may still identify the previous season. Listing startDate is
    # not game kickoff; query the verified season and eventWeek instead.
    save_response(directory, 'pm_week1' if week == 1 else f'pm_week{week}', GAMMA + '/events',
                  {'series_id': found[0]['id'], 'event_week': week, 'closed': 'false', 'limit': 100})
    for sid, filename in zip(SERIES, ('kalshi_games', 'kalshi_spreads', 'kalshi_totals')):
        response = save_response(directory, filename, KALSHI + '/markets', {'series_ticker': sid, 'status': 'open', 'limit': 1000})
        page = 1
        while response.get('cursor'):
            response = save_response(directory, f'{filename}_{page}', KALSHI + '/markets',
                {'series_ticker': sid, 'status': 'open', 'limit': 1000, 'cursor': response['cursor']})
            page += 1
    for sid in (*SERIES, *COMBO_SERIES):
        save_response(directory, 'series_' + sid, KALSHI + '/series/' + sid)
        save_response(directory, 'fees_' + sid, KALSHI + '/series/fee_changes', {'series_ticker': sid, 'show_historical': 'true'})
    for ticker in combo_samples:
        save_response(directory, 'combo_' + ticker, KALSHI + '/markets/' + ticker)


def build(directory, base, season, week):
    sources = {}
    def read(name):
        path = directory / (name + '.json')
        raw = path.read_bytes(); record = json.loads(raw)
        if record['status'] != 200:
            raise ValueError('unsuccessful source: ' + name)
        sources[str(path)] = {'sha256': hashlib.sha256(raw).hexdigest(), 'url': record['url'], 'retrieved_at': record['retrieved_at']}
        return record['payload']
    markets = []
    for filename in ('kalshi_games', 'kalshi_spreads', 'kalshi_totals'):
        page = read(filename); markets.extend(page['markets']); index = 1
        while page.get('cursor'):
            page = read(f'{filename}_{index}'); markets.extend(page['markets']); index += 1
    series = {sid: read('series_' + sid)['series'] for sid in (*SERIES, *COMBO_SERIES)}
    fee_changes = {sid: read('fees_' + sid) for sid in series}
    events = read(f'pm_week{week}')
    if len(events) >= 100:
        raise ValueError('Polymarket event response may be truncated; add pagination before building')
    mappings, review = build_mappings(markets, events, series, season, week)
    if not mappings:
        raise ValueError('no matched NFL markets')
    def checked_at(name):
        return sources[str(directory / (name + '.json'))]['retrieved_at']
    def fee_expiry(sid):
        verified = min(checked_at('series_' + sid), checked_at('fees_' + sid))
        expiry = verified + 86400
        for change in fee_changes[sid]['series_fee_change_arr']:
            when = datetime.fromisoformat(change['scheduled_ts'].replace('Z', '+00:00')).timestamp()
            if when > verified:
                expiry = min(expiry, when)
        return verified, expiry
    for mapping in mappings:
        sid = mapping['kalshi_ticker'].split('-')[0]
        verified, expiry = fee_expiry(sid)
        mapping['fees']['kalshi'].update(verified_at=verified, valid_until=expiry)
        verified = checked_at(f'pm_week{week}')
        mapping['fees']['polymarket'].update(verified_at=verified, valid_until=verified+86400)
    terms = {}
    for path in sorted(directory.glob('combo_*.json')):
        market = read(path.stem)['market']
        # Require an exact verified series boundary. The RFQ collection can be
        # non-zero-fee even when its resulting market uses the zero-fee series.
        sid = next((s for s in COMBO_SERIES if market['ticker'].startswith(s + '-')), None)
        if not sid:
            continue
        ranges = market.get('price_ranges')
        if not ranges:
            raise ValueError('combo price grid missing')
        if sid + '-' in terms and terms[sid + '-']['price_ranges'] != ranges:
            raise ValueError('sampled grids differ within series; require per-market grid lookup')
        terms[sid + '-'] = {'maker_fee_rate': kalshi_rates(series[sid])['maker'],
            'fee_reference': FEE_SCHEDULE + '#series=' + sid,
            'price_ranges': ranges, 'grid_reference': KALSHI + '/markets/' + market['ticker'],
            'grid_validation': 'sampled_market_metadata; refresh_and_validate_market_before_live_execution',
            'fee_changes': fee_changes[sid]}
        verified, expiry = fee_expiry(sid)
        terms[sid + '-'].update(verified_at=verified, valid_until=expiry)
    if len(terms) != len(COMBO_SERIES):
        raise ValueError('provide current market grid samples for both combo series')
    result = copy.deepcopy(base)
    result.update(mode='shadow', mappings=mappings, combo_terms=terms,
        comment='NFL shadow collection config. Use config/weighting.json for delayed-Pinnacle pregame policy. Pinnacle payoff review, exceptional-settlement policy and current fees still gate pricing. Risk caps inherited from base config. No ticket cap or probability restriction.')
    review.update(combo_terms=terms, sources=sources,
        polymarket_fee_rates=sorted({m['fees']['polymarket']['rate'] for m in mappings}),
        kalshi_taker_rates=sorted({m['fees']['kalshi']['rate'] for m in mappings}))
    return result, review


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raw-dir', type=Path, required=True)
    parser.add_argument('--base-config', type=Path, default=Path('config/runtime.json'))
    parser.add_argument('--out-config', type=Path, required=True)
    parser.add_argument('--out-review', type=Path, required=True)
    parser.add_argument('--season', type=int, default=2026)
    parser.add_argument('--week', type=int, default=1)
    parser.add_argument('--refresh', action='store_true', help='Public GET only; requires a new raw directory')
    parser.add_argument('--combo-sample', action='append', default=[], help='One actual market ticker per supported combo series')
    args = parser.parse_args()
    if args.refresh:
        refresh(args.raw_dir, args.season, args.week, args.combo_sample)
    config, review = build(args.raw_dir, json.loads(args.base_config.read_text()), args.season, args.week)
    for path, payload in ((args.out_config, config), (args.out_review, review)):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2) + '\n')
    print(json.dumps({k: review[k] for k in ('fixtures', 'kalshi_in_week', 'matched', 'polymarket_fee_rates', 'kalshi_taker_rates', 'pricing_ready')}, indent=2))


if __name__ == '__main__':
    main()

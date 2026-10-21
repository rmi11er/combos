#!/usr/bin/env python3
"""Review retained NFL January exchange definitions and the tiny history probe."""
import argparse
from datetime import datetime
import gzip
import hashlib
import json
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
ALIASES = {'LAR': 'LA', 'JAX': 'JAC'}


def native_event(fixture):
    date = datetime.fromisoformat(fixture['scheduled_start']).astimezone(ZoneInfo('America/New_York'))
    pair = ''.join(ALIASES.get(fixture[key], fixture[key]) for key in ('away_code', 'home_code'))
    return 'KXNFLGAME-' + date.strftime('%y%b%d').upper() + pair


def review(schedule, markets, events):
    result = []
    for fixture in schedule['fixtures']:
        names = {fixture['away'], fixture['home']}
        date = fixture['scheduled_start'][:10]
        pm = [event for event in events if event.get('seriesSlug') == 'nfl-2025'
              and event.get('eventDate') == date and {team.get('name') for team in event.get('teams', [])} == names]
        if len(pm) != 1:
            raise ValueError('exact_PM_playoff_fixture_not_unique')
        event = pm[0]
        moneylines = [m for m in event['markets'] if m.get('sportsMarketType') == 'moneyline']
        if len(moneylines) != 1:
            raise ValueError('exact_PM_moneyline_not_unique')
        market = moneylines[0]
        tokens = json.loads(market['clobTokenIds']) if isinstance(market['clobTokenIds'], str) else market['clobTokenIds']
        outcomes = json.loads(market['outcomes']) if isinstance(market['outcomes'], str) else market['outcomes']
        if len(tokens) != 2 or len(set(tokens)) != 2 or len(outcomes) != 2 or not all(str(t).isdigit() for t in tokens):
            raise ValueError('invalid_PM_binary_tokens')
        native = [m for m in markets if m['event_ticker'] == native_event(fixture)]
        if len(native) != 2:
            raise ValueError('exact_Kalshi_fixture_does_not_have_two_moneylines')
        mapped = []
        for team in event['teams']:
            if team['alias'] not in outcomes:
                raise ValueError('PM_outcome_alias_not_exact')
            official_code = fixture['away_code'] if team['name'] == fixture['away'] else fixture['home_code']
            code = ALIASES.get(official_code, official_code)
            found = [m for m in native if m['ticker'].endswith('-' + code)]
            if len(found) != 1:
                raise ValueError('Kalshi_selected_team_not_unique')
            mapped.append({'kalshi_ticker': found[0]['ticker'], 'polymarket_token': str(tokens[outcomes.index(team['alias'])]),
                           'team': team['name'], 'normal_game_identity_matched': True,
                           'exceptional_payoff_parity_verified': False})
        result.append({'fixture': fixture, 'kalshi_event_ticker': native_event(fixture), 'polymarket_event_id': event['id'],
                       'polymarket_event_slug': event['slug'], 'polymarket_startTime': event.get('startTime'),
                       'polymarket_eventWeek_ignored': event.get('eventWeek'), 'moneyline_identity_candidates': mapped,
                       'polymarket_moneyline_feesEnabled': market.get('feesEnabled'),
                       'polymarket_moneyline_feeSchedule': market.get('feeSchedule'),
                       'historical_fee_effective_date_verified': False,
                       'fullgame_nonplayer_PM_market_counts': {kind: sum(m.get('sportsMarketType') == kind for m in event['markets'])
                                                              for kind in ('moneyline', 'spreads', 'totals', 'team_totals')}})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--schedule', type=Path, default=ROOT / 'config/nfl_playoffs_history_2026.json')
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    inventory = {}
    def source(name):
        path = args.archive / (name + '.json.gz')
        inventory[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
        with gzip.open(path, 'rt') as handle:
            env = json.load(handle)
        if env['status'] != 200:
            raise ValueError('unsuccessful_exchange_source')
        return env['payload']
    native = source('kalshi_series')
    if native.get('cursor'):
        raise ValueError('native_series_page_truncated')
    fixtures = review(json.loads(args.schedule.read_text()), native['markets'], source('polymarket_events'))
    k, p = source('kalshi_candle'), source('polymarket_candle')
    if not k['candlesticks'] or not p['history']:
        raise ValueError('tiny_history_probe_empty')
    result = {'schema_version': 1, 'sport': 'NFL', 'fixture_identity_count': len(fixtures),
              'moneyline_identity_candidates': sum(len(f['moneyline_identity_candidates']) for f in fixtures),
              'fixtures': fixtures, 'tiny_history_probe': {'kalshi_candles': len(k['candlesticks']),
                   'polymarket_history_points': len(p['history']), 'fixture': '2026-01-10 Rams at Panthers',
                   'query_window_UTC': ['2026-01-10T18:00:00Z', '2026-01-10T19:00:00Z'],
                   'coverage_scope': 'One fixture, one pregame hour; not complete multi-fixture price history'},
              'inventory_sha256': inventory, 'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'exceptional_payoff_parity_verified': False, 'historical_fee_effective_dates_verified': False,
              'three_source_pricing_ready': False, 'orders_enabled': False}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({key: result[key] for key in ('fixture_identity_count', 'moneyline_identity_candidates', 'tiny_history_probe')}))


if __name__ == '__main__':
    main()

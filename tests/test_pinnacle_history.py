from datetime import datetime, timezone
import gzip
import json

import pytest

from src.combos.pinnacle_history import PinnacleHistory

BASE = datetime(2026, 9, 1, tzinfo=timezone.utc).timestamp()


def stamp(seconds):
    return datetime.fromtimestamp(BASE + seconds, timezone.utc).isoformat()


def write_gz(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, 'wt') as stream:
        json.dump(value, stream)


def fixture_files(tmp_path, markets, *, inactive=False, mismatch=False):
    native = {'fixtureId': 'f1', 'statusId': 0, 'startTime': stamp(1000),
              'participant1Name': 'Miami Hurricanes', 'participant1ShortName': 'Miami',
              'participant2Name': 'Bears', 'participant2ShortName': 'Bears'}
    (tmp_path / 'fixtures.json').write_text(json.dumps({'payload': [native]}))
    # Deliberately no PM token, fee, price, depth or matched payoff status.
    mappings = {ticker: {'status': 'payoff_unmatched', 'teams': ['bears', 'miamifl'],
                         'start_time': stamp(1001 if mismatch else 1000)} for ticker in markets}
    (tmp_path / 'polymarket_mapping.json').write_text(json.dumps(mappings))
    for ticker, market in markets.items():
        write_gz(tmp_path / 'markets' / f'{ticker}.json.gz', {'payload': {'market': {'ticker': ticker, **market}}})
    rows_yes = [{'createdAt': stamp(0), 'price': 2., 'active': True},
                {'createdAt': stamp(10), 'price': 1.5, 'active': True}]
    rows_no = [{'createdAt': stamp(0), 'price': 2., 'active': True}]
    if inactive:
        rows_no.append({'createdAt': stamp(20), 'price': 2., 'active': False})
    catalog = [{'marketId': 1, 'marketType': 'moneyline', 'handicap': 0, 'period': 'result',
                'playerProp': False, 'outcomes': [{'outcomeName': '1', 'outcomeId': 1},
                                                 {'outcomeName': '2', 'outcomeId': 2}]},
               {'marketId': 2, 'marketType': 'spreads', 'handicap': -3.5, 'period': 'result',
                'playerProp': False, 'outcomes': [{'outcomeName': '1', 'outcomeId': 3},
                                                 {'outcomeName': '2', 'outcomeId': 4}]}]
    (tmp_path / 'catalog.json').write_text(json.dumps(catalog))
    native_markets = {}
    for item in catalog:
        a, b = [str(o['outcomeId']) for o in item['outcomes']]
        native_markets[str(item['marketId'])] = {'outcomes': {a: {'players': {'0': rows_yes}}, b: {'players': {'0': rows_no}}}}
    write_gz(tmp_path / 'history' / 'f1.json.gz', {'payload': {'fixtureId': 'f1',
              'bookmakers': {'pinnacle+30': {'markets': native_markets}}}})
    return PinnacleHistory(tmp_path, market_dir=tmp_path / 'markets', catalog_path=tmp_path / 'catalog.json')


def test_independent_history_is_causal_and_inactive_fails_closed(tmp_path):
    ticker = 'KXNCAAFGAME-test'
    history = fixture_files(tmp_path, {ticker: {'yes_sub_title': 'Miami FL'}}, inactive=True)
    assert ticker in history.maps  # Future/unsettled game and unmatched PM payoff still qualify.
    with pytest.raises(ValueError, match='no_prior_state'):
        history.at(ticker, BASE + 29)
    assert history.at(ticker, BASE + 39)['interval']['point'] == .5
    updated = history.at(ticker, BASE + 40)
    assert updated['interval']['point'] == pytest.approx(4 / 7)
    assert updated['source_at'] == BASE
    assert updated['source_provenance']['available_at_assumption'] == BASE + 40
    with pytest.raises(ValueError, match='inactive_latest_state'):
        history.at(ticker, BASE + 50)


def test_native_spread_signs_and_integer_line_rejection(tmp_path):
    home, away, integer = ('KXNCAAFSPREAD-home', 'KXNCAAFSPREAD-away', 'KXNCAAFSPREAD-integer')
    history = fixture_files(tmp_path, {
        home: {'yes_sub_title': 'Miami FL wins by over 3.5 points', 'floor_strike': 3.5},
        away: {'yes_sub_title': 'Bears wins by over -3.5 points', 'floor_strike': -3.5},
        integer: {'yes_sub_title': 'Miami FL wins by over 3 points', 'floor_strike': 3},
    })
    assert history.maps[home]['native_yes_outcome_id'] == '3'
    assert history.maps[away]['native_yes_outcome_id'] == '4'
    assert integer not in history.maps
    assert history.at(home, BASE + 40)['interval']['point'] == pytest.approx(4 / 7)
    assert history.at(away, BASE + 40)['interval']['point'] == pytest.approx(3 / 7)


def test_alias_requires_exact_fixture_time_and_pregame_cutoff(tmp_path):
    ticker = 'KXNCAAFGAME-test'
    history = fixture_files(tmp_path, {ticker: {'yes_sub_title': 'Miami FL'}})
    assert history.at(ticker, BASE + 939)['interval']['point'] == pytest.approx(4 / 7)
    with pytest.raises(ValueError, match='pregame_cutoff'):
        history.at(ticker, BASE + 940)
    mismatch = fixture_files(tmp_path, {ticker: {'yes_sub_title': 'Miami FL'}}, mismatch=True)
    assert not mismatch.maps
    assert mismatch.exclusions[0]['reason'] == 'no_exact_fixture_identity'


def test_conflicting_unused_native_market_does_not_poison_fixture(tmp_path):
    moneyline, spread = 'KXNCAAFGAME-test', 'KXNCAAFSPREAD-test'
    fixture_files(tmp_path, {moneyline: {'yes_sub_title': 'Miami FL'},
                            spread: {'yes_sub_title': 'Miami FL wins by over 3.5 points', 'floor_strike': 3.5}})
    path = tmp_path / 'history' / 'f1.json.gz'
    with gzip.open(path, 'rt') as stream:
        envelope = json.load(stream)
    conflicting = envelope['payload']['bookmakers']['pinnacle+30']['markets']['2']['outcomes']['3']['players']['0']
    conflicting.append({**conflicting[0], 'active': False})
    write_gz(path, envelope)
    history = PinnacleHistory(tmp_path, market_dir=tmp_path / 'markets', catalog_path=tmp_path / 'catalog.json')
    assert moneyline in history.maps
    assert spread not in history.maps
    assert history.at(moneyline, BASE + 30)['interval']['point'] == .5
    assert history.market_exclusions == [{'fixture_id': 'f1', 'native_market_id': '2',
                                          'reason': 'conflicting historical state timestamp'}]

from copy import deepcopy
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from combos.nfl_matching import build_mappings, polymarket_fee, kalshi_rates


def definitions():
    # The real opener crosses midnight UTC. eventDate is its Eastern date;
    # startDate and Kalshi expiry describe different times entirely.
    def km(series, suffix, team=None, line=None):
        return {'ticker': series + '-26SEP09NESEA-' + suffix, 'event_ticker': series + '-26SEP09NESEA',
            'custom_strike': {'football_team': team} if team else None, 'floor_strike': line,
            'status': 'active', 'rules_primary': 'Team wins' if line is None else f'If score is more than {line} points',
            'rules_secondary': 'Ties resolve to $0.50 for each team.'}
    kalshi = [km('KXNFLGAME', 'NE', 'ne-id'), km('KXNFLGAME', 'SEA', 'sea-id'),
              km('KXNFLSPREAD', 'SEA4', 'sea-id', 3.5), km('KXNFLTOTAL', '42', line=41.5)]
    pm = [{'id': '1', 'sportsMarketType': 'moneyline', 'outcomes': '["Patriots","Seahawks"]', 'clobTokenIds': '["11","12"]',
           'description': 'If Patriots wins, the market will resolve to "Patriots".\nIf Seahawks wins, the market will resolve to "Seahawks".\nA tie resolves 50-50.'},
          {'id': '2', 'sportsMarketType': 'spreads', 'line': -3.5, 'outcomes': '["Seahawks","Patriots"]', 'clobTokenIds': '["21","22"]',
           'description': 'This market will resolve to "Seahawks" if the Seahawks win the game by 4 or more points. Otherwise, this market will resolve to "Patriots".'},
          {'id': '3', 'sportsMarketType': 'totals', 'line': 41.5, 'outcomes': '["Over","Under"]', 'clobTokenIds': '["31","32"]',
           'description': 'This market will resolve to "Over" if the teams combine to score 42 or more points. If the combined total is less than 42, this market will resolve to "Under".'}]
    for m in pm:
        m.update(active=True, closed=False, acceptingOrders=True, conditionId='condition-' + m['id'],
                 feeSchedule={'rate': .05, 'exponent': 1, 'takerOnly': True}, feesEnabled=True)
    event = {'seriesSlug': 'nfl-2026', 'eventWeek': 1, 'eventDate': '2026-09-09', 'startTime': '2026-09-10T00:20:00Z',
             'startDate': '2026-07-30T00:00:00Z', 'slug': 'nfl-ne-sea-2026-09-10',
             'teams': [{'league': 'nfl', 'abbreviation': 'ne', 'alias': 'Patriots', 'name': 'New England Patriots'},
                       {'league': 'nfl', 'abbreviation': 'sea', 'alias': 'Seahawks', 'name': 'Seattle Seahawks'}], 'markets': pm}
    series = {s: {'fee_type': 'quadratic_with_maker_fees', 'fee_multiplier': 1} for s in ('KXNFLGAME', 'KXNFLSPREAD', 'KXNFLTOTAL')}
    return kalshi, [event], series


def build(data):
    return build_mappings(*data, 2026, 1)


def test_exact_outcomes_kickoff_and_half_point_lines():
    mappings, review = build(definitions())
    assert review['matched'] == {'moneyline': 2, 'spreads': 1, 'totals': 1}
    assert [m['polymarket_yes_token'] for m in mappings] == ['11', '12', '21', '31']
    assert all(m['start_at'] == 1788999600 for m in mappings)
    assert all(m['pricing_block_reason'] == 'pinnacle_payoff_mapping_unreviewed' for m in mappings)
    assert all(m['fees']['polymarket']['rate'] == .05 for m in mappings)


@pytest.mark.parametrize('field,value,reason', [('seriesSlug','nfl-2025','season'), ('eventWeek',2,'week'),
    ('eventDate','2026-09-10','eastern_event_date')])
def test_wrong_season_week_or_utc_date_is_rejected(field, value, reason):
    data = definitions(); data[1][0][field] = value
    with pytest.raises(ValueError, match=reason): build(data)


def test_line_sign_and_rules_must_agree_no_nearest_line_substitution():
    data = definitions(); data[1][0]['markets'][1]['line'] = 3.5
    mappings, review = build(data)
    assert not any(m['market_type'] == 'spreads' for m in mappings)
    assert review['rejected_polymarket'][0]['reason'] == 'spread_line_and_rules_disagree'
    data = definitions(); data[1][0]['markets'][2]['line'] = 42.5
    mappings, review = build(data)
    assert not any(m['market_type'] == 'totals' for m in mappings)
    assert review['rejected_polymarket'][0]['reason'] == 'total_line_and_rules_disagree'


def test_outcome_one_handicap_and_unknown_complement():
    data = definitions(); m = data[1][0]['markets'][1]
    m.update(outcomes='["Patriots","Seahawks"]', clobTokenIds='["22","21"]', line=3.5)
    mappings, _ = build(data)
    assert next(m for m in mappings if m['market_type'] == 'spreads')['polymarket_yes_token'] == '21'
    m.update(outcomes='["Seahawks","Unknown"]', line=-3.5)
    mappings, _ = build(data)
    assert not any(m['market_type'] == 'spreads' for m in mappings)


def test_integer_push_or_duplicate_payoff_does_not_map():
    data = definitions(); data[1][0]['markets'][2]['line'] = 42
    mappings, review = build(data)
    assert len(mappings) == 3 and 'push_model' in review['rejected_polymarket'][0]['reason']
    data = definitions(); dupe = deepcopy(data[1][0]['markets'][2]); dupe['id'] = '4'
    data[1][0]['markets'].append(dupe)
    mappings, review = build(data)
    assert len(mappings) == 3 and any(u['reason'] == 'ambiguous_exact_payoff' for u in review['unmatched'])


def test_market_fee_schedule_overrides_legacy_fee_rate():
    m = definitions()[1][0]['markets'][0]; m.update(maker_base_fee=1000, taker_base_fee=1000)
    assert polymarket_fee(m) == .05
    m['feeSchedule']['exponent'] = 2
    with pytest.raises(ValueError, match='unsupported'): polymarket_fee(m)
    assert kalshi_rates({'fee_type':'quadratic', 'fee_multiplier':1}) == {'maker':0, 'taker':.07}
    assert kalshi_rates({'fee_type':'quadratic_with_combo_maker_fees', 'fee_multiplier':1})['maker'] == .035


def test_moneyline_ties_must_pay_half_and_periods_cannot_mix():
    data = definitions(); data[1][0]['markets'][0]['description'] = 'Ties refund stakes.'
    data[1][0]['markets'][1]['description'] += ' First half only.'
    mappings, _ = build(data)
    assert [m['market_type'] for m in mappings] == ['totals']

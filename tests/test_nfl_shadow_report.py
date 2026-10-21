import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from nfl_shadow_report import summarize


def test_report_separates_scope_freshness_and_quotes():
    mappings = [
        {'kalshi_ticker': 'A', 'sport': 'NFL', 'player_prop': False, 'fixture_key': 'f1'},
        {'kalshi_ticker': 'B', 'sport': 'NFL', 'player_prop': False, 'fixture_key': 'f2'},
    ]
    decisions = [
        {'status': 'skipped', 'reason': 'polymarket: future or stale', 'leg_count': 2,
         'received_at': 120, 'request': {'mve_selected_legs': [{'market_ticker': 'A'}, {'market_ticker': 'B'}]}},
        {'status': 'shadow_quote', 'leg_count': 2, 'received_at': 180, 'rfq_id': 'q', 'quantity': 10,
         'yes_ask': .2, 'economics': {'customer_premium': 2, 'expected_edge': .1, 'maximum_loss': 8},
         'request': {'mve_selected_legs': [{'market_ticker': 'A'}, {'market_ticker': 'B'}]}},
    ]
    result = summarize(decisions, [{'venue': 'pinnacle', 'active': True}], mappings, event_count=3)
    assert result['scope'] == {'two_to_four_nonplayer_nfl': 2, 'mapped_cross_fixture': 2}
    assert result['freshness_rejections'] == {'polymarket: future or stale': 1}
    assert result['quote_count'] == 1
    assert result['quotes'][0]['expected_edge'] == .1

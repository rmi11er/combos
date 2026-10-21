import sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from combos.cfb_market_scope import classify_combo


def market(*series):
    return {'mve_selected_legs':[{'event_ticker':s+'-26SEP05TEST','side':'no'} for s in series]}


def test_more_than_two_legs_and_no_side_are_retained():
    c=classify_combo(market('KXNCAAFGAME','KXNCAAFSPREAD','KXNCAAFTOTAL'))
    assert c['scope']=='full_game_only' and c['nlegs']==3


def test_team_and_period_markets_are_not_player_props():
    assert classify_combo(market('KXNCAAFGAME','KXNCAAFTEAMTOTAL'))['scope']=='team_total_extension'
    c=classify_combo(market('KXNCAAF1HSPREAD','KXNCAAFTEAMTOTAL'))
    assert c['scope']=='team_total_and_period' and not c['has_player_prop']
    assert classify_combo(market('KXNCAAFGAME','KXNCAAF1Q'))['scope']=='period_extension'


def test_unknown_series_and_mixed_sports_are_not_silently_classified():
    for s in ('KXNCAAFUNKNOWN','KXNFLPASSYDS'):
        with pytest.raises(ValueError,match='unreviewed'):
            classify_combo(market('KXNCAAFGAME',s))

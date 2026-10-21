import pytest

from combos.event_types import infer_event_type, validate_event_type
from combos.settlement_policy import settlement_policy


def test_legacy_mapping_gets_stable_versioned_event_type():
    mapping = {'market_type': 'spreads', 'period': 'full_game'}
    assert infer_event_type(mapping).name == 'nfl.full_game.spread'
    assert settlement_policy(mapping) == 'nfl.full_game.spread:v1'


def test_explicit_event_type_rejects_cross_family_mapping():
    with pytest.raises(ValueError, match='market family'):
        validate_event_type({'event_type': 'nfl.full_game.total', 'market_type': 'spreads', 'period': 'full_game'})

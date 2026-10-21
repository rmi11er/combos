"""Shared launch universe. Collection screens candidates; pricing checks mappings."""
import math
from .market_families import NFL_SERIES, family_for_ticker


def validate_scope(config):
    lo, hi = config.get('minimum_legs', 2), config.get('maximum_legs', 4)
    if type(lo) is not int or type(hi) is not int or not 2 <= lo <= hi <= 4:
        raise ValueError('supported_leg_range_is_two_through_four')
    if config.get('pregame_only', True) is not True:
        raise ValueError('launch_requires_pregame_only')
    cutoff = config.get('pregame_cutoff_seconds', 60.)
    if not math.isfinite(cutoff) or cutoff < 60:
        raise ValueError('pregame_cutoff_must_be_at_least_60_seconds')


def check_legs(legs, config):
    if not config.get('minimum_legs', 2) <= len(legs) <= config.get('maximum_legs', 4):
        raise ValueError('outside_leg_count_scope')
    if any(not isinstance(l, dict) or not l.get('market_ticker') or l.get('side') not in ('yes', 'no') for l in legs):
        raise ValueError('invalid_legs')
    if any(l.get('yes_settlement_value_dollars') not in (None, '') for l in legs):
        raise ValueError('settled_leg_requires_scalar_pricing')
    if config['sport'] == 'NFL':
        if any(not l['market_ticker'].startswith('KXNFL') for l in legs):
            raise ValueError('outside_sport_scope')
        if any(l['market_ticker'].split('-', 1)[0] not in NFL_SERIES for l in legs):
            raise ValueError('outside_supported_non_player_scope')


def collection_candidate(legs, config):
    try:
        check_legs(legs, config)
        return True
    except (ValueError, TypeError, KeyError):
        return False


def check_mappings(legs, mappings, config):
    if any(not m for m in mappings):
        raise ValueError('reviewed_mapping_missing')
    if any(m['sport'] != config['sport'] for m in mappings):
        raise ValueError('outside_sport_scope')
    if len({m['fixture_key'] for m in mappings}) != len(legs):
        raise ValueError('same_fixture_joint_model_required')
    if config['sport'] == 'NFL':
        for leg,mapping in zip(legs,mappings):
            family=family_for_ticker(leg['market_ticker'])
            if mapping.get('market_type')!=family.market_type or mapping.get('period','full_game')!=family.period:
                raise ValueError('mapping_market_type_or_period_mismatch')
            if mapping.get('player_prop',False) is not False:raise ValueError('player_prop_excluded')


def check_start(mapping, status, at, config):
    # Scope enforcement does not depend on the choice of fair/weighting model.
    if status.get('started') or status.get('phase', 'pregame') != 'pregame':
        raise ValueError('pregame_only')
    if at >= mapping['start_at'] - config.get('pregame_cutoff_seconds', 60.):
        raise ValueError('pregame_cutoff')

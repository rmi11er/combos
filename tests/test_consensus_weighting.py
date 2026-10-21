from dataclasses import replace

import pytest

from combos.observations import Observation, VENUES
from combos.pricing import Interval
from combos.weighted_fair import WeightPolicy, weighted_fair


def books(points, depths=(10000, 100, 100)):
    return [Observation('same-payoff', v, 100, 100, True,
                        Interval(p-.001, p, p+.001), d, d, 'source', 'mapping', 'fee')
            for v, p, d in zip(VENUES, points, depths)]


def price(points, **kwargs):
    return weighted_fair(books(points), 100, 'pregame',
                         WeightPolicy(delayed_pinnacle=True, consensus_lean_enabled=True, **kwargs))


@pytest.mark.parametrize('points,direction', [((.53, .5, .502), -1), ((.47, .5, .502), 1)])
def test_isolated_kalshi_lean_is_liquidity_weighted_and_capped(points, direction):
    result = price(points)
    audit = result['consensus_lean']
    assert audit['detected'] and audit['applied']
    assert direction*audit['point_adjustment_cents'] > 0
    assert audit['final_weights']['kalshi'] < audit['base_weights']['kalshi']
    assert sum(audit['final_weights'].values()) == pytest.approx(1)
    assert audit['final_weights']['pinnacle'] <= .2+1e-12
    assert max(audit['final_weights'].values()) <= .6+1e-12
    assert result['guard']['additional_pinnacle_score_multiplier'] == 1
    assert audit['base_weights']['kalshi'] != pytest.approx(1/3)


@pytest.mark.parametrize('points', [(.51, .50, .53), (.501, .50, .502), (.502, .50, .501)])
def test_no_consensus_or_insignificant_gap_does_not_lean(points):
    assert not price(points)['consensus_lean']['detected']


def test_hard_disagreement_still_blocks():
    result = price((.60, .50, .502))
    assert not result['guard']['quote_allowed']
    assert not result['consensus_lean']['applied']


def test_stale_sources_still_rejected():
    observations = books((.53, .5, .502))
    observations[1] = replace(observations[1], observed_at=80)
    with pytest.raises(ValueError, match='stale'):
        weighted_fair(observations, 100, 'pregame',
                      WeightPolicy(delayed_pinnacle=True, consensus_lean_enabled=True))


def test_frozen_policy_remains_opt_out():
    result = weighted_fair(books((.53, .5, .502)), 100, 'pregame', WeightPolicy(delayed_pinnacle=True))
    assert not result['consensus_lean']['enabled']
    assert result['guard']['additional_pinnacle_score_multiplier'] == .25


def test_two_sources_do_not_imply_three_source_agreement():
    result = weighted_fair(books((.53, .5, .502))[1:], 100, 'pregame',
                          WeightPolicy(allow_partial_venues=True, consensus_lean_enabled=True))
    assert not result['consensus_lean']['detected']


def test_caps_without_headroom_do_not_force_transfer():
    result = price((.53, .5, .502), maximum_venue_weight=.4)
    assert result['consensus_lean']['detected']
    assert not result['consensus_lean']['applied']


@pytest.mark.parametrize('kwargs', [dict(consensus_lean_enabled=1),
    dict(consensus_maximum_transfer_fraction=.51), dict(consensus_agreement_cents=float('nan'))])
def test_invalid_policy(kwargs):
    with pytest.raises(ValueError):
        WeightPolicy(**kwargs)

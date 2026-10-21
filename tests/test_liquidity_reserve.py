from dataclasses import replace
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from combos.liquidity_reserve import LegLiquidity, VenueLiquidity, liquidity_reserve
from combos.pricing import Interval


def legs(depth=100., width=2.):
    sources = tuple(VenueLiquidity(v, 1/3, width, depth, 'synthetic',
        'verified_USD_stake_limit_converted_to_payout' if v == 'pinnacle' else 'top_of_book')
        for v in ('kalshi', 'polymarket', 'pinnacle'))
    return [LegLiquidity(str(i), Interval(.49, .5, .51), sources, 'synthetic_validated_context') for i in range(2)]


def test_thinner_wider_and_larger_require_more_reserve_without_moving_fair():
    base = liquidity_reserve(legs(), 100., 0.)
    for inputs, q in ((legs(depth=10.), 100.), (legs(width=4.), 100.), (legs(), 1000.)):
        result = liquidity_reserve(inputs, q, 0.)
        assert result['incremental_reserve_per_contract'] > base['incremental_reserve_per_contract']
        assert result['after']['joint']['point'] == base['after']['joint']['point']
    assert not base['orders_enabled'] and not base['calibrated']
    assert base['incremental_reserve_dollars'] == 100. * base['incremental_reserve_per_contract']


def test_existing_wider_uncertainty_is_credited_not_charged_twice():
    inputs = [replace(leg, interval=Interval(.4, .5, .6)) for leg in legs()]
    result = liquidity_reserve(inputs, 100., 0.)
    assert result['incremental_reserve_per_contract'] == 0.
    assert result['before'] == result['after']


def test_complement_symmetry_and_bounded_intervals():
    inputs = [replace(leg, interval=Interval(.05, .1, .12)) for leg in legs(depth=.001)]
    result = liquidity_reserve(inputs, 100., .1)
    assert all(leg['after']['lower'] == 0. and leg['after']['upper'] == 1. for leg in result['legs'])
    inputs = [replace(leg, interval=Interval(.7, .8, .85)) for leg in legs()]
    opposite = [replace(leg, interval=Interval(1-leg.interval.upper, 1-leg.interval.point, 1-leg.interval.lower)) for leg in inputs]
    a, b = (liquidity_reserve(x, 100., 0.) for x in (inputs, opposite))
    assert a['legs'][0]['after']['upper'] == pytest.approx(1-b['legs'][0]['after']['lower'])


@pytest.mark.parametrize('quantity', [0., -1., float('nan'), float('inf')])
def test_invalid_sizes(quantity):
    with pytest.raises(ValueError):
        liquidity_reserve(legs(), quantity, 0.)


def test_imputation_requires_explicit_historical_scenario_and_never_pinnacle():
    inputs = legs()
    inputs[0] = replace(inputs[0], venues=(replace(inputs[0].venues[0], capacity_kind='historical_assumption'), *inputs[0].venues[1:]))
    with pytest.raises(ValueError, match='capacity'):
        liquidity_reserve(inputs, 100., 0.)
    assert liquidity_reserve(inputs, 100., 0., historical_assumption_reference='synthetic_scenario')['historical_assumption_reference']
    inputs[0] = replace(inputs[0], venues=tuple(replace(v, capacity_kind='historical_assumption') for v in inputs[0].venues))
    with pytest.raises(ValueError, match='capacity'):
        liquidity_reserve(inputs, 100., 0., historical_assumption_reference='synthetic_scenario')


def test_bad_weights_and_duplicate_payoffs_rejected():
    inputs = legs()
    with pytest.raises(ValueError, match='distinct'):
        liquidity_reserve([inputs[0], inputs[0]], 100., 0.)
    inputs[0] = replace(inputs[0], venues=(replace(inputs[0].venues[0], weight=.9), *inputs[0].venues[1:]))
    with pytest.raises(ValueError, match='normalized'):
        liquidity_reserve(inputs, 100., 0.)

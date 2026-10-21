"""Conditional consensus is a bounded, causal hypothesis, not quote permission."""
from dataclasses import replace
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from combos.consensus_anchor import ConsensusObservation, ConsensusPolicy, ConsensusRequest, evaluate_consensus
from combos.fees import taker_fee_context
from combos.pricing import Interval, pinnacle_fair


def source(venue, point=.5):
    pin = venue == 'pinnacle'
    raw_bid, raw_ask = round(point - .005, 4), round(point + .005, 4)
    rate = .035 if venue == 'kalshi' else .05
    if pin:
        yes, no = 1 / (point * 1.04), 1 / ((1 - point) * 1.04)
        interval = pinnacle_fair(yes, no)
    else:
        fee = taker_fee_context(venue, raw_bid, raw_ask, 100., 200., rate)
        interval = Interval(raw_bid - fee['sides']['bid']['conservative_fee_per_share'], point,
                            raw_ask + fee['sides']['ask']['conservative_fee_per_share'])
    return ConsensusObservation(
        venue=venue, canonical_payoff_key='mlb:fixture:home_win', payoff_rules_key='synthetic:verified_fullgame_rules',
        quoted_side='yes', mapping_verified=True, mapping_reference='synthetic:reviewed_mapping', mapping_available_at=900.,
        source_reference='synthetic:' + venue, information_at=970. if pin else 995., available_at=1000. if pin else 996.,
        information_clock='snapshot_information_time', information_clock_reference='synthetic:verified_provider_snapshot',
        active=True, interval=interval, bid_capacity=100., ask_capacity=200., capacity_unit='payout_dollars',
        capacity_kind='verified_USD_stake_limit_converted_to_payout' if pin else 'top_of_book',
        capacity_reference='synthetic:actual_capacity', capacity_imputed=False,
        depth_information_at=970. if pin else 995., depth_available_at=1000. if pin else 996.,
        raw_bid=None if pin else raw_bid, raw_ask=None if pin else raw_ask, taker_rate=None if pin else rate,
        fee_model='bookmaker_margin_in_interval' if pin else 'venue_cash_v2',
        fee_reference=None if pin else 'synthetic:dated_fee_schedule', fee_schedule_verified=not pin,
        fee_valid_from=None if pin else 0., fee_valid_until=None if pin else 2000.,
        balance_precision='.0001' if venue == 'kalshi' else None,
        decimal_odds_selected=yes if pin else None, decimal_odds_other=no if pin else None,
        price_changed_at=100.)


def request(k=.52, pm=.5, pin=.5):
    sources = (source('kalshi', k), source('polymarket', pm), source('pinnacle', pin))
    point = .4 * k + .3 * pm + .3 * pin
    return ConsensusRequest('mlb:fixture:home_win', 'synthetic:verified_fullgame_rules', 1000., 2000.,
                            'pregame', 'live', Interval(point - .05, point, point + .05),
                            {'kalshi': .4, 'polymarket': .3, 'pinnacle': .3}, 'synthetic:baseline', sources)


def changed(req, venue, **fields):
    return replace(req, observations=tuple(replace(o, **fields) if o.venue == venue else o for o in req.observations))


def test_agreeing_anchors_tilt_normalized_weights_without_quote_permission_or_narrowing():
    req = request()
    result = evaluate_consensus(replace(req, baseline_weights={'kalshi': 4., 'polymarket': 3., 'pinnacle': 3.}))
    assert result['activated']
    assert sum(result['effective_weights'].values()) == pytest.approx(1.)
    assert result['effective_weights']['kalshi'] < .4
    assert result['candidate_interval']['point'] < req.baseline_interval.point
    assert result['candidate_interval']['lower'] <= req.baseline_interval.lower
    assert result['candidate_interval']['upper'] >= req.baseline_interval.upper
    assert 0 < result['lean_fraction'] <= .25
    assert not result['execution_authorized'] and not result['quote_guard_override']
    json.dumps(result, allow_nan=False)


def test_fee_band_overlap_can_activate_and_kalshi_fees_need_not_exceed_polymarket():
    result = evaluate_consensus(request())
    assert result['activated']
    assert result['features']['kalshi_overlaps_both_anchor_fee_bands']
    assert result['features']['kalshi_minus_polymarket_fee_expanded_width_cents'] < 0
    assert not result['features']['inventory_or_flow_cause_observed']


@pytest.mark.parametrize('k,pm,pin,reason', [
    (.52, .50, .515, 'pinnacle_polymarket_points_do_not_agree'),
    (.502, .504, .500, 'kalshi_not_isolated_from_both_anchors'),
    (.501, .500, .500, 'kalshi_disagreement_below_fixed_threshold'),
    (.55, .500, .500, 'kalshi_disagreement_exceeds_modest_scope'),
])
def test_fixed_agreement_isolation_and_modest_gap_requirements(k, pm, pin, reason):
    result = evaluate_consensus(request(k, pm, pin))
    assert not result['activated'] and reason in result['reasons']


def test_missing_pinnacle_never_becomes_two_exchange_consensus():
    req = request()
    result = evaluate_consensus(replace(req, observations=req.observations[:2]))
    assert not result['activated']
    assert result['candidate_interval']['point'] == req.baseline_interval.point
    assert 'all_three_distinct_sources_required_no_consensus_fallback' in result['reasons']


@pytest.mark.parametrize('venue,fields,reason', [
    ('kalshi', {'available_at': 1001.}, 'future_or_invalid_source_clock'),
    ('kalshi', {'mapping_available_at': 1001.}, 'future_or_invalid_source_clock'),
    ('kalshi', {'depth_information_at': 970.}, 'stale_price_or_depth_snapshot'),
    ('pinnacle', {'information_at': 980.}, 'pinnacle_delay_not_reflected_in_availability'),
    ('pinnacle', {'information_at': 900.}, 'stale_price_or_depth_snapshot'),
    ('pinnacle', {'information_clock': 'last_price_change'}, 'verified_snapshot_information_clock_required'),
    ('polymarket', {'capacity_imputed': True}, 'real_two_sided_capacity_required'),
    ('polymarket', {'ask_capacity': 0.}, 'positive_two_sided_payout_capacity_required'),
    ('pinnacle', {'capacity_kind': 'unknown_currency_limit'}, 'verified_pinnacle_limit_units_required'),
])
def test_causal_information_and_real_depth_requirements(venue, fields, reason):
    result = evaluate_consensus(changed(request(), venue, **fields))
    assert not result['activated']
    assert any(reason in r for r in result['reasons'])


def test_old_last_price_change_is_not_stale_snapshot_and_extra_pinnacle_age_reduces_lean():
    fresh = evaluate_consensus(changed(request(), 'pinnacle', price_changed_at=0.))
    old = evaluate_consensus(changed(request(), 'pinnacle', information_at=940., depth_information_at=940.))
    assert fresh['activated'] and old['activated']
    assert fresh['sources']['pinnacle']['price_change_age_seconds'] == 1000.
    assert fresh['sources']['pinnacle']['snapshot_age_seconds'] == 30.
    assert old['lean_fraction'] < fresh['lean_fraction']


@pytest.mark.parametrize('fields,reason', [
    ({'canonical_payoff_key': 'different_fixture'}, 'unverified_or_mismatched_canonical_payoff'),
    ({'payoff_rules_key': 'different_void_rules'}, 'unverified_or_mismatched_canonical_payoff'),
    ({'mapping_verified': False}, 'unverified_or_mismatched_canonical_payoff'),
    ({'quoted_side': 'buy'}, 'invalid_quoted_side'),
    ({'fee_schedule_verified': False}, 'verified_market_specific_cash_fee_schedule_required'),
    ({'fee_valid_until': 999.}, 'fee_schedule_not_effective_for_decision'),
    ({'taker_rate': .07}, 'fee_or_bookmaker_interval_mismatch'),
    ({'balance_precision': None}, 'verified_kalshi_balance_precision_required'),
])
def test_mapping_side_and_exact_fee_expansion_gates(fields, reason):
    result = evaluate_consensus(changed(request(), 'kalshi', **fields))
    assert not result['activated'] and any(reason in r for r in result['reasons'])


def test_opposite_quoted_side_normalizes_book_probability_and_depth_orientation():
    req = request(.61, .59, .59)
    baseline = evaluate_consensus(req)
    opposite = source('kalshi', .39)
    opposite = replace(opposite, quoted_side='no', bid_capacity=200., ask_capacity=100.)
    fee = taker_fee_context('kalshi', opposite.raw_bid, opposite.raw_ask, 200., 100., opposite.taker_rate)
    opposite = replace(opposite, interval=Interval(opposite.raw_bid - fee['sides']['bid']['conservative_fee_per_share'], .39,
                                                  opposite.raw_ask + fee['sides']['ask']['conservative_fee_per_share']))
    converted = evaluate_consensus(replace(req, observations=(opposite, *req.observations[1:])))
    assert baseline['activated'] and converted['activated']
    assert converted['candidate_interval']['point'] == pytest.approx(baseline['candidate_interval']['point'])
    assert converted['sources']['kalshi']['bid_capacity_payout_dollars'] == 100.
    assert converted['sources']['kalshi']['ask_capacity_payout_dollars'] == 200.


def test_pregame_cutoff_and_baseline_weight_evidence_are_required():
    req = request()
    assert not evaluate_consensus(replace(req, scheduled_start_at=1060.))['activated']
    assert not evaluate_consensus(replace(req, phase='in_play'))['activated']
    result = evaluate_consensus(replace(req, baseline_interval=Interval(.3, .4, .6)))
    assert 'baseline_point_does_not_match_recorded_normalized_weights' in result['reasons']


def test_invalid_policy_bounds_and_no_extra_pinnacle_taker_fee():
    for fields in ({'maximum_lean_fraction': .8}, {'depth_exponent': float('nan')}, {'pinnacle_delay_seconds': True}):
        with pytest.raises(ValueError):
            ConsensusPolicy(**fields)
    result = evaluate_consensus(changed(request(), 'pinnacle', taker_rate=.01))
    assert not result['activated']
    assert any('pinnacle_margin_must_not_receive_extra_taker_fee' in r for r in result['reasons'])


def test_candidate_direction_is_symmetric_and_anchor_weight_cap_holds():
    low = evaluate_consensus(request(.48, .50, .50))
    assert low['activated'] and low['features']['point_change_cents'] > 0
    assert all(.25 <= w <= .75 for w in low['anchor_weights'].values())


def test_published_fixed_config_matches_defaults_and_invalid_weight_sum_is_rejected():
    config = json.loads((ROOT / 'config/conditional_consensus_research.json').read_text())
    assert ConsensusPolicy(**config['policy']) == ConsensusPolicy()
    assert config['live_enabled'] is False and config['automatic_promotion'] is False
    with pytest.raises(ValueError, match='baseline_weights_required'):
        evaluate_consensus(replace(request(), baseline_weights={v: 1e308 for v in ('kalshi', 'polymarket', 'pinnacle')}))


def test_explicit_historical_pm_equal_kalshi_depth_scenario_can_activate_but_live_cannot():
    req = changed(request(), 'polymarket', capacity_imputed=True, capacity_kind='historical_assumption',
                  capacity_assumption_basis='equal_to_kalshi', capacity_reference='scenario:PM_depth_equals_K')
    req = replace(req, mode='historical', historical_depth_assumption_reference='scenario:acknowledged_equal_K_depth')
    historical = evaluate_consensus(req)
    assert historical['activated'] and historical['features']['historical_depth_scenario_used']
    assert historical['sources']['polymarket']['capacity_imputed']
    assert not evaluate_consensus(replace(req, mode='live'))['activated']
    assert not evaluate_consensus(replace(req, historical_depth_assumption_reference=None))['activated']


def test_historical_shared_fixed_depth_scenario_keeps_pm_equal_k_and_never_imputes_pin():
    req = request()
    sources = []
    for old in req.observations:
        if old.venue == 'pinnacle':
            sources.append(old)
            continue
        fee = taker_fee_context(old.venue, old.raw_bid, old.raw_ask, 1000., 1000., old.taker_rate)
        interval = Interval(old.raw_bid - fee['sides']['bid']['conservative_fee_per_share'], old.interval.point,
                            old.raw_ask + fee['sides']['ask']['conservative_fee_per_share'])
        sources.append(replace(old, bid_capacity=1000., ask_capacity=1000., interval=interval,
                               capacity_imputed=True, capacity_kind='historical_assumption',
                               capacity_assumption_basis='equal_to_kalshi' if old.venue == 'polymarket' else 'fixed_historical_payout_capacity',
                               capacity_reference='scenario:shared_1000_payout_capacity'))
    req = replace(req, mode='historical', observations=tuple(sources),
                  historical_depth_assumption_reference='scenario:explicit_shared_1000')
    result = evaluate_consensus(req)
    assert result['activated'] and result['features']['historical_depth_scenario_used']
    assert not evaluate_consensus(changed(req, 'pinnacle', capacity_imputed=True,
                                         capacity_assumption_basis='equal_to_kalshi'))['activated']

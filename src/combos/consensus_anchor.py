"""Research candidate: conditionally lean toward agreeing Pinnacle/Polymarket.

This leaf module is deliberately not imported by production or historical
baseline pipelines. It neither authorizes quotes nor changes risk/edge charges.
Snapshot information time and price-change time have different meanings.
"""
from dataclasses import asdict, dataclass
import math
from typing import Literal

from .fees import taker_fee_context
from .pricing import Interval, pinnacle_fair

VENUES = ('kalshi', 'polymarket', 'pinnacle')


@dataclass(frozen=True)
class ConsensusPolicy:
    anchor_agreement_cents: float = .75
    minimum_kalshi_disagreement_cents: float = .5
    maximum_kalshi_disagreement_cents: float = 3.
    maximum_lean_fraction: float = .25
    maximum_anchor_venue_weight: float = .75
    depth_exponent: float = .5
    spread_floor_cents: float = 1.
    freshness_half_life_seconds: float = 60.
    pinnacle_delay_seconds: float = 30.
    pinnacle_max_age_seconds: float = 90.
    exchange_max_age_seconds: float = 15.
    pregame_buffer_seconds: float = 60.

    def __post_init__(self):
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v <= 0
               for v in asdict(self).values()):
            raise ValueError('invalid_consensus_policy')
        if not (self.minimum_kalshi_disagreement_cents < self.maximum_kalshi_disagreement_cents <= 10
                and self.anchor_agreement_cents < self.maximum_kalshi_disagreement_cents
                and self.maximum_lean_fraction <= .5 and .5 <= self.maximum_anchor_venue_weight <= 1
                and self.depth_exponent <= 1 and self.pinnacle_delay_seconds < self.pinnacle_max_age_seconds
                and self.pregame_buffer_seconds >= self.pinnacle_delay_seconds):
            raise ValueError('invalid_consensus_policy_bounds')


@dataclass(frozen=True)
class ConsensusObservation:
    venue: str
    canonical_payoff_key: str
    payoff_rules_key: str
    quoted_side: Literal['yes', 'no']
    mapping_verified: bool
    mapping_reference: str
    mapping_available_at: float
    source_reference: str
    information_at: float
    available_at: float
    information_clock: str
    information_clock_reference: str
    active: bool
    interval: Interval
    bid_capacity: float
    ask_capacity: float
    capacity_unit: str
    capacity_kind: str
    capacity_reference: str
    capacity_imputed: bool
    depth_information_at: float
    depth_available_at: float
    raw_bid: float | None = None
    raw_ask: float | None = None
    taker_rate: float | None = None
    fee_model: str | None = None
    fee_reference: str | None = None
    fee_schedule_verified: bool = False
    fee_valid_from: float | None = None
    fee_valid_until: float | None = None
    balance_precision: str | None = None
    decimal_odds_selected: float | None = None
    decimal_odds_other: float | None = None
    price_changed_at: float | None = None
    capacity_assumption_basis: str | None = None


@dataclass(frozen=True)
class ConsensusRequest:
    canonical_payoff_key: str
    payoff_rules_key: str
    decision_at: float
    scheduled_start_at: float
    phase: str
    mode: str
    baseline_interval: Interval
    baseline_weights: dict[str, float]
    baseline_reference: str
    observations: tuple[ConsensusObservation, ...]
    historical_depth_assumption_reference: str | None = None


def finite(value):
    return not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def _canonical_source(source, request, policy):
    """Validate recorded evidence and normalize the quoted side to canonical YES."""
    if source.venue not in VENUES:
        raise ValueError('unsupported_venue')
    if source.quoted_side not in ('yes', 'no'):
        raise ValueError('invalid_quoted_side')
    if (source.canonical_payoff_key != request.canonical_payoff_key
            or source.payoff_rules_key != request.payoff_rules_key
            or source.mapping_verified is not True):
        raise ValueError('unverified_or_mismatched_canonical_payoff')
    if any(not nonempty(getattr(source, key)) for key in
           ('mapping_reference', 'source_reference', 'information_clock_reference', 'capacity_reference')):
        raise ValueError('missing_source_mapping_clock_or_capacity_evidence')
    if source.active is not True:
        raise ValueError('inactive_source')
    if not isinstance(source.interval, Interval):
        raise ValueError('typed_probability_interval_required')
    if source.information_clock != 'snapshot_information_time':
        raise ValueError('verified_snapshot_information_clock_required')
    times = [source.information_at, source.available_at, source.mapping_available_at,
             source.depth_information_at, source.depth_available_at]
    if not all(finite(t) and 0 <= t <= request.decision_at for t in times):
        raise ValueError('future_or_invalid_source_clock')
    if source.available_at < source.information_at or source.depth_available_at < source.depth_information_at:
        raise ValueError('invalid_publication_chronology')
    if source.price_changed_at is not None and (not finite(source.price_changed_at)
                                               or not 0 <= source.price_changed_at <= source.information_at):
        raise ValueError('invalid_price_change_clock')
    if type(source.capacity_imputed) is not bool:
        raise ValueError('explicit_capacity_imputation_status_required')
    if source.capacity_imputed:
        if request.mode != 'historical' or not nonempty(request.historical_depth_assumption_reference):
            raise ValueError('real_two_sided_capacity_required_or_explicit_historical_scenario')
        basis = {'kalshi': 'fixed_historical_payout_capacity', 'polymarket': 'equal_to_kalshi'}.get(source.venue)
        if basis is None or source.capacity_assumption_basis != basis:
            raise ValueError('unsupported_historical_capacity_assumption')
        if source.venue == 'kalshi' and source.bid_capacity != source.ask_capacity:
            raise ValueError('fixed_historical_capacity_must_be_two_sided_equal')
    if source.capacity_unit != 'payout_dollars' or not all(finite(q) and q > 0 for q in (source.bid_capacity, source.ask_capacity)):
        raise ValueError('positive_two_sided_payout_capacity_required')
    age = request.decision_at - source.information_at
    depth_age = request.decision_at - source.depth_information_at
    is_pin = source.venue == 'pinnacle'
    age_limit = policy.pinnacle_max_age_seconds if is_pin else policy.exchange_max_age_seconds
    if max(age, depth_age) > age_limit:
        raise ValueError('stale_price_or_depth_snapshot')
    if is_pin and (source.available_at - source.information_at + 1e-9 < policy.pinnacle_delay_seconds
                   or source.depth_available_at - source.depth_information_at + 1e-9 < policy.pinnacle_delay_seconds):
        raise ValueError('pinnacle_delay_not_reflected_in_availability')
    fee_context = None
    if is_pin:
        if source.capacity_kind != 'verified_USD_stake_limit_converted_to_payout':
            raise ValueError('verified_pinnacle_limit_units_required')
        expected = pinnacle_fair(source.decimal_odds_selected, source.decimal_odds_other)
        if source.taker_rate not in (None, 0) or source.fee_model != 'bookmaker_margin_in_interval':
            raise ValueError('pinnacle_margin_must_not_receive_extra_taker_fee')
        raw_bid, raw_ask = expected.lower, expected.upper
    else:
        expected_kind = 'historical_assumption' if source.capacity_imputed else 'top_of_book'
        if source.capacity_kind != expected_kind:
            raise ValueError('actual_exchange_top_of_book_required')
        if not all(finite(p) for p in (source.raw_bid, source.raw_ask, source.taker_rate)) or not 0 <= source.raw_bid <= source.raw_ask <= 1:
            raise ValueError('invalid_raw_exchange_book')
        if source.fee_model != 'venue_cash_v2' or source.fee_schedule_verified is not True or not nonempty(source.fee_reference):
            raise ValueError('verified_market_specific_cash_fee_schedule_required')
        if not all(finite(t) for t in (source.fee_valid_from, source.fee_valid_until)) or not (
                source.fee_valid_from <= source.information_at <= request.decision_at < source.fee_valid_until):
            raise ValueError('fee_schedule_not_effective_for_decision')
        if source.venue == 'kalshi' and source.balance_precision not in ('.0001', '.01'):
            raise ValueError('verified_kalshi_balance_precision_required')
        fee_context = taker_fee_context(source.venue, source.raw_bid, source.raw_ask, source.bid_capacity,
                                        source.ask_capacity, source.taker_rate, source.balance_precision or '.0001')
        expected = Interval(max(0., source.raw_bid - fee_context['sides']['bid']['conservative_fee_per_share']),
                            (source.raw_bid + source.raw_ask) / 2,
                            min(1., source.raw_ask + fee_context['sides']['ask']['conservative_fee_per_share']))
        raw_bid, raw_ask = source.raw_bid, source.raw_ask
    if any(abs(getattr(source.interval, name) - getattr(expected, name)) > 1e-10 for name in ('lower', 'point', 'upper')):
        raise ValueError('fee_or_bookmaker_interval_mismatch')
    interval = source.interval
    bid_capacity, ask_capacity = source.bid_capacity, source.ask_capacity
    if source.quoted_side == 'no':
        interval = Interval(1 - interval.upper, 1 - interval.point, 1 - interval.lower)
        raw_bid, raw_ask = 1 - raw_ask, 1 - raw_bid
        bid_capacity, ask_capacity = ask_capacity, bid_capacity
    spread_cents = 100 * (interval.upper - interval.lower)
    delayed_floor = policy.pinnacle_delay_seconds if is_pin else 0.
    excess_age = max(0., max(age, depth_age) - delayed_floor)
    freshness = 2 ** (-excess_age / policy.freshness_half_life_seconds)
    score = min(bid_capacity, ask_capacity) ** policy.depth_exponent / max(spread_cents, policy.spread_floor_cents) * freshness
    return {'interval': asdict(interval), 'raw_bid': raw_bid, 'raw_ask': raw_ask,
            'raw_spread_cents': 100 * (raw_ask - raw_bid), 'fee_expanded_spread_cents': spread_cents,
            'bid_capacity_payout_dollars': bid_capacity, 'ask_capacity_payout_dollars': ask_capacity,
            'snapshot_age_seconds': age, 'depth_snapshot_age_seconds': depth_age,
            'publication_lag_seconds': source.available_at - source.information_at,
            'available_age_seconds': request.decision_at - source.available_at,
            'price_change_age_seconds': None if source.price_changed_at is None else request.decision_at - source.price_changed_at,
            'information_clock_reference': source.information_clock_reference,
            'freshness_excess_over_delay_seconds': excess_age, 'freshness_factor': freshness,
            'liquidity_score': score, 'fee_context_in_quoted_side': fee_context,
            'fee_reference': source.fee_reference, 'source_reference': source.source_reference,
            'mapping_reference': source.mapping_reference, 'capacity_reference': source.capacity_reference,
            'capacity_imputed': source.capacity_imputed, 'capacity_assumption_basis': source.capacity_assumption_basis,
            'quoted_side': source.quoted_side}


def evaluate_consensus(request: ConsensusRequest, policy=ConsensusPolicy()):
    """Return an auditable research candidate; never a tradability decision."""
    if (not finite(request.decision_at) or not finite(request.scheduled_start_at) or request.decision_at < 0
            or request.mode not in ('live', 'historical') or not nonempty(request.baseline_reference)
            or not nonempty(request.canonical_payoff_key) or not nonempty(request.payoff_rules_key)
            or not isinstance(request.baseline_interval, Interval)):
        raise ValueError('invalid_consensus_request')
    weights = request.baseline_weights
    if (set(weights) != set(VENUES) or not all(finite(w) and w >= 0 for w in weights.values())
            or not math.isfinite(sum(weights.values())) or sum(weights.values()) <= 0):
        raise ValueError('explicit_nonnegative_three_source_baseline_weights_required')
    weights = {v: w / sum(weights.values()) for v, w in weights.items()}
    result = {'schema_version': 1, 'model': 'conditional_pin_pm_consensus_research_v1', 'activated': False,
              'reasons': [], 'canonical_payoff_key': request.canonical_payoff_key, 'payoff_rules_key': request.payoff_rules_key,
              'decision_at': request.decision_at, 'mode': request.mode, 'baseline_reference': request.baseline_reference,
              'historical_depth_assumption_reference': request.historical_depth_assumption_reference,
              'baseline_interval': asdict(request.baseline_interval), 'candidate_interval': asdict(request.baseline_interval),
              'normalized_baseline_weights': weights, 'effective_weights': dict(weights), 'anchor_weights': {},
              'lean_fraction': 0., 'sources': {}, 'features': {}, 'policy': asdict(policy),
              'execution_authorized': False, 'quote_guard_override': False,
              'interpretation': 'Unfitted conditional fair-value hypothesis; no claimed edge, acceptance probability or inventory observation.'}
    if request.phase != 'pregame' or request.decision_at >= request.scheduled_start_at - policy.pregame_buffer_seconds:
        result['reasons'].append('outside_verified_pregame_research_scope')
    venues = [o.venue for o in request.observations]
    if len(venues) != 3 or set(venues) != set(VENUES):
        result['reasons'].append('all_three_distinct_sources_required_no_consensus_fallback')
        return result
    for source in request.observations:
        try:
            result['sources'][source.venue] = _canonical_source(source, request, policy)
        except (ValueError, TypeError, ArithmeticError) as error:
            result['reasons'].append(source.venue + ':' + str(error))
    if result['reasons']:
        return result
    sources = result['sources']; points = {v: sources[v]['interval']['point'] for v in VENUES}
    if sources['polymarket']['capacity_imputed']:
        if any(abs(sources['polymarket'][key] - sources['kalshi'][key]) > 1e-9
               for key in ('bid_capacity_payout_dollars', 'ask_capacity_payout_dollars')):
            result['reasons'].append('historical_polymarket_capacity_must_equal_canonical_kalshi_capacity')
            return result
    baseline_point = sum(weights[v] * points[v] for v in VENUES)
    if abs(baseline_point - request.baseline_interval.point) > 1e-9:
        result['reasons'].append('baseline_point_does_not_match_recorded_normalized_weights')
        return result
    pin_fraction = sources['pinnacle']['liquidity_score'] / sum(sources[v]['liquidity_score'] for v in ('pinnacle', 'polymarket'))
    pin_fraction = min(policy.maximum_anchor_venue_weight, max(1 - policy.maximum_anchor_venue_weight, pin_fraction))
    anchor_weights = {'pinnacle': pin_fraction, 'polymarket': 1 - pin_fraction}
    anchor = sum(anchor_weights[v] * points[v] for v in anchor_weights)
    anchor_gap = abs(points['pinnacle'] - points['polymarket']) * 100
    kalshi_gap = (points['kalshi'] - anchor) * 100
    isolated = (points['kalshi'] - points['pinnacle']) * (points['kalshi'] - points['polymarket']) > 0
    gaps = {}
    for a, b in (('pinnacle', 'polymarket'), ('kalshi', 'polymarket'), ('kalshi', 'pinnacle')):
        ia, ib = sources[a]['interval'], sources[b]['interval']
        gaps[a + ':' + b] = 100 * max(0., ia['lower'] - ib['upper'], ib['lower'] - ia['upper'])
    result['features'] = {'anchor_point': anchor, 'anchor_point_gap_cents': anchor_gap,
                          'kalshi_minus_anchor_point_cents': kalshi_gap, 'kalshi_isolated_same_direction': isolated,
                          'fee_expanded_interval_gaps_cents': gaps,
                          'kalshi_overlaps_both_anchor_fee_bands': all(gaps['kalshi:' + v] <= 1e-10 for v in ('pinnacle', 'polymarket')),
                          'kalshi_minus_polymarket_fee_expanded_width_cents': sources['kalshi']['fee_expanded_spread_cents'] - sources['polymarket']['fee_expanded_spread_cents'],
                          'historical_depth_scenario_used': any(s['capacity_imputed'] for s in sources.values()),
                          'inventory_or_flow_cause_observed': False}
    result['anchor_weights'] = anchor_weights
    if anchor_gap >= policy.anchor_agreement_cents:
        result['reasons'].append('pinnacle_polymarket_points_do_not_agree')
    if not isolated:
        result['reasons'].append('kalshi_not_isolated_from_both_anchors')
    if abs(kalshi_gap) < policy.minimum_kalshi_disagreement_cents:
        result['reasons'].append('kalshi_disagreement_below_fixed_threshold')
    if abs(kalshi_gap) > policy.maximum_kalshi_disagreement_cents:
        result['reasons'].append('kalshi_disagreement_exceeds_modest_scope')
    if result['reasons']:
        return result
    agreement_factor = 1 - anchor_gap / policy.anchor_agreement_cents
    freshness_factor = min(sources[v]['freshness_factor'] for v in VENUES)
    strength = agreement_factor * freshness_factor
    alpha = policy.maximum_lean_fraction * strength
    effective = {v: (1 - alpha) * weights[v] + alpha * anchor_weights.get(v, 0.) for v in VENUES}
    point = sum(effective[v] * points[v] for v in VENUES)
    # The point can lean while fee bands still overlap. Uncertainty never
    # contracts: include the baseline and all source executable/fee envelopes.
    candidate = Interval(min(request.baseline_interval.lower, *(sources[v]['interval']['lower'] for v in VENUES)),
                         point, max(request.baseline_interval.upper, *(sources[v]['interval']['upper'] for v in VENUES)))
    result.update(activated=True, reasons=['fixed_conditional_consensus_hypothesis'], effective_weights=effective,
                  lean_fraction=alpha, candidate_interval=asdict(candidate))
    result['features'].update(agreement_factor=agreement_factor, freshness_factor=freshness_factor,
                              heuristic_strength_not_probability=strength,
                              point_change_cents=100 * (point - request.baseline_interval.point))
    return result

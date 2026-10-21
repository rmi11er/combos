"""Unfitted research transform of validated leg intervals; never quote permission.

Callers must first validate payoff mappings, dated fees, snapshot clocks, and
source health. This module accepts their normalized diagnostics, not raw feeds.
"""
from dataclasses import asdict, dataclass
import math

from .pricing import Interval
from .joint_pricing import price_joint


@dataclass(frozen=True)
class VenueLiquidity:
    venue: str
    weight: float
    # Exchange fee-expanded bid/ask width, or Pinnacle margin-band width.
    width_cents: float
    two_sided_capacity_payout: float
    reference: str
    capacity_kind: str


@dataclass(frozen=True)
class LegLiquidity:
    payoff_key: str
    interval: Interval
    venues: tuple[VenueLiquidity, ...]
    validated_context_reference: str


def liquidity_reserve(legs, quantity, rho, *, depth_multiplier=1.,
                      width_floor_cents=1., historical_assumption_reference=None):
    """Return symmetric leg uncertainty floors and their joint seller reserve.

Quantity is payout contracts, a fixed conservative size proxy, not a claim of
hedge demand. No live adapter or automatic parameter selection is supplied.
"""
    if not (math.isfinite(quantity) and quantity > 0
            and math.isfinite(depth_multiplier) and depth_multiplier >= 0
            and math.isfinite(width_floor_cents) and width_floor_cents > 0):
        raise ValueError('invalid_liquidity_policy_or_quantity')
    if not 2 <= len(legs) <= 4 or len({leg.payoff_key for leg in legs}) != len(legs):
        raise ValueError('requires_two_to_four_distinct_legs')
    widened, details = [], []
    for leg in legs:
        if not leg.payoff_key or not leg.validated_context_reference or not leg.venues:
            raise ValueError('missing_validated_leg_evidence')
        names = [v.venue for v in leg.venues]
        if len(set(names)) != len(names) or not set(names) <= {'kalshi', 'polymarket', 'pinnacle'}:
            raise ValueError('invalid_venue_set')
        if not math.isclose(sum(v.weight for v in leg.venues), 1., abs_tol=1e-10, rel_tol=0):
            raise ValueError('weights_must_be_normalized')
        terms = []
        for v in leg.venues:
            if not (math.isfinite(v.weight) and 0 <= v.weight <= 1
                    and math.isfinite(v.width_cents) and 0 <= v.width_cents <= 100
                    and math.isfinite(v.two_sided_capacity_payout) and v.two_sided_capacity_payout > 0
                    and v.reference):
                raise ValueError('invalid_liquidity_evidence')
            required_kind = 'verified_USD_stake_limit_converted_to_payout' if v.venue == 'pinnacle' else 'top_of_book'
            if v.capacity_kind != required_kind:
                if not (v.venue != 'pinnacle' and v.capacity_kind == 'historical_assumption'
                        and historical_assumption_reference):
                    raise ValueError('unverified_or_unacknowledged_capacity')
            half_width = max(v.width_cents, width_floor_cents) / 200.
            target = half_width * (1. + depth_multiplier * math.sqrt(quantity / v.two_sided_capacity_payout))
            terms.append({**asdict(v), 'target_radius': target, 'weighted_radius': v.weight * target})
        radius = sum(t['weighted_radius'] for t in terms)
        old = leg.interval
        new = Interval(max(0., min(old.lower, old.point-radius)), old.point,
                       min(1., max(old.upper, old.point+radius)))
        widened.append(new)
        details.append({'payoff_key': leg.payoff_key, 'before': asdict(old), 'after': asdict(new),
                        'target_radius': radius, 'sources': terms,
                        'validated_context_reference': leg.validated_context_reference})
    before = price_joint([leg.interval for leg in legs], rho)
    after = price_joint(widened, rho)
    increment = max(0., after['stressed_upper']-before['stressed_upper'])
    return {'model': 'liquidity_uncertainty_floor_v1', 'mode': 'research_only',
            'orders_enabled': False, 'calibrated': False, 'legs': details,
            'quantity': quantity, 'depth_multiplier': depth_multiplier,
            'width_floor_cents': width_floor_cents,
            'historical_assumption_reference': historical_assumption_reference,
            'before': before, 'after': after,
            'incremental_reserve_per_contract': increment,
            'incremental_reserve_dollars': quantity * increment,
            'integration': 'replace_existing_stressed_upper_with_after_do_not_add_both'}

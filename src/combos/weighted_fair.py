"""Transparent spread/depth liquidity proxy; parameters are hypotheses."""
from dataclasses import dataclass, asdict
import math
from .observations import VENUES
from .pricing import Interval

@dataclass(frozen=True)
class WeightPolicy:
    depth_exponent: float = .5
    spread_floor_cents: float = 1.
    maximum_venue_weight: float = .6
    pregame_half_life_seconds: float = 60.
    in_play_half_life_seconds: float = 5.
    pregame_max_age_seconds: float = 120.
    in_play_max_age_seconds: float = 15.
    delayed_pinnacle: bool = False
    pinnacle_delay_seconds: float = 30.
    pinnacle_max_age_seconds: float = 90.
    exchange_max_age_seconds: float = 15.
    pregame_cutoff_seconds: float = 60.
    polymarket_score_multiplier: float = 1.5
    pinnacle_score_multiplier: float = .5
    pinnacle_weight_cap: float = .2
    disagreement_soft_cents: float = 2.
    disagreement_hard_cents: float = 5.
    delayed_padding_cents: float = .5
    disagreement_padding_multiplier: float = 1.
    disagreement_pinnacle_score_multiplier: float = .25
    disagreement_risk_multiplier: float = .5
    # Full-game NFL moneyline contracts pay 0.50 on a tie. This is an
    # explicit sensitivity input, not an inferred probability.
    full_game_tie_probability: float = .01
    period_tie_probability: float = .05
    allow_partial_venues: bool = False
    allow_single_exchange: bool = False
    liquidity_weighted_pair_fallback: bool = False
    # Opt-in preserves frozen historical manifests. Thresholds are hypotheses.
    consensus_lean_enabled: bool = False
    consensus_agreement_cents: float = .75
    consensus_minimum_kalshi_gap_cents: float = .5
    consensus_maximum_transfer_fraction: float = .25

    def __post_init__(self):
        values = asdict(self)
        if type(self.liquidity_weighted_pair_fallback) is not bool:raise ValueError('liquidity_weighted_pair_fallback must be boolean')
        if not isinstance(self.delayed_pinnacle, bool):
            raise ValueError('delayed_pinnacle must be boolean')
        if not isinstance(self.consensus_lean_enabled, bool):
            raise ValueError('consensus_lean_enabled must be boolean')
        if not isinstance(self.allow_single_exchange,bool):raise ValueError('allow_single_exchange must be boolean')
        if not all(math.isfinite(v) and v > 0 for k, v in values.items()
                   if k not in ('delayed_pinnacle', 'allow_partial_venues', 'allow_single_exchange', 'consensus_lean_enabled','liquidity_weighted_pair_fallback')):
            raise ValueError('weight parameters must be finite and positive')
        if (self.consensus_maximum_transfer_fraction > .5
                or self.consensus_agreement_cents >= self.disagreement_hard_cents
                or self.consensus_minimum_kalshi_gap_cents >= self.disagreement_hard_cents):
            raise ValueError('invalid consensus lean parameters')
        if self.depth_exponent > 1 or not 1/3 <= self.maximum_venue_weight <= 1:
            raise ValueError('invalid depth exponent or venue cap')
        if not (self.disagreement_soft_cents < self.disagreement_hard_cents <= 100
                and self.pinnacle_delay_seconds < self.pinnacle_max_age_seconds
                and self.pregame_cutoff_seconds >= self.pinnacle_delay_seconds
                and 0 < self.pinnacle_weight_cap <= self.maximum_venue_weight
                and (not self.delayed_pinnacle or 2*self.maximum_venue_weight+self.pinnacle_weight_cap >= 1)
                and 0 < self.disagreement_risk_multiplier <= 1
                and 0 < self.disagreement_pinnacle_score_multiplier <= 1
                and 0 <= self.full_game_tie_probability < 1):
            raise ValueError('invalid delayed-feed guard parameters')

    def check_pregame(self, start_at, decision_at, phase=None):
        if not self.delayed_pinnacle:
            return
        if start_at is None or not math.isfinite(start_at):
            raise ValueError('pregame_start_time_required')
        if phase is not None and phase != 'pregame':
            raise ValueError('pregame_only')
        if decision_at >= start_at-self.pregame_cutoff_seconds:
            raise ValueError('pregame_cutoff')

def capped_weights(scores, cap):
    caps = cap if isinstance(cap, dict) else {v: cap for v in scores}
    if (not scores or set(caps) != set(scores)
            or any(not math.isfinite(c) or not 0 < c <= 1 for c in caps.values())
            or sum(caps.values()) < 1-1e-12):
        raise ValueError('infeasible venue weight cap')
    if not all(math.isfinite(v) and v > 0 for v in scores.values()):
        raise ValueError('scores must be finite and positive')
    remaining = dict(scores); weights = {}; mass = 1.
    while remaining:
        total = sum(remaining.values())
        proposed = {v: mass*s/total for v, s in remaining.items()}
        capped = [v for v, w in proposed.items() if w > caps[v]+1e-12]
        if not capped:
            weights.update(proposed); break
        for v in capped:
            weights[v] = caps[v]; mass -= caps[v]; del remaining[v]
    return weights

def weighted_fair(observations, decision_at, phase, policy=WeightPolicy()):
    if phase not in ('pregame', 'in_play'):
        raise ValueError('known phase required')
    if policy.delayed_pinnacle and phase != 'pregame':
        raise ValueError('pregame_only')
    venues = {o.venue for o in observations}
    if policy.allow_single_exchange and len(observations) == 1 and venues <= {'kalshi', 'polymarket'}:
        pass
    elif policy.allow_partial_venues:
        if len(observations) < 2 or len(venues) != len(observations) or not venues.issubset(set(VENUES)):
            raise ValueError('at_least_two_distinct_venues_required')
    elif len(observations) != 3 or venues != set(VENUES):
        raise ValueError('all three distinct venues required')
    if len({o.market_key for o in observations}) != 1:
        raise ValueError('canonical payoff mismatch')
    half_life = getattr(policy, f'{phase}_half_life_seconds')
    max_age = getattr(policy, f'{phase}_max_age_seconds')
    scores = {}; details = {}
    for o in observations:
        if not o.active:
            raise ValueError(f'{o.venue}: inactive')
        age = decision_at-o.observed_at
        if not math.isfinite(decision_at) or o.available_at > decision_at or not 0 <= age <= max_age:
            raise ValueError(f'{o.venue}: future or stale')
        raw_age = age
        multiplier = 1.
        if policy.delayed_pinnacle:
            if o.venue == 'pinnacle':
                # Never rejuvenate a delayed price by stamping it at receipt.
                # max avoids counting the delay twice when the source timestamp is known.
                age = max(age, decision_at-o.available_at+policy.pinnacle_delay_seconds)
                venue_max_age = policy.pinnacle_max_age_seconds
                multiplier = policy.pinnacle_score_multiplier
            else:
                venue_max_age = policy.exchange_max_age_seconds
                if o.venue == 'polymarket': multiplier = policy.polymarket_score_multiplier
            if age > venue_max_age:
                raise ValueError(f'{o.venue}: future or stale')
        spread = 100*(o.interval.upper-o.interval.lower)
        depth = min(o.bid_capacity, o.ask_capacity)
        freshness = 2**(-age/half_life)
        score = depth**policy.depth_exponent / max(spread, policy.spread_floor_cents) * freshness * multiplier
        if not math.isfinite(score) or score <= 0:
            raise ValueError('invalid liquidity score')
        scores[o.venue] = score
        details[o.venue] = {'age_seconds': age, 'two_sided_depth_payout_dollars': depth,
            'source_age_seconds': raw_age, 'available_at': o.available_at, 'score_multiplier': multiplier,
            'fee_expanded_spread_cents': spread, 'freshness': freshness, 'score': score,
            'source_reference': o.source_reference, 'mapping_reference': o.mapping_reference,
            'fee_reference': o.fee_reference}
        details[o.venue]['fee_context']=o.fee_context
        details[o.venue]['freshness_context']=o.freshness_context
    guard = {'enabled': policy.delayed_pinnacle, 'quote_allowed': True, 'risk_multiplier': 1.}
    points = {o.venue: o.interval.point for o in observations}
    consensus = {'enabled': policy.consensus_lean_enabled, 'detected': False,
                 'applied': False, 'source_points': points}
    if policy.consensus_lean_enabled and venues == set(VENUES):
        k, pm, pin = (points[v] for v in VENUES)
        external_gap = abs(pm-pin)*100
        kalshi_gap = min(abs(k-pm), abs(k-pin))*100
        consensus.update(external_agreement_cents=external_gap,
                         minimum_kalshi_gap_cents=kalshi_gap,
                         detected=(external_gap <= policy.consensus_agreement_cents+1e-10
                                   and (k-pm)*(k-pin) > 0
                                   and kalshi_gap+1e-10 >= policy.consensus_minimum_kalshi_gap_cents))
    caps = {v: policy.maximum_venue_weight for v in scores}
    if policy.delayed_pinnacle and len(venues) > 1:
        books = {o.venue: o.interval for o in observations}
        gaps = {}
        for a, b in (('pinnacle', 'kalshi'), ('pinnacle', 'polymarket'), ('kalshi', 'polymarket')):
            if a not in books or b not in books:
                continue
            gaps[a+':'+b] = 100*max(0., books[a].lower-books[b].upper, books[b].lower-books[a].upper)
        gap = max(gaps.values())
        moderate = gap+1e-10 >= policy.disagreement_soft_cents
        hard = gap+1e-10 >= policy.disagreement_hard_cents
        penalize_pinnacle = moderate and not consensus['detected']
        if penalize_pinnacle and 'pinnacle' in scores:
            scores['pinnacle'] *= policy.disagreement_pinnacle_score_multiplier
            details['pinnacle']['score'] = scores['pinnacle']
        if 'pinnacle' in scores: caps['pinnacle'] = policy.pinnacle_weight_cap
        guard.update(quote_allowed=not hard, reason='venue_disagreement_hard' if hard else None,
            regime='halt' if hard else ('defensive' if moderate else 'normal'),
            interval_gaps_cents=gaps, maximum_interval_gap_cents=gap,
            risk_multiplier=policy.disagreement_risk_multiplier if moderate else 1.,
            additional_pinnacle_score_multiplier=policy.disagreement_pinnacle_score_multiplier if penalize_pinnacle else 1.,
            padding_cents=policy.delayed_padding_cents+policy.disagreement_padding_multiplier*max(0.,gap-policy.disagreement_soft_cents))
    weights = capped_weights(scores, caps)
    consensus['base_weights'] = dict(weights)
    if consensus['detected'] and guard['quote_allowed']:
        # Transfer at most a fraction of Kalshi's weight into available external
        # headroom, proportional to the same liquidity scores. Never relax caps.
        remaining = weights['kalshi']*policy.consensus_maximum_transfer_fraction
        recipients = {v for v in ('polymarket', 'pinnacle') if caps[v]-weights[v] > 1e-12}
        while remaining > 1e-12 and recipients:
            total = sum(scores[v] for v in recipients)
            allocation = {v: min(caps[v]-weights[v], remaining*scores[v]/total)
                          for v in recipients}
            transferred = sum(allocation.values())
            for v, amount in allocation.items():
                weights[v] += amount
            weights['kalshi'] -= transferred
            remaining -= transferred
            recipients = {v for v in recipients if caps[v]-weights[v] > 1e-12}
        consensus['applied'] = weights['kalshi'] < consensus['base_weights']['kalshi']-1e-12
    consensus['final_weights'] = dict(weights)
    consensus['point_adjustment_cents'] = 100*sum(
        (weights[v]-consensus['base_weights'][v])*points[v] for v in weights)
    fair = Interval(*(sum(weights[o.venue]*getattr(o.interval, k) for o in observations)
                      for k in ('lower', 'point', 'upper')))
    blend = asdict(fair)
    if policy.delayed_pinnacle and 'pinnacle' in venues:
        # Conservative envelope protects both selected YES and selected NO legs.
        # An old Pinnacle anchor must not narrow current exchange uncertainty.
        exchange_intervals = [o.interval for o in observations if o.venue != 'pinnacle']
        padding = guard['padding_cents']/100
        fair = Interval(max(0., min(fair.lower, *(b.lower for b in exchange_intervals))-padding),
                        fair.point,
                        min(1., max(fair.upper, *(b.upper for b in exchange_intervals))+padding))
    for venue, weight in weights.items(): details[venue]['weight'] = weight
    disagreement = max(o.interval.point for o in observations)-min(o.interval.point for o in observations)
    return {'fair': asdict(fair), 'unprotected_blend': blend, 'guard': guard,
            'venues': details, 'consensus_lean': consensus, 'venue_point_range_cents': 100*disagreement,
            'policy': asdict(policy), 'model': 'delayed_pinnacle_pregame_v1' if policy.delayed_pinnacle else 'spread_depth_proxy_v1'}

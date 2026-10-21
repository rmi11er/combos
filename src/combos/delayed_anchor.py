"""Research estimator: a delayed sharp level plus causal exchange innovations.

Returns a point forecast and diagnostic inputs, not a quote or an uncertainty
bound. No timestamps are rejuvenated and no missing book depth is imputed.
"""
from bisect import bisect_right
from dataclasses import asdict, dataclass
import math

from .pricing import Interval


@dataclass(frozen=True)
class ProbabilitySnapshot:
    market_key: str
    mapping_reference: str
    venue: str
    interval: Interval
    information_at: float
    available_at: float
    source_reference: str
    information_time_basis: str
    information_time_verified: bool
    active: bool = True
    two_sided_depth: float | None = None
    historical_imputed: bool = False

    def __post_init__(self):
        if self.venue not in ('pinnacle', 'kalshi', 'polymarket'):
            raise ValueError('unsupported venue')
        if any(not isinstance(v, str) or not v for v in (
                self.market_key, self.mapping_reference, self.source_reference, self.information_time_basis)):
            raise ValueError('snapshot provenance required')
        if not isinstance(self.interval, Interval):
            raise ValueError('probability interval required')
        if not all(math.isfinite(v) for v in (self.information_at, self.available_at)) or self.information_at > self.available_at:
            raise ValueError('invalid snapshot chronology')
        if any(type(v) is not bool for v in (self.active, self.information_time_verified, self.historical_imputed)):
            raise ValueError('explicit snapshot flags required')
        if self.two_sided_depth is not None and (not math.isfinite(self.two_sided_depth) or self.two_sided_depth <= 0):
            raise ValueError('invalid depth')


class ProbabilityHistory:
    """Local append-only as-of history, including inactive states and resets.

    Availability, rather than a last-price-change timestamp, orders observations.
    Querying an old cutoff never sees a newer received packet. No HTTP is used.
    """
    def __init__(self):
        self._rows = {}
        self._times = {}

    def append(self, record: ProbabilitySnapshot):
        if not isinstance(record, ProbabilitySnapshot):
            raise ValueError('typed_probability_snapshot_required')
        key = (record.market_key, record.venue)
        rows = self._rows.setdefault(key, [])
        times = self._times.setdefault(key, [])
        if times and record.available_at < times[-1]:
            raise ValueError('out_of_order_availability')
        if rows and record.information_at < rows[-1].information_at:
            raise ValueError('information_time_regressed')
        if times and record.available_at == times[-1]:
            if record != rows[-1]:
                raise ValueError('conflicting_available_timestamp')
            return
        rows.append(record); times.append(record.available_at)

    def asof(self, market_key, venue, at):
        if not math.isfinite(at):
            raise ValueError('invalid asof time')
        key = (market_key, venue)
        i = bisect_right(self._times.get(key, []), at)-1
        if i < 0:
            raise ValueError(venue+': no_prior_state')
        return self._rows[key][i]


@dataclass(frozen=True)
class DelayedAnchorPolicy:
    beta: float = .5
    exchange_max_age_seconds: float = 15.
    anchor_max_age_seconds: float = 90.
    baseline_max_age_seconds: float = 15.
    pregame_cutoff_seconds: float = 60.
    probability_clip: float = 1e-6
    depth_exponent: float = .5
    spread_floor_cents: float = 1.
    polymarket_score_multiplier: float = 1.5
    maximum_innovation_disagreement_cents: float = 5.

    def __post_init__(self):
        for name, value in asdict(self).items():
            if not math.isfinite(value) or value < 0 or (name != 'beta' and value == 0):
                raise ValueError('invalid delayed-anchor parameter: '+name)
        if self.beta > 1 or self.depth_exponent > 1 or self.probability_clip >= .5:
            raise ValueError('invalid beta, depth exponent or clipping')


class DelayedAnchorEstimator:
    def __init__(self, history: ProbabilityHistory, policy=DelayedAnchorPolicy()):
        self.history = history
        self.policy = policy

    def manifest(self):
        return {'model': 'delayed_anchor_exchange_innovation_v1', 'policy': asdict(self.policy),
                'calibrated': False, 'output': 'point forecast; quote reserves supplied separately',
                'exchange_weights': 'normalized minimum current/baseline depth over widest fee-expanded interval, with PM prior'}

    def _check(self, record, at, max_age):
        if not record.active:
            raise ValueError(record.venue+': inactive_latest_state')
        if record.historical_imputed:
            raise ValueError(record.venue+': imputed_book_forbidden')
        if not record.information_time_verified:
            raise ValueError(record.venue+': effective_information_time_unverified')
        if record.available_at > at or not 0 <= at-record.information_at <= max_age:
            raise ValueError(record.venue+': future_or_stale')
        if record.venue != 'pinnacle' and record.two_sided_depth is None:
            raise ValueError(record.venue+': depth_missing')

    def _logit(self, p):
        p = min(1-self.policy.probability_clip, max(self.policy.probability_clip, p))
        return math.log(p/(1-p))

    @staticmethod
    def _logistic(z):
        if z >= 0:
            return 1/(1+math.exp(-z))
        ez = math.exp(z)
        return ez/(1+ez)

    def estimate(self, anchor, current_exchanges, decision_at, start_at):
        p = self.policy
        if not math.isfinite(decision_at) or not math.isfinite(start_at) or decision_at >= start_at-p.pregame_cutoff_seconds:
            raise ValueError('pregame_cutoff')
        if anchor.venue != 'pinnacle':
            raise ValueError('pinnacle_anchor_required')
        self._check(anchor, decision_at, p.anchor_max_age_seconds)
        if len(current_exchanges) != 2 or {o.venue for o in current_exchanges} != {'kalshi', 'polymarket'}:
            raise ValueError('both distinct current exchanges required')
        s = anchor.information_at
        scores, details = {}, {}
        for current in current_exchanges:
            self._check(current, decision_at, p.exchange_max_age_seconds)
            if current.information_at < s:
                raise ValueError(current.venue+': current_information_precedes_anchor')
            baseline = self.history.asof(anchor.market_key, current.venue, s)
            self._check(baseline, s, p.baseline_max_age_seconds)
            if any((o.market_key, o.mapping_reference) != (anchor.market_key, anchor.mapping_reference)
                   for o in (current, baseline)):
                raise ValueError('canonical_payoff_or_mapping_version_mismatch')
            depth = min(current.two_sided_depth, baseline.two_sided_depth)
            spread = 100*max(current.interval.upper-current.interval.lower,
                             baseline.interval.upper-baseline.interval.lower)
            prior = p.polymarket_score_multiplier if current.venue == 'polymarket' else 1.
            score = prior * depth**p.depth_exponent/max(spread, p.spread_floor_cents)
            if not math.isfinite(score) or score <= 0:
                raise ValueError('invalid_exchange_liquidity_score')
            scores[current.venue] = score
            details[current.venue] = {'baseline': asdict(baseline), 'current': asdict(current),
                'logit_innovation': self._logit(current.interval.point)-self._logit(baseline.interval.point),
                'probability_innovation_cents':100*(current.interval.point-baseline.interval.point),
                'liquidity_score':score}
        moves = [v['probability_innovation_cents'] for v in details.values()]
        if max(moves)-min(moves) > p.maximum_innovation_disagreement_cents:
            raise ValueError('exchange_innovation_disagreement')
        total_score = sum(scores.values())
        if not math.isfinite(total_score):
            raise ValueError('invalid_total_exchange_liquidity_score')
        weights = {venue:score/total_score for venue,score in scores.items()}
        innovation = sum(weights[venue]*details[venue]['logit_innovation'] for venue in weights)
        correction = p.beta*innovation
        point = self._logistic(self._logit(anchor.interval.point)+correction)
        return {'fair_point':point, 'anchor_point':anchor.interval.point,
                'adjustment_cents':100*(point-anchor.interval.point), 'anchor_information_at':s,
                'decision_at':decision_at, 'anchor':asdict(anchor), 'exchange_context':details,
                'exchange_weights':weights, 'logit_innovation':innovation, 'logit_correction':correction,
                'clipping_applied':any(not p.probability_clip <= value <= 1-p.probability_clip
                                      for value in [anchor.interval.point]+[d[k]['interval']['point']
                                          for d in details.values() for k in ('baseline','current')]),
                'uncertainty_bound':None, 'quote_authorized':False, 'components':self.manifest()}

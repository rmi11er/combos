"""Composable RFQ pricing over prebuilt mappings and local observations.

Collectors and mapping builders perform I/O outside this service. Models expose
versioned manifests so replay records which implementation produced each quote.
"""
from dataclasses import asdict, dataclass, replace
import math
from typing import Protocol, Sequence
from .observations import Observation, VENUES
from .pricing import Interval
from .joint_pricing import price_joint
from .weighted_fair import WeightPolicy, weighted_fair
from .rfq_scope import check_legs, check_mappings, check_start
from .payoff_risk import canonical_leg_risk
from .replay import complement
from .settlement_policy import normalize_pinnacle_interval, settlement_policy


class SnapshotRepository(Protocol):
    def get(self, owner: str, key: str, default=None): ...


class LegFairModel(Protocol):
    required_venues: Sequence[str]
    def price(self, observations: Sequence[Observation], at: float, phase: str) -> dict: ...
    def manifest(self) -> dict: ...


class JointPricingModel(Protocol):
    def price(self, intervals: Sequence[Interval]) -> dict: ...
    def manifest(self) -> dict: ...


@dataclass(frozen=True)
class SignalAdjustment:
    quote_allowed: bool = True
    risk_multiplier: float = 1.
    extra_edge_per_share: float = 0.
    reason: str | None = None

    def __post_init__(self):
        if type(self.quote_allowed) is not bool or not math.isfinite(self.risk_multiplier) or not 0<self.risk_multiplier<=1:
            raise ValueError('invalid signal quote/risk adjustment')
        if not math.isfinite(self.extra_edge_per_share) or self.extra_edge_per_share<0:
            raise ValueError('invalid signal edge adjustment')


class PricingSignal(Protocol):
    def evaluate(self, legs: Sequence[dict], pricing: dict, at: float) -> SignalAdjustment: ...
    def manifest(self) -> dict: ...


@dataclass(frozen=True)
class WeightedLegFair:
    policy: WeightPolicy
    @property
    def required_venues(self):
        return VENUES

    def price(self, observations, at, phase):
        policy=self.policy
        if policy.allow_single_exchange and len(observations)<3:
            # A lone exchange necessarily has full weight; retain Pinnacle's
            # 20% cap when only one exchange and Pinnacle remain.
            cap=1. if len(observations)==1 or (policy.liquidity_weighted_pair_fallback and any(o.venue=='pinnacle' for o in observations)) else max(policy.maximum_venue_weight,
                1-policy.pinnacle_weight_cap if any(o.venue=='pinnacle' for o in observations) else .5)
            policy=replace(policy,maximum_venue_weight=cap,allow_partial_venues=True)
        return weighted_fair(observations,at,phase,policy)

    def manifest(self):
        return {'model':'weighted_available_venues_v1' if self.policy.allow_single_exchange else 'weighted_three_venue_v1',
                'policy':asdict(self.policy),'required_venues':list(self.required_venues)}


@dataclass(frozen=True)
class PairwiseMomentJoint:
    rho: float

    def price(self, intervals):return price_joint(intervals,self.rho)

    def manifest(self):return {'model':'pairwise_moment_upper_v1','rho':self.rho}


class MappingRegistry:
    """Exact O(1) ticker lookup; no fuzzy matching or HTTP requests on an RFQ."""
    def __init__(self, mappings):
        self.by_ticker={}
        for mapping in mappings:
            for key in ('market_key','fixture_key','sport','mapping_reference','kalshi_ticker'):
                if not mapping.get(key):raise ValueError(f'mapping missing {key}')
            if not math.isfinite(mapping['start_at']):raise ValueError('invalid fixture start')
            if mapping['kalshi_ticker'] in self.by_ticker:raise ValueError('duplicate Kalshi mapping')
            self.by_ticker[mapping['kalshi_ticker']]=mapping

    def resolve(self, legs):
        return [self.by_ticker.get(l['market_ticker']) for l in legs]


class PricingService:
    def __init__(self, repository: SnapshotRepository, config, weights, leg_model=None, joint_model=None, signals=()):
        self.repository=repository;self.config=config;self.weights=weights
        self.registry=MappingRegistry(config['mappings'])
        fallback=config.get('source_fallback',{}).get('enabled',False)
        if type(fallback) is not bool:raise ValueError('source_fallback.enabled must be boolean')
        if fallback:
            for key in ('minimum_two_sided_depth_dollars','maximum_raw_spread_cents'):
                value=config['source_fallback'].get(key)
                if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<=0:
                    raise ValueError('invalid source_fallback.'+key)
        self.leg_model=leg_model or WeightedLegFair(replace(weights,allow_single_exchange=True,allow_partial_venues=True,
            liquidity_weighted_pair_fallback=config.get('source_fallback',{}).get('liquidity_weighted_pair_fallback',False)) if fallback else weights)
        self.joint_model=joint_model or PairwiseMomentJoint(config['correlation_rho'])
        self.signals=tuple(signals)
        if not self.leg_model.required_venues or len(set(self.leg_model.required_venues))!=len(self.leg_model.required_venues):
            raise ValueError('distinct required model venues needed')

    def manifest(self):
        return {'leg_model':self.leg_model.manifest(),'joint_model':self.joint_model.manifest(),
                'signals':[s.manifest() for s in self.signals]}

    def price(self, legs, at):
        check_legs(legs,self.config)
        mappings=self.registry.resolve(legs);check_mappings(legs,mappings,self.config)
        intervals=[];details=[];fixtures=[];contracts=[]
        for leg,mapping in zip(legs,mappings):
            status=self.repository.get('fixture_status',mapping['fixture_key'],{})
            phase=status.get('phase','in_play' if at>=mapping['start_at'] else 'pregame')
            self.weights.check_pregame(mapping['start_at'],at,phase)
            check_start(mapping,status,at,self.config)
            shadow_permissive = (self.config.get('mode') == 'shadow' and
                                 self.config.get('shadow_allow_unreviewed_families') and
                                 mapping.get('shadow_pricing_authorized') is True)
            fallback=self.config.get('source_fallback',{})
            fallback_enabled=fallback.get('enabled',False)
            pin_block=mapping.get('pricing_block_reason') in ('pinnacle_payoff_mapping_unreviewed','void_basis_required')
            if mapping.get('pricing_block_reason') and not shadow_permissive and not (fallback_enabled and pin_block):
                raise ValueError(mapping['pricing_block_reason'])
            if not fallback_enabled and any(f.get('valid_until') is not None and at>=f['valid_until'] for f in mapping.get('fees',{}).values()):
                raise ValueError('leg_fee_metadata_expired')
            observations=[];excluded={}
            for venue in self.leg_model.required_venues:
                if fallback_enabled and venue=='pinnacle' and pin_block:
                    excluded[venue]='pinnacle_mapping_unavailable';continue
                fees=mapping.get('fees',{}).get(venue,{})
                if fallback_enabled and fees.get('valid_until') is not None and at>=fees['valid_until']:
                    excluded[venue]='fee_metadata_expired';continue
                row=self.repository.get('observations',mapping['market_key']+':'+venue)
                if row is None:
                    if fallback_enabled:
                        excluded[venue]='observation_missing';continue
                    if shadow_permissive and venue == 'pinnacle':
                        continue
                    raise ValueError(f'{venue}: observation_missing')
                if row.get('historical_only') or row.get('depth_imputed'):
                    raise ValueError('historical_imputation_forbidden_in_forward_pricing')
                if row['mapping_reference']!=mapping['mapping_reference']:raise ValueError('mapping_version_mismatch')
                observation = Observation.from_record(row)
                observation = normalize_pinnacle_interval(
                    observation, mapping, self.weights.full_game_tie_probability,
                    self.weights.period_tie_probability)
                if fallback_enabled:
                    age=at-observation.observed_at
                    max_age=self.weights.exchange_max_age_seconds if self.weights.delayed_pinnacle else getattr(self.weights,f'{phase}_max_age_seconds')
                    if venue=='pinnacle' and self.weights.delayed_pinnacle:
                        age=max(age,at-observation.available_at+self.weights.pinnacle_delay_seconds)
                        max_age=self.weights.pinnacle_max_age_seconds
                    reason=None
                    if not observation.active:reason='inactive'
                    elif observation.available_at>at or not 0<=age<=max_age:reason='future_or_stale'
                    elif venue!='pinnacle':
                        if min(observation.bid_capacity,observation.ask_capacity)<fallback['minimum_two_sided_depth_dollars']:reason='insufficient_depth'
                        elif 100*(float(row['yes_ask'])-float(row['yes_bid']))>fallback['maximum_raw_spread_cents']+1e-9:reason='spread_too_wide'
                    if reason:excluded[venue]=reason;continue
                observations.append(observation)
            if fallback_enabled and not any(o.venue in ('kalshi','polymarket') for o in observations):
                raise ValueError('no_liquid_fresh_exchange:'+','.join(f'{v}={r}' for v,r in sorted(excluded.items())))
            if len(observations) < 3 and not shadow_permissive and not fallback_enabled:
                raise ValueError('incomplete_source_set')
            fair=self.leg_model.price(observations,at,phase)
            if fallback_enabled:fair['source_fallback']={'used':sorted(o.venue for o in observations),'excluded':excluded}
            guard=fair['guard']
            if type(guard['quote_allowed']) is not bool or not math.isfinite(guard['risk_multiplier']) or not 0<guard['risk_multiplier']<=1:
                raise ValueError('invalid leg model guard')
            intervals.append(complement(Interval(**fair['fair']),leg['side']))
            details.append({'mapping':mapping,'selected_side':leg['side'],
                            'settlement_policy':settlement_policy(mapping),**fair})
            fixtures.append(mapping['fixture_key']);contracts.append(canonical_leg_risk(mapping,leg['side'])['key'])
        joint=self.joint_model.price(intervals)
        base=Interval(**joint['joint']);upper=joint['stressed_upper']
        if not math.isfinite(upper) or not base.upper<=upper<=min(v.upper for v in intervals)+1e-9:
            raise ValueError('invalid joint model bound')
        tail = self.config.get('correlation_tail') or {}
        tail_rejected = (bool(tail.get('enabled')) and
                         'shadow_policy_study' not in self.config and
                         100 * (upper - base.point) >= float(tail.get('reject_reserve_cents', math.inf)))
        result={**joint,'legs':details,'fixtures':fixtures,'contracts':contracts,
                'quote_allowed':all(d['guard']['quote_allowed'] for d in details) and not tail_rejected,
                'risk_multiplier':min(d['guard']['risk_multiplier'] for d in details),
                'extra_edge_per_share':0.,'signals':[],'components':self.manifest()}
        if tail_rejected:
            result['block_reason'] = 'correlation_tail_reserve'
            result['correlation_tail'] = {'enabled': True, 'reject_reserve_cents': float(tail['reject_reserve_cents']), 'reserve_cents': 100 * (upper - base.point), 'basis': tail.get('basis', 'frozen_development_percentile')}
        for signal in self.signals:
            adjustment=signal.evaluate(legs,result,at)
            if not isinstance(adjustment,SignalAdjustment):raise ValueError('invalid signal result')
            result['signals'].append({'component':signal.manifest(),'adjustment':asdict(adjustment)})
            result['quote_allowed'] &= adjustment.quote_allowed
            result['risk_multiplier']=min(result['risk_multiplier'],adjustment.risk_multiplier)
            result['extra_edge_per_share']+=adjustment.extra_edge_per_share
            if not adjustment.quote_allowed:result['block_reason']='signal:'+str(adjustment.reason or signal.manifest()['model'])
        return result

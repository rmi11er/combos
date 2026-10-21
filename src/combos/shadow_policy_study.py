"""Versioned quote experiments attached to decisions, never an execution policy.

Evaluate after the baseline decision so even an infeasible stressed floor has a
reviewable point-model alternative. Successful pricing is still mandatory: this
module cannot recover missing mappings/depth or override any source-health gate.
"""
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
import math
from pathlib import Path

from .observations import Observation
from .quote_policy import FairSignal, MakerFeeTerms, QuotePolicy, QuoteRequest, Reserve


class ShadowPolicyStudy:
    def __init__(self, config, runtime, repository):
        self.config = deepcopy(config)
        self.runtime = runtime
        self.repository = repository
        if config.get('schema_version') != 1 or config.get('mode') != 'shadow_research_only':
            raise ValueError('invalid_shadow_study_schema_or_mode')
        if config.get('orders_enabled') is not False:
            raise ValueError('shadow_study_orders_must_be_disabled')
        if not config.get('policy_reference'):
            raise ValueError('shadow_study_policy_reference_required')
        for key in ('policy_available_at', 'fee_terms_available_at'):
            if not math.isfinite(config[key]):
                raise ValueError('invalid_shadow_study_information_time')
        if config.get('balance_precision') not in ('.0001', '.01'):
            raise ValueError('shadow_study_verified_balance_precision_required')
        profiles = config.get('sports', {})
        if runtime['sport'] not in profiles:
            raise ValueError('shadow_study_sport_profile_missing')
        for sport, profile in profiles.items():
            if sport not in ('MLB', 'NFL') or not profile.get('version'):
                raise ValueError('invalid_shadow_study_sport_profile')
            names = []
            for variant in profile['variants']:
                names.append(variant['name'])
                if variant['fair_source'] not in ('existing_blend', 'kalshi', 'polymarket'):
                    raise ValueError('unsupported_shadow_study_fair_source')
                if variant['reserve_mode'] not in ('existing_stressed', 'point_diagnostic'):
                    raise ValueError('unsupported_shadow_study_reserve_mode')
                if variant['reserve_mode'] == 'existing_stressed' and variant['fair_source'] != 'existing_blend':
                    raise ValueError('stressed_reserves_require_existing_blend')
            if not names or len(set(names)) != len(names):
                raise ValueError('duplicate_or_missing_shadow_study_variants')
            markups = profile['commercial_markups_per_contract']
            if not markups or any(not math.isfinite(x) or x < 0 for x in markups):
                raise ValueError('invalid_shadow_study_markups')
        self.profile = profiles[runtime['sport']]
        self.policy = QuotePolicy()

    def manifest(self):
        raw = json.dumps(self.config, sort_keys=True, separators=(',', ':'))
        return {'component': 'shadow_policy_study_v1', 'mode': 'shadow_research_only',
                'sport': self.runtime['sport'], 'sport_model_version': self.profile['version'],
                'config_sha256': hashlib.sha256(raw.encode()).hexdigest(),
                'config': self.config, 'quote_policy': self.policy.manifest(),
                'code_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                'acceptance_labels_available': False, 'orders_enabled': False}

    def source_context(self, pricing, at):
        """Recover exactly the snapshots that the successful pricer validated."""
        legs = []
        source_joint = {'kalshi': 1., 'polymarket': 1.}
        for detail in pricing['legs']:
            mapping = detail['mapping']
            venue_details = {}
            for venue in ('kalshi', 'polymarket'):
                row = self.repository.get('observations', mapping['market_key'] + ':' + venue)
                if not row or row.get('historical_only') or row.get('depth_imputed'):
                    raise ValueError('shadow_study_real_exchange_depth_required')
                observed = Observation.from_record(row)
                proven = detail['venues'][venue]
                if (not observed.active or observed.available_at > at
                        or observed.mapping_reference != mapping['mapping_reference']
                        or observed.source_reference != proven['source_reference']
                        or observed.available_at != proven['available_at']):
                    raise ValueError('shadow_study_snapshot_differs_from_priced_context')
                selected = observed.selected_interval(detail['selected_side'])
                source_joint[venue] *= selected.point
                venue_details[venue] = {
                    'selected_interval': asdict(selected),
                    'canonical_yes_interval': asdict(observed.interval),
                    'two_sided_depth_payout_dollars': min(observed.bid_capacity, observed.ask_capacity),
                    'fee_expanded_spread_cents': 100 * (selected.upper - selected.lower),
                    'observed_at': observed.observed_at, 'available_at': observed.available_at,
                    'age_seconds': at - observed.observed_at,
                    'source_reference': observed.source_reference,
                    'mapping_reference': observed.mapping_reference,
                    'fee_reference': observed.fee_reference, 'fee_context': observed.fee_context,
                    'freshness_context': observed.freshness_context,
                    'existing_blend_weight': proven['weight']}
            k, p = (venue_details[v]['selected_interval'] for v in ('kalshi', 'polymarket'))
            legs.append({'kalshi_ticker': mapping['kalshi_ticker'],
                         'market_key': mapping['market_key'], 'fixture_key': mapping['fixture_key'],
                         'selected_side': detail['selected_side'], 'venues': venue_details,
                         'polymarket_minus_kalshi_selected_cents': 100 * (p['point'] - k['point']),
                         'fee_expanded_interval_gap_cents': 100 * max(0., p['lower'] - k['upper'], k['lower'] - p['upper'])})
        return {'legs': legs, 'source_combo_point_probabilities': source_joint,
                'polymarket_minus_kalshi_combo_cents': 100 * (source_joint['polymarket'] - source_joint['kalshi']),
                'source_combo_assumption': 'independent_distinct_fixtures',
                'source_sharpness_conclusion': 'unvalidated_sport_specific_hypothesis'}

    def evaluate_decision(self, decision):
        result = {'mode': 'shadow_research_only', 'orders_enabled': False,
                  'fills_assumed': False, 'selected': None,
                  'baseline_status': decision['status'], 'baseline_reason': decision.get('reason'),
                  'sport': self.runtime['sport'], 'sport_model_version': self.profile['version'],
                  'policy_reference': self.config['policy_reference'], 'variants': [],
                  'risk_context': {'capital_available_before_baseline_dollars': decision['capital_available_dollars'],
                                   'baseline_risk': decision.get('risk'),
                                   'candidate_risk_checks': 'not_performed_no_candidate_reservations'}}
        pricing = decision.get('pricing')
        if pricing is None:
            return {**result, 'status': 'blocked', 'reason': decision.get('reason', 'pricing_unavailable')}
        if not pricing['quote_allowed']:
            return {**result, 'status': 'blocked', 'reason': pricing.get('block_reason', 'venue_disagreement_hard')}
        # The engine computes pricing only after creator, scope and causal data
        # checks. Refuse to silently extrapolate a future engine's new rejection.
        allowed_reasons = {None, 'no_price_with_required_edge', 'rounded_fee_edge_below_floor',
                           'capital_exhausted', 'contract_risk_limit', 'combo_risk_limit',
                           'fixture_risk_limit', 'risk_limits_unconfigured'}
        if decision.get('reason') not in allowed_reasons:
            return {**result, 'status': 'blocked', 'reason': decision['reason']}
        at = decision['decision_at']
        result['source_disagreement'] = self.source_context(pricing, at)
        request = decision['request']
        fixed = request.get('contracts_fp')
        if not fixed or float(fixed) <= 0:
            return {**result, 'status': 'unavailable',
                    'reason': 'target_cost_requires_candidate_dependent_quantity' if request.get('target_cost_dollars') else 'rfq_size_missing'}
        quantity = float(fixed)
        terms = next((v for prefix, v in sorted(self.runtime['combo_terms'].items(), key=lambda kv: -len(kv[0]))
                      if request['market_ticker'].startswith(prefix)), None)
        if not terms or not terms.get('fee_reference'):
            return {**result, 'status': 'blocked', 'reason': 'combo_fee_or_grid_unconfigured'}
        for variant in self.profile['variants']:
            name = variant['name']
            point = pricing['joint']['point'] if variant['fair_source'] == 'existing_blend' else result['source_disagreement']['source_combo_point_probabilities'][variant['fair_source']]
            stressed = variant['reserve_mode'] == 'existing_stressed'
            amounts = {'uncertainty': pricing['joint']['upper'] - point if stressed else 0.,
                       'dependence': pricing['stressed_upper'] - pricing['joint']['upper'] if stressed else 0.,
                       'adverse_selection': 0., 'inventory': 0.,
                       'strategy_signal': pricing.get('extra_edge_per_share', 0.)}
            reserves = tuple(Reserve(k, v, at,
                'existing_pricing_uncalibrated_bound' if stressed and k in ('uncertainty', 'dependence')
                else 'explicit_unestimated_zero_assumption' if v == 0 else 'existing_pricing_signal', False)
                for k, v in amounts.items())
            quote_request = QuoteRequest(
                str(decision['source_seq']) + ':' + self.profile['version'] + ':' + name, at, quantity,
                FairSignal(point, at, 'validated_shadow_pricing_and_source_context:' + str(decision['source_seq'])),
                reserves, MakerFeeTerms(terms['maker_fee_rate'], self.config['fee_terms_available_at'],
                                       terms['fee_reference'], self.config['balance_precision'], terms.get('valid_until')),
                tuple(terms['price_ranges']), self.runtime['minimum_net_edge_per_share'],
                self.config['policy_reference'], self.config['policy_available_at'])
            evaluated = self.policy.evaluate(quote_request, self.profile['commercial_markups_per_contract'])
            result['variants'].append({'name': name, 'fair_source': variant['fair_source'],
                                       'reserve_mode': variant['reserve_mode'],
                                       'deployable': False, 'evaluation': evaluated})
        result['status'] = 'evaluated'
        return result

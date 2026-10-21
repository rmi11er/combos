"""Composable quote-floor research with no execution or invented fill model.

All prices/probabilities use dollars per $1 payout contract. Seller YES asks are
implemented as native NO bids. Actual single-fill cash fees use fees.py; reserve
and commercial markup dollars remain separate in every candidate ledger.
"""
from bisect import bisect_left
from copy import deepcopy
from dataclasses import dataclass, asdict
from decimal import Decimal
from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path
from typing import Protocol

from .fees import kalshi_fill_fee, value


def finite_time(t):
    if not math.isfinite(t):
        raise ValueError('nonfinite_information_time')
    return t


def asof(available_at, decision_at, reference):
    if not reference or finite_time(available_at) > finite_time(decision_at):
        raise ValueError('missing_provenance_or_future_information')


def probability(p):
    p = value(p)
    if not 0 <= p <= 1:
        raise ValueError('invalid_probability')
    return p


@dataclass(frozen=True)
class FairSignal:
    probability: float
    available_at: float
    reference: str


@dataclass(frozen=True)
class Reserve:
    name: str
    per_contract: float
    available_at: float
    reference: str
    calibrated: bool = False


@dataclass(frozen=True)
class MakerFeeTerms:
    rate: float
    available_at: float
    reference: str
    balance_precision: str
    valid_until: float | None = None
    # A new quote has no previous fills/rounding credit. Partial fill sequences
    # require realized order accumulator accounting; this is one full fill.
    fill_assumption: str = 'new_order_single_full_fill'


@dataclass(frozen=True)
class QuoteRequest:
    decision_id: str
    decision_at: float
    quantity: float
    fair: FairSignal
    reserves: tuple[Reserve, ...]
    fees: MakerFeeTerms
    price_ranges: tuple[dict, ...]
    minimum_profit_per_contract: float
    policy_reference: str
    policy_available_at: float


@dataclass(frozen=True)
class AcceptanceEstimate:
    candidate_id: str
    acceptance_probability: float
    conditional_yes_probability: float | None
    available_at: float
    training_data_available_at: float
    calibrated: bool
    model_version: str
    calibration_reference: str
    conditional_outcome_calibration_reference: str
    scope_reference: str
    label_unit: str = 'full_requested_quantity_rfq_acceptance'


class AcceptanceModel(Protocol):
    def manifest(self) -> dict:
        """Versioned calibration/feature/scope identity for replay manifests."""
        ...

    def predict(self, request: QuoteRequest, candidate: dict) -> AcceptanceEstimate:
        """Use only request-time features; no eventual prints or settlements."""
        ...


@lru_cache(maxsize=64)
def seller_prices(ranges):
    """Mirror the *submitted NO-side* grid; never assume grid symmetry."""
    asks = set()
    unit = Decimal('.0001')
    for raw_start, raw_end, raw_step in ranges:
        start, end, step = map(value, (raw_start, raw_end, raw_step))
        if not 0 <= start < end <= 1 or step <= 0 or any(x % unit for x in (start, end, step)):
            raise ValueError('invalid_four_decimal_price_grid')
        p = start
        while p < end:
            if 0 < p < 1:
                asks.add(1-p)
            p += step
    if not asks:
        raise ValueError('empty_native_no_price_grid')
    return tuple(sorted(asks))


def validate(request):
    asof(request.fair.available_at, request.decision_at, request.fair.reference)
    asof(request.policy_available_at, request.decision_at, request.policy_reference)
    asof(request.fees.available_at, request.decision_at, request.fees.reference)
    probability(request.fair.probability)
    q, edge = value(request.quantity), value(request.minimum_profit_per_contract)
    if not request.decision_id or q <= 0 or q % Decimal('.01') or edge < 0:
        raise ValueError('invalid_quantity_or_minimum_profit')
    if not 0 <= value(request.fees.rate) < 1 or request.fees.balance_precision not in ('.0001', '.01'):
        raise ValueError('invalid_fee_terms')
    if request.fees.fill_assumption != 'new_order_single_full_fill':
        raise ValueError('unsupported_fill_fee_assumption')
    if request.fees.valid_until is not None and finite_time(request.fees.valid_until) <= request.decision_at:
        raise ValueError('expired_fee_terms')
    names = [r.name for r in request.reserves]
    if len(names) != len(set(names)) or not {'uncertainty', 'dependence', 'adverse_selection', 'inventory'} <= set(names):
        raise ValueError('duplicate_or_missing_reserve_components')
    for reserve in request.reserves:
        asof(reserve.available_at, request.decision_at, reserve.reference)
        if value(reserve.per_contract) < 0:
            raise ValueError('negative_reserve')
    return seller_prices(tuple((str(g['start']), str(g['end']), str(g['step'])) for g in request.price_ranges))


def candidate_ledger(request, yes_ask, floor, requested_markup):
    q, fair = value(request.quantity), probability(request.fair.probability)
    no_bid = 1-yes_ask
    cash_fee = kalshi_fill_fee(q, no_bid, request.fees.rate, 'buy', request.fees.balance_precision, accumulator=0)
    fee = cash_fee['net_fee']
    reserve_cash = {r.name:q*value(r.per_contract) for r in request.reserves}
    gross = q*(yes_ask-fair)
    required_profit = q*value(request.minimum_profit_per_contract)
    remaining = gross-fee-sum(reserve_cash.values())
    identity = f'{request.decision_id}:{q}:{yes_ask}'
    return {'candidate_id':hashlib.sha256(identity.encode()).hexdigest(),
            'yes_ask':float(yes_ask), 'no_bid':float(no_bid),
            'quote':{'yes_bid':'0.0000', 'no_bid':f'{no_bid:.4f}'},
            'quantity':float(q), 'customer_yes_premium':float(q*yes_ask),
            'maker_no_principal':float(q*no_bid), 'maximum_loss':float(q*no_bid+fee),
            'fair_yes_probability':float(fair), 'gross_point_margin':float(gross),
            'maker_fee':float(fee), 'maker_fee_components':{k:float(v) if isinstance(v,Decimal) else v for k,v in cash_fee.items()},
            'reserve_dollars':{k:float(v) for k,v in reserve_cash.items()},
            'required_minimum_profit':float(required_profit),
            'point_expected_profit':float(gross-fee),
            'margin_after_reserves_and_fee':float(remaining),
            'floor_surplus_after_minimum_profit':float(remaining-required_profit),
            'eligible':remaining >= required_profit,
            'eligibility_scope':'pricing_and_information_only_external_risk_check_required',
            'commercial_markup_requested_per_contract':float(requested_markup),
            'commercial_markup_above_floor_per_contract':float(yes_ask-floor),
            'acceptance':None, 'expected_incremental_profit':None}


class QuotePolicy:
    """Return reviewable candidates; optimize only with validated acceptance inputs."""
    def manifest(self):
        return {'component':'quote_policy_v1', 'mode':'research_shadow_only',
                'fee_engine':'kalshi_fill_fee', 'submitted_side':'buy_no',
                'objective':'P(full_acceptance) * [quantity * (YES ask - conditional YES probability) - maker cash fee]',
                'missing_acceptance_behavior':'no_optimizer_selection',
                'reserves':'eligibility_guards_not_additional_realized_fees',
                'code_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}

    def evaluate(self, request: QuoteRequest, commercial_markups=(0.,), acceptance_model: AcceptanceModel | None = None):
        prices = validate(request)
        markups = sorted({value(x) for x in commercial_markups})
        if not markups or any(x < 0 for x in markups):
            raise ValueError('invalid_commercial_markups')
        lower = probability(request.fair.probability)+sum(value(r.per_contract) for r in request.reserves)+value(request.minimum_profit_per_contract)
        floor = None
        for ask in prices[bisect_left(prices, lower):]:
            if candidate_ledger(request, ask, ask, Decimal(0))['eligible']:
                floor = ask
                break
        result = {'mode':'research_shadow_only', 'decision_id':request.decision_id,
                  'decision_at':request.decision_at, 'manifest':self.manifest(),
                  'input_components':asdict(request), 'floor':None, 'candidates':[],
                  'selected':None, 'selection_status':'no_feasible_price', 'orders_enabled':False}
        if floor is None:
            return result
        result['floor'] = candidate_ledger(request, floor, floor, Decimal(0))
        result['selection_status'] = 'acceptance_model_unavailable'
        seen = set()
        for markup in markups:
            idx = bisect_left(prices, floor+markup)
            if idx == len(prices):
                continue
            candidate = candidate_ledger(request, prices[idx], floor, markup)
            if candidate['candidate_id'] in seen:
                continue
            seen.add(candidate['candidate_id'])
            if acceptance_model is not None:
                try:
                    estimate = acceptance_model.predict(deepcopy(request), deepcopy(candidate))
                    self._validate_estimate(request, candidate, estimate)
                    p = probability(estimate.acceptance_probability)
                    conditional = probability(estimate.conditional_yes_probability)
                    conditional_profit = value(request.quantity)*(value(candidate['yes_ask'])-conditional)-value(candidate['maker_fee'])
                    candidate['acceptance'] = asdict(estimate)
                    candidate['conditional_expected_profit'] = float(conditional_profit)
                    candidate['expected_incremental_profit'] = float(p*conditional_profit)
                except (ValueError, TypeError, AttributeError) as exc:
                    candidate['acceptance_rejection_reason'] = str(exc)
            result['candidates'].append(candidate)
        if acceptance_model is not None:
            eligible = [c for c in result['candidates'] if c['eligible'] and c['expected_incremental_profit'] is not None]
            if eligible:
                best = max(eligible, key=lambda c:(c['expected_incremental_profit'], -c['yes_ask']))
                # No-quote has zero incremental profit. A calibrated losing
                # candidate must not be selected merely because it is the best.
                if best['expected_incremental_profit'] > 0:
                    result.update(selected=best, selection_status='calibrated_expected_profit_selection')
                else:
                    result['selection_status'] = 'no_positive_expected_incremental_profit'
            else:
                result['selection_status'] = 'acceptance_inputs_unusable'
        return result

    @staticmethod
    def _validate_estimate(request, candidate, estimate):
        if type(estimate.calibrated) is not bool or estimate.calibrated is not True or not estimate.model_version or not estimate.scope_reference:
            raise ValueError('acceptance_model_not_calibrated_or_provenanced')
        if estimate.candidate_id != candidate['candidate_id'] or estimate.label_unit != 'full_requested_quantity_rfq_acceptance':
            raise ValueError('acceptance_prediction_candidate_or_label_mismatch')
        asof(estimate.available_at, request.decision_at, estimate.calibration_reference)
        asof(estimate.training_data_available_at, request.decision_at, estimate.conditional_outcome_calibration_reference)
        if estimate.training_data_available_at > estimate.available_at:
            raise ValueError('training_information_after_prediction')
        if estimate.conditional_yes_probability is None:
            raise ValueError('conditional_outcome_model_unavailable')
        probability(estimate.acceptance_probability)
        probability(estimate.conditional_yes_probability)


class ShadowQuoteAudit:
    """Opt-in sidecar: log candidate floors, never replace the engine's quote.

    Fee metadata availability and account precision must be supplied explicitly.
    Existing stressed pricing is decomposed without asserting it is calibrated.
    """
    def __init__(self, fee_terms_available_at, balance_precision, policy_available_at,
                 policy_reference, commercial_markups=(0., .005, .01), acceptance_model=None):
        self.fee_terms_available_at = fee_terms_available_at
        self.balance_precision = balance_precision
        self.policy_available_at = policy_available_at
        self.policy_reference = policy_reference
        self.commercial_markups = commercial_markups
        self.acceptance_model = acceptance_model
        self.policy = QuotePolicy()

    def manifest(self):
        return {**self.policy.manifest(), 'sidecar':'logging_only',
                'fee_terms_available_at':self.fee_terms_available_at,
                'balance_precision':self.balance_precision,
                'policy_available_at':self.policy_available_at,
                'policy_reference':self.policy_reference,
                'commercial_markups':list(self.commercial_markups),
                'acceptance_model':None if self.acceptance_model is None else self.acceptance_model.manifest()}

    def evaluate(self, *, decision_id, decision_at, quantity, pricing, terms, minimum_profit_per_contract):
        p, upper, stressed = (float(pricing['joint']['point']), float(pricing['joint']['upper']), float(pricing['stressed_upper']))
        if not p <= upper <= stressed:
            raise ValueError('non_nested_existing_pricing_bounds')
        values = {'uncertainty':upper-p, 'dependence':stressed-upper,
                  'adverse_selection':0., 'inventory':0.,
                  'strategy_signal':float(pricing.get('extra_edge_per_share',0.))}
        reserves = tuple(Reserve(k,v,decision_at,
            'existing_pricing_output' if k in ('uncertainty','dependence','strategy_signal') else 'not_estimated_explicit_zero_assumption',False) for k,v in values.items())
        request = QuoteRequest(decision_id,decision_at,quantity,
            FairSignal(p,decision_at,'causal_shadow_pricing_output:'+decision_id),reserves,
            MakerFeeTerms(terms['maker_fee_rate'],self.fee_terms_available_at,terms['fee_reference'],
                          self.balance_precision,terms.get('valid_until')),
            tuple(terms['price_ranges']),minimum_profit_per_contract,self.policy_reference,self.policy_available_at)
        return self.policy.evaluate(request,self.commercial_markups,self.acceptance_model)

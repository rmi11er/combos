import json
import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('candidate', ROOT / 'scripts/build_nfl_candidate_runtime.py')
candidate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(candidate)


def mapping(key, period='full_game', selector=True):
    return {'market_key': key, 'mapping_reference': 'ref:'+key, 'kalshi_ticker': key, 'period': period,
            'market_type': 'totals', 'pinnacle': {'selector_reference': 'x'} if selector else {}}


def test_candidate_intersects_exact_selector_and_verified_payoff():
    runtime = {'mappings': [mapping('a'), mapping('b', 'first_half'), mapping('c', selector=False)]}
    reviews = [{'market_key': 'a', 'review': {'status': 'completed_period_binary_verified'}},
               {'market_key': 'b', 'review': {'status': 'completed_period_binary_verified'}},
               {'market_key': 'c', 'review': {'status': 'completed_period_binary_verified'}}]
    result, excluded = candidate.build(runtime, reviews)
    assert [m['market_key'] for m in result['mappings']] == ['a']
    assert len(excluded) == 2
    assert result['launch_status'].startswith('blocked_candidate')


def test_void_and_missing_reviews_are_not_promoted():
    runtime = {'mappings': [mapping('a'), mapping('b')]}
    reviews = [{'market_key': 'a', 'review': {'status': 'void_basis_required'}}]
    result, excluded = candidate.build(runtime, reviews)
    assert result['mappings'] == []
    reasons = {reason for row in excluded for reason in row['reasons']}
    assert 'payoff_void_basis_required' in reasons
    assert 'payoff_review_missing' in reasons


def test_usd_limit_assumption_is_explicit_and_stays_shadow_only():
    runtime = {'mappings': [mapping('a')]}
    reviews = [{'market_key': 'a', 'review': {'status': 'completed_period_binary_verified'}}]
    result, _ = candidate.build(runtime, reviews, shadow_assume_usd_limits=True)
    spec = result['mappings'][0]['pinnacle']
    assert spec['limit_currency'] == 'USD'
    assert result['shadow_assumptions']['orders_enabled'] is False
    assert result['mappings'][0].get('pricing_block_reason') is None


def test_risk_overrides_are_recorded_in_candidate_scope():
    runtime = {'mappings': [mapping('a')]}
    reviews = [{'market_key': 'a', 'review': {'status': 'completed_period_binary_verified'}}]
    result, _ = candidate.build(runtime, reviews,
                                risk_overrides={'per_contract_dollars': 500,
                                                'per_combo_dollars': 500,
                                                'per_fixture_dollars': 500,
                                                'maximum_committed_dollars': 5000})
    assert result['per_contract_dollars'] == 500
    assert result['candidate_scope']['risk_overrides']['maximum_committed_dollars'] == 5000

"""Read-only preflight for initializing live execution risk.

This gate never changes a risk ledger, account balance or exchange state. It
distinguishes a desired strategy budget from authenticated available cash.
"""
from decimal import Decimal, InvalidOperation
import math


def _money(value):
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError('invalid startup cash') from None
    if not result.is_finite():
        raise ValueError('invalid startup cash')
    return result


def assess_startup(account_summary, strategy_budget, now, *, maximum_age_seconds=30,
                   shared_activity_cleared=False, required_mapping_count=None,
                   verified_mapping_count=None):
    """Return a conservative startup decision from archived authenticated reads."""
    if not isinstance(account_summary, dict):
        raise ValueError('account summary required')
    if not math.isfinite(now) or maximum_age_seconds <= 0:
        raise ValueError('invalid startup clock')
    assessment = account_summary.get('cash_assessment')
    if not isinstance(assessment, dict):
        return {'ready_for_ledger_initialization': False,
                'reasons': ['cash_assessment_missing'],
                'strategy_budget_dollars': str(_money(strategy_budget)),
                'maximum_initial_strategy_cash_dollars': '0',
                'ledger_mutated': False}
    reasons = []
    budget = _money(strategy_budget)
    if budget <= 0:
        raise ValueError('positive strategy budget required')
    try:
        cash = _money(assessment['reported_available_dollars'])
        initial = _money(assessment['maximum_initial_strategy_cash_dollars'])
        received = float(assessment['received_at'])
    except (KeyError, TypeError, ValueError):
        raise ValueError('malformed cash assessment') from None
    if not math.isfinite(received) or now - received > maximum_age_seconds:
        reasons.append('cash_read_stale')
    if cash <= 0 or initial <= 0 or assessment.get('positive_cash_available') is not True:
        reasons.append('nonpositive_available_cash')
    if account_summary.get('atomic_snapshot') is not True:
        reasons.append('account_reads_not_atomic')
    for name, value in account_summary.get('collections', {}).items():
        if value.get('pagination_complete') is not True:
            reasons.append(name + '_pagination_incomplete')
    if account_summary.get('collections', {}).get('positions', {}).get('rows', 0):
        reasons.append('existing_positions')
    if account_summary.get('collections', {}).get('resting_orders', {}).get('rows', 0):
        reasons.append('existing_resting_orders')
    if account_summary.get('collections', {}).get('self_quotes', {}).get('rows', 0):
        reasons.append('existing_self_quotes')
    if not shared_activity_cleared:
        reasons.append('shared_account_activity_unresolved')
    if required_mapping_count is not None and verified_mapping_count != required_mapping_count:
        reasons.append('production_mappings_incomplete')
    return {'ready_for_ledger_initialization': not reasons,
            'reasons': reasons,
            'strategy_budget_dollars': str(budget),
            'maximum_initial_strategy_cash_dollars': str(max(Decimal(0), min(cash, budget)).quantize(Decimal('.0001'))),
            'cash_received_at': received,
            'ledger_mutated': False,
            'orders_submitted': 0}

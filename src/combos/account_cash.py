"""Read-only balance evidence; no transfer, ledger reset or funding mutation."""
from decimal import Decimal, InvalidOperation, ROUND_FLOOR
import math


def number(value):
    try:d=Decimal(str(value))
    except InvalidOperation:raise ValueError('invalid account balance') from None
    if not d.is_finite():raise ValueError('nonfinite account balance')
    return d


def assess_account_cash(envelope, strategy_budget, now, maximum_age_seconds=30):
    if envelope.get('method')!='GET' or envelope.get('path')!='/trade-api/v2/portfolio/balance' or envelope.get('http_status')!=200:
        raise ValueError('successful authenticated balance read required')
    received=envelope['received_at'];began=envelope['request_started_at']
    if not all(math.isfinite(v) for v in (received,began,now,maximum_age_seconds)) or maximum_age_seconds<=0:
        raise ValueError('invalid balance observation timing')
    if not began<=received<=now or now-began>maximum_age_seconds:
        raise ValueError('stale or invalid balance read')
    payload=envelope['payload']
    if 'balance_dollars' in payload:
        cash=number(payload['balance_dollars']);basis='balance_dollars'
        if cash%Decimal('.0001'):raise ValueError('unsupported balance precision')
    else:
        cents=number(payload['balance'])
        if cents!=cents.to_integral_value():raise ValueError('legacy balance must be integer cents')
        cash=cents/100;basis='legacy_integer_cents'
    budget=number(strategy_budget)
    if budget<=0:raise ValueError('positive strategy budget required')
    budget=(budget*10000).to_integral_value(rounding=ROUND_FLOOR)/10000
    allocation=max(Decimal(0),min(cash,budget))
    subaccount=envelope.get('params',{}).get('subaccount',0)
    if type(subaccount) is not int or not 0<=subaccount<=63:raise ValueError('invalid balance subaccount')
    return {'subaccount':subaccount,'reported_available_dollars':str(cash),
            'strategy_budget_dollars':str(budget),'maximum_initial_strategy_cash_dollars':str(allocation),
            'positive_cash_available':allocation>0,'balance_field':basis,
            'non_cent_balance_observed':bool(cash%Decimal('.01')),
            'received_at':received,'ledger_initialization_authorized':False,
            'remaining_checks':['positions_and_open_orders','shared_account_activity','account_precision_evidence']}

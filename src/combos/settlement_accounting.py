"""Reconcile buy-only market settlement economics without asserting cash release.

Settlement revenue excludes collateral returned by earlier YES/NO netting. The
inferred pair credit below is an economic identity, not an observed cash transfer.
Selling/position transfers require a richer inventory ledger and are rejected.
"""
from decimal import Decimal

from .execution_fills import normalize_fill
from .quote_reconciliation import decimal, timestamp


def reconcile_buy_only_settlement(settlement, raw_fills, subaccount):
    if type(subaccount) is not int or not 0 <= subaccount <= 63:
        raise ValueError('explicit settlement subaccount required')
    if type(settlement['exchange_index']) is not int or settlement['exchange_index'] < 0:
        raise ValueError('invalid settlement exchange')
    if not isinstance(settlement['ticker'], str) or not settlement['ticker']:
        raise ValueError('settlement ticker required')
    settled_at = timestamp(settlement['settled_time'])
    result = settlement['market_result']
    if result not in ('yes', 'no', 'scalar'):
        raise ValueError('unknown settlement result')
    value = settlement.get('value')
    if result in ('yes', 'no'):
        expected_value = 100 if result == 'yes' else 0
        if value is not None and (type(value) is not int or value != expected_value):
            raise ValueError('settlement value contradicts result')
        value = expected_value
    elif type(value) is not int or not 0 <= value <= 100:
        raise ValueError('scalar payout value required')
    revenue = settlement['revenue']
    if type(revenue) is not int or revenue < 0:
        raise ValueError('settlement revenue must be nonnegative integer cents')
    quantity = {side: Decimal(0) for side in ('yes', 'no')}
    cost = dict(quantity)
    fees = Decimal(0)
    seen = {}
    for raw in raw_fills:
        fill = normalize_fill(raw)
        for key, expected in (('ticker', settlement['ticker']),
                ('exchange_index', settlement['exchange_index']), ('subaccount_number', subaccount)):
            if fill[key] != expected or type(fill[key]) is not type(expected):
                raise ValueError('settlement fill identity mismatch')
        if fill['action'] != 'buy':
            raise ValueError('sell activity requires inventory reconciliation')
        key = fill['fill_id']
        if key in seen:
            if seen[key] != fill:
                raise ValueError('conflicting duplicate fill')
            continue
        seen[key] = fill
        quantity[fill['side']] += decimal(fill['quantity'])
        cost[fill['side']] += decimal(fill['principal'])
        fees += decimal(fill['fee'])
    for side in quantity:
        count = decimal(settlement[side+'_count_fp'])
        basis = decimal(settlement[side+'_total_cost_dollars'])
        if count < 0 or count % Decimal('.01') or basis < 0:
            raise ValueError('invalid settlement quantity or cost')
        if count != quantity[side] or basis != cost[side]:
            raise ValueError('fill quantities or cost do not reconcile to settlement')
    if decimal(settlement['fee_cost']) != fees:
        raise ValueError('fill fees do not reconcile to settlement')
    yes_value = Decimal(value)/100
    gross_payoff = quantity['yes']*yes_value + quantity['no']*(1-yes_value)
    pairs = min(quantity.values())
    net_payoff = gross_payoff-pairs
    posted = Decimal(revenue)/100
    difference = net_payoff-posted
    pnl = gross_payoff-sum(cost.values())-fees
    return {'ticker': settlement['ticker'], 'subaccount': subaccount,
            'exchange_index': settlement['exchange_index'], 'settled_at': settled_at,
            'unique_fills': len(seen), 'fees_dollars': str(fees),
            'gross_payoff_dollars': str(gross_payoff),
            'inferred_prior_pair_credit_dollars': str(pairs),
            'expected_net_settlement_dollars': str(net_payoff),
            'reported_settlement_revenue_dollars': str(posted),
            'net_settlement_difference_dollars': str(difference),
            'settlement_revenue_matches': difference == 0,
            'economic_pnl_before_balance_adjustments_dollars': str(pnl),
            'pnl_using_only_posted_settlement_dollars': str(posted-sum(cost.values())-fees),
            'capital_release_authorized': False,
            'remaining_checks': ['complete_fill_history_and_no_transfers',
                'prior_netting_cash_credit' if pairs else 'account_cash_reconciliation',
                'settlement_rounding_and_balance_reconciliation', 'strategy_order_ownership']}

import pytest
from combos.account_cash import assess_account_cash


def envelope(payload):
    return {'method':'GET','path':'/trade-api/v2/portfolio/balance','http_status':200,
            'params':{'subaccount':0},'request_started_at':100,'received_at':101,'payload':payload}


def test_fixed_point_balance_takes_precedence_and_negative_never_funds():
    result=assess_account_cash(envelope({'balance_dollars':'-1048.3917','balance':-104839}),10000,102)
    assert result['reported_available_dollars']=='-1048.3917'
    assert not result['positive_cash_available']
    assert result['maximum_initial_strategy_cash_dollars']=='0'
    assert result['non_cent_balance_observed']


def test_available_cash_and_strategy_budget_both_limit_initialization():
    assert assess_account_cash(envelope({'balance_dollars':'12345.6789'}),10000,102)['maximum_initial_strategy_cash_dollars']=='10000'
    assert assess_account_cash(envelope({'balance':12345}),10000,102)['maximum_initial_strategy_cash_dollars']=='123.45'
    with pytest.raises(ValueError,match='stale'):
        assess_account_cash(envelope({'balance':12345}),10000,140)
    with pytest.raises(ValueError,match='nonfinite'):
        assess_account_cash(envelope({'balance_dollars':'NaN'}),10000,102)

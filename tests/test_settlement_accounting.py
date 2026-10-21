import pytest
from combos.settlement_accounting import reconcile_buy_only_settlement
from test_execution_ownership import fill


def case():
    yes = dict(fill(), fill_id='yes', side='yes', count_fp='10', yes_price_dollars='.9', no_price_dollars='.1', fee_cost='.01')
    no = dict(fill(), fill_id='no', count_fp='2', yes_price_dollars='.08', no_price_dollars='.92', fee_cost='.002')
    settlement = {'ticker':'M', 'exchange_index':0, 'market_result':'no', 'value':0,
        'yes_count_fp':'10', 'no_count_fp':'2', 'yes_total_cost_dollars':'9',
        'no_total_cost_dollars':'1.84', 'fee_cost':'.012', 'revenue':0,
        'settled_time':'2026-09-06T20:00:00Z'}
    return settlement, [yes, no]


def test_netted_pair_is_not_paid_again_at_settlement():
    s, f = case()
    r = reconcile_buy_only_settlement(s, f+f, 0)
    assert r['unique_fills'] == 2 and r['settlement_revenue_matches']
    assert r['inferred_prior_pair_credit_dollars'] == '2'
    assert r['economic_pnl_before_balance_adjustments_dollars'] == '-8.852'
    assert r['pnl_using_only_posted_settlement_dollars'] == '-10.852'
    assert not r['capital_release_authorized']


def test_scalar_rounding_is_exposed_not_silently_credited():
    s, f = case(); s.update(market_result='scalar', value=33, yes_count_fp='10.01', yes_total_cost_dollars='9.009', revenue=264)
    f[0]['count_fp']='10.01'
    r = reconcile_buy_only_settlement(s, f, 0)
    assert not r['settlement_revenue_matches']
    assert r['net_settlement_difference_dollars'] == '0.0033'


@pytest.mark.parametrize('field,value', [('no_count_fp','3'), ('fee_cost','.02'), ('revenue',False), ('value',100)])
def test_settlement_mismatch_rejected(field,value):
    s,f=case();s[field]=value
    with pytest.raises(ValueError):reconcile_buy_only_settlement(s,f,0)


@pytest.mark.parametrize('field,value', [('action','sell'), ('subaccount_number',1), ('exchange_index',1), ('ticker','other')])
def test_unsupported_or_foreign_fill_rejected(field,value):
    s,f=case();f[0][field]=value
    with pytest.raises(ValueError):reconcile_buy_only_settlement(s,f,0)


def test_no_pair_single_direction_settlement():
    s,f=case();s.update(yes_count_fp='0',yes_total_cost_dollars='0',fee_cost='.002',revenue=200)
    r=reconcile_buy_only_settlement(s,[f[1]],0)
    assert r['settlement_revenue_matches'] and r['inferred_prior_pair_credit_dollars']=='0'
    assert r['economic_pnl_before_balance_adjustments_dollars']=='0.158'

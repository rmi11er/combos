from decimal import Decimal as D
import pytest
from combos.research_rfq_quote import solve_quote


def test_full_size_and_fee_edge():
    r=solve_quote('.4','.45',0,'.003',contracts='1000')
    assert r['quantity_bound']==1000
    assert r['reference_compensation']>=D('3')
    assert r['fragmentation_cash_bound']>=r['single_fill_cash']
    assert r['yes_ask']>D('.403')


def test_target_upper_bound():
    r=solve_quote('.4','.45',.25,'.003',target_cost='10')
    q,p=r['quantity_bound'],r['yes_ask']
    assert q*p>=10 and (q-D('.01'))*p<10
    assert r['sizing_basis']=='target_cost_upper_bound'


def test_infeasible_and_ambiguous():
    with pytest.raises(ValueError):solve_quote('.999','.999',0,'.003',contracts=1)
    with pytest.raises(ValueError):solve_quote('.4','.5',0,0,contracts=1,target_cost=1)


def test_buy_no_cash_identity():
    r=solve_quote('.2','.3',1,0,contracts='1.6')
    assert r['single_fill_cash']==D('1.6')*r['no_bid']+r['single_fill_fee']
    assert r['point_compensation']-r['reference_compensation']==D('1.6')*D('.1')


def test_captured_piecewise_grid():
    r=solve_quote('.4031','.5',0,0,contracts=10,rate=0,ranges=[{'start':'.01','end':'.99','step':'.001'}])
    assert r['yes_ask']==D('.404')
    with pytest.raises(ValueError):
        solve_quote('.4','.5',0,0,contracts=10,ranges=[{'start':0,'end':1,'step':0}])

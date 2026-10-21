from dataclasses import replace
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from research_partial_sizing import fee, size_rows
from combos.backtest import BacktestConfig, run_backtest
import pytest


def row(identifier, at, settled=10, outcome=0):
    return dict(model='k',evaluation_id=identifier,at=at,quantity=100.,yes_price=.5,
        maker_fee=fee(100,.5,.035),fair_point=.4,stressed_upper=.45,
        quote_allowed=True,risk_multiplier=1.,settled_at=settled,yes_settlement=outcome,
        buckets={'contract':['a','b'],'fixture':['a','b'],'combo':['ab']},
        source={'nlegs':2,'fee_basis':{'rate':.035}})


def test_partial_reprices_fee_and_settlement_controls_reuse():
    c=BacktestConfig(entry_basis='point',per_contract_dollars=10,per_combo_dollars=10)
    rows, accepted=size_rows([row('a',1),row('b',2),row('c',11,20)],c)
    assert rows[0]['quantity']==19
    assert rows[0]['maker_fee']==fee(19,.5,.035)
    assert accepted=={('k','a'),('k','c')}
    result=run_backtest(rows,0,30,c,constrained=True)
    assert {(r['model'],r['evaluation_id']) for r in result['decisions'] if r['accepted']}==accepted


def test_future_outcome_does_not_affect_pre_settlement_sizing():
    c=BacktestConfig(entry_basis='point',capital_dollars=10)
    a,_=size_rows([row('a',1,outcome=0),row('b',2)],c)
    b,_=size_rows([row('a',1,outcome=1),row('b',2)],c)
    assert [(r['quantity'],r['quote_allowed']) for r in a]==[(r['quantity'],r['quote_allowed']) for r in b]


def test_contract_risk_multiplier_and_complementary_bucket_reuse():
    c=BacktestConfig(entry_basis='point',per_contract_dollars=10)
    r=row('a',1);r['risk_multiplier']=.5
    rows,_=size_rows([r,row('b',2)],c)
    assert rows[0]['quantity']==9
    assert rows[1]['quantity']==10


def test_fraction_limits_each_ticket_without_resetting_event_exposure():
    c=BacktestConfig(entry_basis='point',per_contract_dollars=1000,per_combo_dollars=1000,per_fixture_dollars=10)
    rows,accepted=size_rows([row(str(i),i+1,20) for i in range(5)],c,event_fraction=.25)
    assert [r['quantity'] for r in rows]==[4.,4.,4.,4.,3.]
    result=run_backtest(rows,0,30,c,constrained=True)
    assert {(r['model'],r['evaluation_id']) for r in result['decisions'] if r['accepted']}==accepted
    for value in (0,-1,1.01,float('nan'),float('inf')):
        with pytest.raises(ValueError):size_rows([],c,event_fraction=value)

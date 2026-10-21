from decimal import Decimal
from itertools import product
from pathlib import Path
import sys

import numpy as np
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from combos.research_spend_risk import target_size,payout_upper
from spend_same_game_study import cohort


@pytest.mark.parametrize('budget',[5,10,20,50])
@pytest.mark.parametrize('price',['.05','.1','.25','.5','.1234'])
@pytest.mark.parametrize('precision',['.0001','.01'])
def test_spend_maximality(budget,price,precision):
    r=target_size(budget,price,'.07',precision=precision)
    assert r['quantity']%Decimal('.01')==0
    assert r['total_debit']<=budget
    assert r['next_quantity_budget_charge']>budget
    assert r['orders_enabled'] is False


def test_fee_mode_and_price_dependent_quantity():
    assert target_size(10,'.1',0)['quantity']==100
    assert target_size(10,'.5',0)['quantity']==20
    r=target_size(10,'.1','.07',excludes_fees=True)
    assert r['quantity']==100 and r['total_debit']>10 and r['budget_charge']==10
    assert target_size('.0001','.9','.07')['quantity']==0


def test_exact_amounts_not_neighborhoods():
    assert cohort('5.0000')=='$5'
    assert cohort('4.9999')=='other_spend'
    assert cohort('50.0001')=='other_spend'
    assert cohort(None)=='fixed_or_missing'


def test_aligned_volume_does_not_net():
    r=payout_upper([[('a','yes')]]*100,np.ones(100))
    assert r['payout_upper_units']==100
    assert r['guaranteed_reduction_units']==0


def test_equal_money_is_not_equal_contract_offset():
    assert payout_upper([[('a','yes')],[('a','no')]],[10,10])['payout_upper_units']==pytest.approx(10)
    r=payout_upper([[('a','yes')],[('a','no')]],[100,20])
    assert r['payout_upper_units']==pytest.approx(100)
    assert r['cash_collateral_credit']==0


def test_scalar_safe_even_for_contradictory_or_repeated_legs():
    tickets=[[('a','yes'),('a','no')],[('a','yes'),('a','yes')],
             [('a','no'),('b','yes')],[('b','no')]]
    weights=[4,1,2,3];r=payout_upper(tickets,weights)
    for a,b in product(np.linspace(0,1,21),repeat=2):
        state={'a':a,'b':b}
        actual=sum(q*np.prod([state[t] if s=='yes' else 1-state[t] for t,s in ticket]) for q,ticket in zip(weights,tickets))
        assert actual<=r['payout_upper_units']+1e-7


def test_same_game_complementary_branch():
    r=payout_upper([[('a','yes'),('b','yes')],[('a','yes'),('b','no')]],[1,1])
    assert r['payout_upper_units']==pytest.approx(1)


@pytest.mark.parametrize('weights',[[0],[-1],[float('nan')]])
def test_invalid_risk_weights(weights):
    with pytest.raises(ValueError):payout_upper([[('a','yes')]],weights)

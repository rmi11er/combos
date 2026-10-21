import math
import pytest
from src.combos.pricing import *

def test_fee_interval_and_no_complement():
    yes=fee_expanded_book(.4,.42,.07)
    no=fee_expanded_book(*selected_book(.4,.42,'no'),.07)
    assert yes.lower==pytest.approx(.4-.07*.4*.6)
    assert yes.point==pytest.approx(.41)
    assert no.lower==pytest.approx(1-yes.upper)
    assert no.upper==pytest.approx(1-yes.lower)

def test_customer_and_maker_units():
    n=customer_quantity(10,.1,include_customer_fee=False)
    assert n==100
    econ=short_yes_economics(n,.1,.09,maker_rate=0)
    assert econ['customer_premium']==10
    assert econ['maximum_loss']==90
    assert econ['expected_edge']==pytest.approx(1)
    n=customer_quantity(10,.1)
    assert n*.1+total_fee(n,.1,.07)<=10+1e-9
    assert (n+.01)*.1+total_fee(n+.01,.1,.07)>10

def test_weighted_blend_rejects_missing_future_and_different_payoffs():
    i=Interval(.4,.5,.6)
    vs=[VenueFair(v,i,90,w,90,'game:full:home') for v,w in [('kalshi',1),('polymarket',2),('pinnacle',3)]]
    assert liquidity_blend(vs,100,'game:full:home').point==.5
    with pytest.raises(ValueError): liquidity_blend(vs[:2],100,'game:full:home')
    with pytest.raises(ValueError): liquidity_blend(vs,80,'game:full:home')
    with pytest.raises(ValueError): liquidity_blend(vs,100,'game:firsthalf:home')

def test_no_vig_and_joint_bounds():
    assert pinnacle_fair(1.91,1.91).point==.5
    l=Interval(.2,.3,.4);r=Interval(.5,.6,.7)
    j=joint_independence(l,r)
    assert j.point==.18
    assert j.upper==pytest.approx(.28)
    assert j.upper<=stressed_joint_upper(l,r,.05)<=min(l.upper,r.upper)

def test_fee_rounded_with_cost_fractional_quantity():
    q,p,r=12.34,.9876,.035
    fee=total_fee(q,p,r)
    assert fee>=q*r*p*(1-p)-1e-12
    assert (q*p+fee)*10000==pytest.approx(round((q*p+fee)*10000))

def test_uncapped_observed_size_and_cash_limited_partial_allocation():
    assert affordable_short_yes_quantity(10000,1000,.2)==1000
    n=affordable_short_yes_quantity(100,1000,.2)
    assert 0<n<1000
    assert short_yes_economics(n,.2,.15)['maximum_loss']<=100+1e-10
    assert short_yes_economics(n+.01,.2,.15)['maximum_loss']>100
    assert n*.2>10
    assert affordable_short_yes_quantity(0,1000,.2)==0

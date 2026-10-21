import sys
from pathlib import Path
import pytest
from itertools import product

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from offsession_inventory_study import probability, intersection, variance_delta, Scenario

def legs(a=1):return [('A','A',a,False),('B','B',1,False)]

def test_opposite_leg_full_size_can_increase_portfolio_variance():
    p={'A':.5,'B':.5};book={'AB':(legs(),100)}
    assert probability(legs(),p)==.25
    assert intersection(legs(),legs(-1),p)==0
    assert variance_delta(legs(-1),100,book,p)==pytest.approx(625)
    assert variance_delta(legs(-1),50,book,p)==pytest.approx(-156.25)

def test_favorable_other_leg_probability_changes_hedge_benefit():
    p={'A':.5,'B':.8};book={'AB':(legs(),100)}
    assert variance_delta(legs(-1),100,book,p)==pytest.approx(-800)

def test_fractional_tie_complements_not_mutually_exclusive():
    a=[('A','A',1,True)];b=[('A','A',-1,True)]
    assert intersection(a,b,{'A':.5})==pytest.approx(.0025)

def test_frechet_intersection_is_not_less_than_independent_bound():
    a=legs();b=[('C','C',1,False),('D','D',1,False)]
    p={k:.5 for k in 'ABCD'}
    assert intersection(a,b,p)==.0625
    assert intersection(a,b,p,True)==.25

def test_combined_pool_checks_signed_and_gross_together():
    s=Scenario('test',True,False);s.used['fixture:A',0]=800;s.used['fixture:A',1]=100
    q={'mult':1}
    assert s.fits(q,100,[('fixture:A',-1)])
    assert not s.fits(q,201,[('fixture:A',-1)])
    assert not s.fits(q,101,[('fixture:A',0)])

def test_payoff_credit_only_from_filled_opposing_premium():
    s=Scenario('payoff',True,True,payoff_credit=True)
    s.used['fixture:A',1]=900;s.used['fixture:A',-1]=300
    assert s.risk('fixture:A',s.used)==900
    s.held_premium['fixture:A',-1]=100
    assert s.risk('fixture:A',s.used)==800
    assert s.fits({'mult':1},200,[('fixture:A',1)])
    assert not s.fits({'mult':1},201,[('fixture:A',1)])
    # Filled hedge premiums never create cash-netting credit.
    s.used['total',0]=1200
    assert s.risk('total',s.used)==1200

def test_fixture_payoff_bound_covers_other_leg_completions_and_tie():
    # Sold 100 A&B at .25, sold 50 not-A&C at .25, plus gross other risk $7.
    s=Scenario('bound',True,True,payoff_credit=True)
    s.held['fixture:A',1]=75;s.held['fixture:A',-1]=37.5;s.held['fixture:A',0]=7
    s.held_premium['fixture:A',1]=25;s.held_premium['fixture:A',-1]=12.5
    bound=s.risk('fixture:A',s.held)
    assert bound==pytest.approx(69.5)
    for a,b,c,d in product((0.,.5,1.),(0.,1.),(0.,1.),(0.,1.)):
        loss=100*a*b+50*(1-a)*c-37.5+10*d-3
        assert loss<=bound+1e-10

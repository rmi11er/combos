import pytest
from combos.research_capacity import CapacityReplay
B={'contract':['same_team_payoff'],'combo':['combo1'],'fixture':['game1']}


def test_expiry_versus_filled_retention():
    for ttl,expected in [(3,True),(None,False)]:
        l=CapacityReplay(100,dict.fromkeys(B,100),ttl)
        assert l.admit('a',0,75,B)['admitted']
        assert not l.admit('b',2,75,B)['admitted']
        assert l.admit('c',3,75,B)['admitted']==expected


def test_fungibility_no_netting_and_all_binding_limits():
    l=CapacityReplay(1000,{'contract':100,'combo':1000,'fixture':120})
    assert l.admit('a',0,80,B)['admitted']
    b={**B,'combo':['different_combo']}
    r=l.admit('b',1,50,b)
    assert set(r['binding_limits'])=={'contract','fixture'}
    assert r['committed_units']==800000


def test_duplicate_and_clock_regression():
    l=CapacityReplay(100,dict.fromkeys(B,100),3)
    l.admit('a',0,10,B)
    assert 'duplicate_rfq' in l.admit('a',4,10,B)['binding_limits']
    with pytest.raises(ValueError):l.admit('c',3,10,B)


def test_defensive_cap_counts_existing_exposure_without_releasing_it():
    l=CapacityReplay(100,dict.fromkeys(B,100))
    assert l.admit('a',0,40,B)['admitted']
    r=l.admit('b',1,11,B,risk_multiplier=.5)
    assert set(r['binding_limits'])=={'contract','combo','fixture'}
    assert r['committed_units']==400000
    assert l.admit('c',2,10,B,risk_multiplier=.5)['admitted']
    assert l.admit('d',3,40,B,risk_multiplier=1)['admitted']


@pytest.mark.parametrize('multiplier',[0,-1,1.01,float('nan'),float('inf')])
def test_invalid_multiplier_cannot_mutate_ledger(multiplier):
    l=CapacityReplay(100,dict.fromkeys(B,100))
    with pytest.raises(ValueError):l.admit('a',0,1,B,risk_multiplier=multiplier)
    assert not l.seen and not l.active

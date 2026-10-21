import pytest
from src.combos.creators import CreatorWatchlist,CreatorPolicy

def test_long_legs_not_automatic_blacklist_and_duplicate_id_no_effect():
    w=CreatorWatchlist();legs=[str(i) for i in range(30)]
    w.observe('r','c',1,legs);w.observe('r','c',2,legs)
    s=w.state('c')
    assert s['evidence']['requests']==1
    assert s['status']=='review' and not s['blacklisted']

def test_spam_chronology_and_window():
    w=CreatorWatchlist(CreatorPolicy(spam_requests=3))
    w.observe('a','c',1,['x','y']);w.observe('b','c',2,['x','y'])
    assert not w.state('c')['reasons']
    w.observe('c','c',3,['x','y'])
    assert 'repetitive_request_burst' in w.state('c')['reasons']
    with pytest.raises(ValueError):w.observe('d','c',2,['x','y'])

def test_blacklist_requires_three_prior_nonoverlapping_bursts():
    w=CreatorWatchlist(CreatorPolicy(spam_requests=3))
    for start in [1,62,123]:
        for offset in range(3):
            assert not w.state('c')['blacklisted']
            at=start+offset
            w.observe(str(at),'c',at,['x','y'])
    assert w.state('c')['evidence']['spam_bursts']==3
    assert w.state('c')['blacklisted']

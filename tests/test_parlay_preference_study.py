from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from parlay_preference_study import features, fixture, raw_features, mix, fit
from parlay_preference_diagnostics import matched_alternatives


def test_favorite_legs_are_not_favorite_combo():
    f=features([.6,.6,.6])
    assert f['all_favorites']
    assert f['fair']==pytest.approx(.216)
    assert f['implied_gross_multiple']==pytest.approx(1/.216)
    assert not features([.5,.7])['all_favorites']


def test_matching_retains_actual_but_does_not_invent_overlap():
    r=matched_alternatives([.8,.7],.0001)
    assert r['matches']==1
    assert r['observed_favorite_share']==r['uniform_matched_favorite_share']==1
    r=matched_alternatives([.6,.6],1)
    assert r['matches']==4
    assert r['uniform_matched_favorite_share']==.5


@pytest.mark.parametrize('p',[[0,.5],[1,.5],[float('nan'),.5],[.5]])
def test_invalid_probability(p):
    with pytest.raises(ValueError):features(p)


def test_same_game_cross_family_and_spend():
    legs=[dict(event_ticker='KXNFLGAME-26SEP09NESEA',market_ticker='KXNFLGAME-26SEP09NESEA-SEA',side='yes'),
          dict(event_ticker='KXNFLRSHYDS-26SEP09NESEA',market_ticker='KXNFLRSHYDS-26SEP09NESEA-SEAEXAMPLE1-40',side='no')]
    r=raw_features(dict(id='one',creator_id='creator',mve_selected_legs=legs,target_cost_dollars='2'))
    assert r['same_nfl_game'] and r['has_nfl_prop'] and r['nfl_only']
    assert r['players']==['SEAEXAMPLE1 [NO]']
    assert r['target_cost']==2
    assert fixture(dict(event_ticker='KXNFLSB-27')) is None


def test_creator_balancing_and_deduplication():
    rows=[]
    for i in range(10):
        rows.append(dict(creator='a' if i<9 else 'b',signature='a' if i<9 else 'b',
                         nlegs=2,has_nfl_prop=i<9,same_nfl_game=i<9,target_cost=2,
                         players=[],families=[],fixture_unknown_legs=0))
    r=mix(pd.DataFrame(rows))
    assert r['mix']['requests']['has_nfl_prop']==.9
    assert r['mix']['equal_creator']['has_nfl_prop']==.5
    assert r['mix']['creator_ticket_once']['n']==2


def test_composition_regression_recovers_known_signal():
    rng=np.random.default_rng(9);n=300
    f=pd.DataFrame(dict(mid=rng.uniform(.1,.5,n),sum_width=rng.uniform(1,5,n),
        hours=rng.uniform(1,10,n),max_age=rng.uniform(60,120,n),quantity=rng.uniform(1,20,n),
        nlegs=rng.integers(2,5,n),day=np.repeat(['a','b','c'],100),
        favorite_share=rng.uniform(0,1,n),weakest=rng.uniform(.1,.5,n),dispersion=rng.uniform(0,.2,n)))
    f['edge']=2*f.favorite_share+3*f.weakest-4*f.dispersion
    r=fit(f,np.ones(n))
    assert r['incremental_partial_r2']==pytest.approx(1)
    assert r['coefficients']['favorite_share']==pytest.approx(2)
    assert r['coefficients']['weakest']==pytest.approx(3)

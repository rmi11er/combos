from pathlib import Path
import sys

import numpy as np
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from spread_calibration_study import components, summarize, regression, fit


def row(q=10., p=.5, fair=.4, outcome=1., width=2., fixture='a'):
    r = dict(quantity=q, yes_price=p, fair_point=fair, maker_fee=.1, yes_settlement=outcome,
             settled_at=100 if outcome is not None else None, raw=width, nlegs=2,
             buckets={'fixture':[fixture]})
    r['values']=components(r)
    return r


def test_decomposition_and_identical_unknown_cohort():
    a=row(); b=row(q=90,p=.9,fair=.1,outcome=None)
    assert a['values']==pytest.approx(dict(compensation=9.,residual=-60.,realized=-51.))
    result=summarize([a,b])
    assert result['components_cents']==pytest.approx(a['values'])
    assert result['unknown_quantity']==90
    assert result['all_priced_compensation_cents']!=result['components_cents']['compensation']


def test_regression_components_add_and_fixture_deletions_not_confidence_intervals():
    rows=[row(q=i+1,p=.2+i*.02,fair=.3,outcome=i%2,width=i,fixture=str(i//2)) for i in range(10)]
    r=regression(rows,'raw','spread_only')
    c=r['components']
    assert c['compensation']['coefficients']['spread_cents']+c['residual']['coefficients']['spread_cents']==pytest.approx(c['realized']['coefficients']['spread_cents'])
    assert r['leave_one_fixture_out_refits']==5
    assert r['standard_errors'] is None and r['p_values'] is None


def test_collinear_adjustment_reported_not_spurious_coefficient():
    rows=[row(width=i,p=.1+i*.02) for i in range(8)]
    assert regression(rows,'raw','price_and_leg_count')['status']=='rank_deficient'


def test_weighted_fit_matches_replicated_integer_weights():
    x=np.array([[1,0],[1,1],[1,2]],dtype=float)
    y=np.array([[1,2,3],[2,4,6],[8,3,11]],dtype=float)
    w=np.array([1,3,6])
    a=fit(x,y,w)[0]
    b=fit(np.repeat(x,w,axis=0),np.repeat(y,w,axis=0),np.ones(w.sum()))[0]
    assert np.allclose(a,b)


def test_unknown_only_is_not_a_zero_residual():
    assert regression([row(outcome=None)],'raw','spread_only')['status']=='no_known_outcomes'

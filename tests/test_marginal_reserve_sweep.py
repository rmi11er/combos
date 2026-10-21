import sqlite3
import pytest
from mlb_marginal_reserve_sweep import with_reserve


def test_reserve_interpolation_retains_point_and_original_bound():
    db = sqlite3.connect(':memory:')
    db.execute('CREATE TABLE features(evaluation_id,model,point,independent_upper)')
    db.execute('INSERT INTO features VALUES(?,?,?,?)', ('a','k',.2,.3))
    row = {'evaluation_id':'a','fair_point':.2,'stressed_upper':.5,'source':{}}
    for fraction, expected in [(0,.2),(.25,.225),(1,.3)]:
        value = next(with_reserve(iter([row]),db,'k',fraction,'synthetic'))
        assert value['stressed_upper'] == pytest.approx(expected)
        assert value['fair_point'] == .2
        assert value['source']['quote_reserve_candidate']['original_joint_upper'] == .5
    assert row['stressed_upper'] == .5
    with pytest.raises(ValueError,match='missing_or_mismatched'):
        next(with_reserve(iter([row]),db,'other',.25,'synthetic'))
    with pytest.raises(ValueError,match='out_of_range'):
        next(with_reserve(iter([row]),db,'k',1.1,'synthetic'))

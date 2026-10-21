import gzip
import json
from pathlib import Path
import sys
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from joint_reserve_components import independent_upper,analyze,MODELS


def test_no_leg_uses_one_minus_lower():
    c=[{'kalshi':{'interval':{'lower':.2,'upper':.4}}},
       {'kalshi':{'interval':{'lower':.3,'upper':.6}}}]
    assert independent_upper([{'side':'yes'},{'side':'no'}],c,'kalshi')==pytest.approx(.28)
    with pytest.raises(ValueError):independent_upper([{'side':'unknown'}],c[:1],'kalshi')


def test_marginal_and_joint_reserve_partition(tmp_path):
    (tmp_path/'replay').mkdir();(tmp_path/'common_model_report').mkdir()
    context={'evaluation_id':'x','legs':[{'side':'yes'},{'side':'no'}],
             'context':[{m:{'interval':{'lower':.4,'upper':.6}} for m in MODELS}]*2}
    with gzip.open(tmp_path/'replay/pricing_context.jsonl.gz','wt') as f:f.write(json.dumps(context)+'\n')
    with gzip.open(tmp_path/'common_model_report/unconstrained_decisions.jsonl.gz','wt') as f:
        for m in MODELS:
            row={'evaluation_id':'x','model':m,'quantity':100,'fair_point':.25,'stressed_upper':.5,
                 'yes_price':.4,'maker_fee':1,'yes_settlement':0,'quote_allowed':True,'required_net_edge':.3,
                 'accepted':True,'entry_basis':'point','source':{'nlegs':2}}
            f.write(json.dumps(row)+'\n')
    for row in analyze([tmp_path])['rows']:
        assert row['marginal_reserve_cents']==pytest.approx(11)
        assert row['additional_joint_reserve_cents']==pytest.approx(14)
        assert row['point_prints']==row['independent_upper_prints']==1
        assert row['stressed_prints']==0
        assert row['independent_upper_net']==39

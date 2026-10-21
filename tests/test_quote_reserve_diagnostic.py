import gzip
import json
from pathlib import Path
import sys
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from quote_reserve_diagnostic import analyze


def test_point_only_and_stress_qualified_rows(tmp_path):
    path=tmp_path/'rows.gz'
    base={'quantity':100,'maker_fee':1,'required_net_edge':.3,'entry_basis':'point',
          'fair_point':.4,'yes_price':.5,'quote_allowed':True,'yes_settlement':0,
          'accepted':True,'model':'kalshi','source':{'nlegs':2}}
    with gzip.open(path,'wt') as f:
        for upper in (.45,.55):f.write(json.dumps({**base,'stressed_upper':upper})+'\n')
    row=analyze([path])['rows'][0]
    assert row['point_pass_prints']==2 and row['stressed_pass_prints']==1
    assert row['point_pass_net']==98 and row['stressed_pass_net']==49
    assert row['point_print_retention_under_stress']==.5
    assert row['quantity_weighted_reserve_cents']==pytest.approx(10)


def test_rejects_funded_admission_in_place_of_unlimited_ledger(tmp_path):
    path=tmp_path/'rows.gz'
    row={'quantity':100,'maker_fee':0,'required_net_edge':.3,'entry_basis':'point',
         'fair_point':.4,'stressed_upper':.45,'yes_price':.5,'quote_allowed':True,
         'accepted':False}
    with gzip.open(path,'wt') as f:f.write(json.dumps(row)+'\n')
    with pytest.raises(AssertionError,match='unlimited'):analyze([path])

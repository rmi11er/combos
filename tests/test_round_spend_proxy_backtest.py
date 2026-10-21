from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from round_spend_proxy_backtest import label,allowed


def test_round_spend_is_not_round_contract_count():
    assert label({'quantity':100,'yes_price':.1},.01)[0]
    assert not label({'quantity':10,'yes_price':.35},.01)[0]


def test_tolerance_boundary_and_fee_basis():
    assert label({'quantity':100,'yes_price':.0999},.01)[0]
    assert not label({'quantity':100,'yes_price':.0998},.01)[0]
    assert label({'quantity':100,'yes_price':.1},0)[0]
    assert not label({'quantity':100,'yes_price':.1},.01,'.07')[0]


def test_whole_contract_budget_sensitivity():
    assert label({'quantity':28,'yes_price':.35},'whole_contract_budget')[0]
    assert not label({'quantity':27,'yes_price':.35},'whole_contract_budget')[0]
    assert not label({'quantity':28.5,'yes_price':.35},'whole_contract_budget')[0]


def test_conditional_hurdle_does_not_override_existing_scope():
    row={'quantity':100,'yes_price':.502,'fair_point':.5,'maker_fee':0,'quote_allowed':True}
    assert allowed(row,'round015_other03',True)
    assert not allowed(row,'round015_other03',False)
    row['quote_allowed']=False
    assert not allowed(row,'round015_other03',True)

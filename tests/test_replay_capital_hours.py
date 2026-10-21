import importlib.util
from pathlib import Path
import pytest
spec = importlib.util.spec_from_file_location('capital_hours', Path(__file__).parents[1]/'scripts/replay_capital_hours.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def ledger(settlement=7200, open_fills=0):
    return {'summaries':[{'model':'a','trade_attributed_pnl':2,'peak_committed_cash':6,'open_fills':open_fills,'unresolved_outcomes':0}],
            'curves':[{'model':'a','at':0,'committed_cash':0}, {'model':'a','at':3600,'committed_cash':6}, {'model':'a','at':7200,'committed_cash':0 if settlement==7200 else 6}, {'model':'a','at':10800,'committed_cash':0 if settlement==7200 else 6}],
            'fills':[{'model':'a','filled_at':3600,'settled_at':settlement,'quantity':10,'yes_price':.5,'maker_fee':1}]}


def test_settlement_not_trade_attribution_releases_cash():
    result=m.measure(ledger())[0]
    assert result['committed_dollar_hours']==6
    assert result['average_committed_cash']==2
    assert result['net_pnl_per_1000_committed_dollar_hours']==pytest.approx(1000/3)


def test_open_position_integrates_to_window_and_withholds_ratio():
    result=m.measure(ledger(None,1))[0]
    assert result['committed_dollar_hours']==12
    assert result['net_pnl_per_1000_committed_dollar_hours'] is None


def test_mismatched_cash_rejected():
    d=ledger();d['curves'][1]['committed_cash']=5
    with pytest.raises(ValueError,match='mismatch'):m.measure(d)

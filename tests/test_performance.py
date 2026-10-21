import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import pytest
from combos.performance import build_curves


def evaluation():
 return {'model':'m','evaluation_id':'r','at':10,'quantity':100,'yes_price':.2,'point_edge':3,'stressed_edge':-2}


def fill():
 return {'model':'m','fill_id':'f','filled_at':10,'quantity':100,'yes_price':.2,'maker_fee':1,
         'settled_at':30,'yes_settlement':0,'basis':'simulated_execution'}


def test_evaluations_never_create_pnl_or_filled_volume():
 result=build_curves([evaluation()],[],0,40)[-1]
 assert result['observed_yes_premium']==20 and result['observed_payout_notional']==100
 assert result['point_edge']==3 and result['stressed_edge']==-2
 assert result['realized_pnl']==result['filled_payout_notional']==result['maker_cash_spent']==0


def test_no_side_pnl_recognized_at_settlement_and_fee_counted_once():
 rows=build_curves([evaluation()],[fill()],0,40)
 before=next(r for r in rows if r['at']==10);after=rows[-1]
 assert before['maker_cash_spent']==81 and before['filled_yes_premium']==20
 assert before['realized_pnl']==0 and before['committed_cash']==81
 assert after['realized_pnl']==19 and after['committed_cash']==0
 assert after['filled_payout_notional']==100
 losing=fill();losing['yes_settlement']=1
 assert build_curves([],[losing],0,40)[-1]['realized_pnl']==-81
 fractional=fill();fractional['yes_settlement']=.5
 assert build_curves([],[fractional],0,40)[-1]['realized_pnl']==-31


def test_unsettled_positions_do_not_receive_future_pnl():
 result=build_curves([],[fill()],0,20)[-1]
 assert result['realized_pnl']==0 and result['committed_cash']==81


def test_duplicate_and_ambiguous_execution_bases_rejected():
 with pytest.raises(ValueError,match='duplicate evaluation'):build_curves([evaluation(),evaluation()],[],0,40)
 with pytest.raises(ValueError,match='duplicate fill'):build_curves([],[fill(),fill()],0,40)
 other=fill();other.update(fill_id='other',basis='actual_execution')
 with pytest.raises(ValueError,match='mix execution bases'):build_curves([],[fill(),other],0,40)
 bad=fill();bad['settled_at']=5
 with pytest.raises(ValueError,match='precedes'):build_curves([],[bad],0,40)

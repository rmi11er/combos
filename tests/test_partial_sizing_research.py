import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from combos.partial_sizing_research import run_partial,sized
from combos.backtest import BacktestConfig
import pytest

def row(i='a',at=1,q=1000,settled=8,outcome=0,mult=1,guard=True):
 r={'model':'m','evaluation_id':i,'at':at,'quantity':q,'yes_price':.5,'fair_point':.4,'stressed_upper':.6,'maker_fee':0,'quote_allowed':guard,'risk_multiplier':mult,'settled_at':settled,'yes_settlement':outcome,'buckets':{'contract':['winner'],'fixture':['f'],'combo':[i]},'source':{'fee_basis':{'rate':.035}}}
 return sized(r,int(q*100))

def test_cap_fee_and_fractional_grid():
 r=run_partial([row()],0,10)
 f=r['fills'][0]
 assert 196<f['quantity']<197
 assert f['maker_fee']==sized(row(),int(round(f['quantity']*100)))['maker_fee']
 assert f['quantity']*.5+f['maker_fee']<=100
 assert (f['quantity']+.01)*.5+sized(row(),int(round(f['quantity']*100))+1)['maker_fee']>100

def test_actual_settlement_releases_capacity_and_cash_not_trade_pnl():
 rows=[row('a',1,settled=5),row('b',2,settled=8),row('c',6,settled=9)]
 r=run_partial(rows,0,10)
 assert [f['fill_id'] for f in r['fills']]==['a','c']
 assert r['fills'][0]['pnl_attributed_at']==1
 assert next(x for x in r['curves'] if x['at']==1)['realized_pnl']==0

def test_unknown_outcome_keeps_risk_reserved_and_bounds_unresolved():
 r=run_partial([row('a',1,settled=None,outcome=None),row('b',6)],0,10)
 assert len(r['fills'])==1
 assert r['summaries'][0]['unresolved_outcomes']==1
 assert r['summaries'][0]['trade_attributed_pnl']==0
 assert r['summaries'][0]['ending_committed_cash']>99

def test_guard_multiplier_and_no_outcome_lookahead():
 r=run_partial([row(mult=.5)],0,10)
 assert r['fills'][0]['quantity']*.5+r['fills'][0]['maker_fee']<=50
 a=run_partial([row(outcome=0,settled=11)],0,10)
 b=run_partial([row(outcome=1,settled=11)],0,10)
 assert a['sizing_audit']==b['sizing_audit']
 assert not run_partial([row(guard=False)],0,10)['fills']

def test_fee_input_must_reconcile():
 r=row();r['maker_fee']+=.01
 with pytest.raises(ValueError,match='fee'):run_partial([r],0,10)

def test_capital_limit_and_shared_canonical_direction_bucket():
 cfg=BacktestConfig(entry_basis='point',capital_dollars=10)
 r=run_partial([row('a'),row('b',at=2)],0,10,cfg)
 assert len(r['fills'])==1
 assert r['summaries'][0]['peak_committed_cash']<=10

def test_settled_profit_can_fund_only_later_orders():
 cfg=BacktestConfig(entry_basis='point',capital_dollars=10)
 r=run_partial([row('a',1,settled=5),row('b',2,settled=9),row('c',6,settled=9)],0,10,cfg)
 assert [f['fill_id'] for f in r['fills']]==['a','c']
 assert r['fills'][1]['quantity']>r['fills'][0]['quantity']
 assert r['summaries'][0]['additional_funding_above_reporting_base']<.001

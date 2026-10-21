import pytest
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from combos.historical_fair import History,historical_observations,compare_fairs


def inputs(at=100):
 return ('key',(40,{'yes_bid':{'close_dollars':.48},'yes_ask':{'close_dollars':.52}}),
         (40,{'p':.5}),(70,{'price':2,'limit':100,'active':True},70,{'price':2,'limit':100,'active':True}),at)


def test_historical_equal_depth_retains_distinct_fee_effects():
 rows=historical_observations(*inputs(),depth=123)
 assert all(r['historical_only'] for r in rows)
 assert rows[0]['yes_bid_size']==rows[1]['yes_bid_size']==123
 fair,obs=compare_fairs(rows)
 assert obs[1].interval.upper-obs[1].interval.lower < obs[0].interval.upper-obs[0].interval.lower
 assert rows[1]['depth_imputed'] and rows[1]['spread_imputed']
 assert fair['venues']['polymarket']['two_sided_depth_payout_dollars']==123


def test_history_inactive_and_delay_no_lookahead():
 h=History([{'at':10,'price':2,'active':True},{'at':20,'active':False},{'at':30,'price':3,'active':True}],'at')
 with pytest.raises(ValueError,match='no_prior'):h.latest(39,30)
 assert h.latest(49,30)[1]['price']==2
 with pytest.raises(ValueError,match='inactive'):h.latest(50,30)
 assert h.latest(60,30)[1]['price']==3
 with pytest.raises(ValueError,match='lookahead'):historical_observations(*inputs(99))


def test_forward_engine_rejects_historical_imputation(tmp_path):
 from test_runtime import config,observation,rfq,seed,drain
 from combos.event_store import EventStore
 from combos.shadow_engine import ShadowEngine
 from combos.creator_service import CreatorService
 store=EventStore(tmp_path/'events.sqlite');engine=ShadowEngine(store,config(),replay=True);seed(store)
 drain(CreatorService(store),engine)
 row=observation('a','kalshi');row['depth_imputed']=True
 with store.transaction():store.put('observations',row['market_key']+':kalshi',row)
 with pytest.raises(ValueError,match='historical_imputation_forbidden'):engine.fair(rfq()['mve_selected_legs'],100)
 store.close()


def test_available_historical_depth_and_spread_take_precedence():
 args=list(inputs());args[1][1].update(yes_bid_size=200,yes_ask_size=300)
 rows=historical_observations(*args)
 assert not rows[0]['depth_imputed'] and rows[1]['depth_imputed']
 assert rows[1]['yes_bid_size']==200 and rows[1]['yes_ask_size']==300
 args[2][1].update(yes_bid_size=90,yes_ask_size=95,yes_bid=.49,yes_ask=.51)
 rows=historical_observations(*args)
 assert not rows[1]['depth_imputed'] and not rows[1]['spread_imputed']
 assert rows[1]['yes_bid_size']==90 and rows[1]['yes_bid']==.49

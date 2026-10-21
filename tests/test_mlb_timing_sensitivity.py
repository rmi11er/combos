import sys,gzip,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import mlb_timing_sensitivity as m
from combos.historical_fair import History
from combos.pricing import Interval
import pytest

def test_extra_source_lag_causal_boundaries_without_trade_shift():
 h=m.DelayedHistory(History([{'t':10,'p':.2},{'t':40,'p':.8}],'t'),{'startTs':0,'endTs':200},30)
 assert h.latest(129,60)[0]==10
 assert h.latest(130,60)[0]==40
 with pytest.raises(ValueError,match='uncovered'):h.latest(89,60)

def test_extra_lag_preserves_latest_inactive_guard():
 h=m.DelayedHistory(History([{'t':10,'p':.2},{'t':40,'p':.8,'active':False}],'t'),{'startTs':0,'endTs':200},30)
 with pytest.raises(ValueError,match='inactive'):h.latest(130,60)

def test_replace_preserves_trade_fee_outcome_and_risk_data():
 base={'at':180,'maker_fee':.1234,'quantity':10,'yes_price':.5,'settled_at':500,'yes_settlement':0,'source':{'fee_basis':{'rate':.035}},'buckets':{'contract':['a'],'fixture':['f'],'combo':['c']}}
 interval=Interval(.2,.3,.4);values=[(({ 'kalshi':(interval,True,.5)}, {}, {}),{'side':'yes'}),(({ 'kalshi':(interval,True,1)}, {}, {}),{'side':'no'})]
 row=m.replacement(base,'kalshi',values)
 for key in base:assert row[key]==base[key]
 assert row['risk_multiplier']==.5 and row['fair_point']==pytest.approx(.21)

def test_fee_effective_at_actual_trade_not_delayed_lookup(monkeypatch,tmp_path):
 import mlb_model_replay as original
 class K:
  publication_delay=60
  def at(self,ticker,at):return {'yes_bid':.3,'yes_ask':.5,'source_at':at-self.publication_delay,'available_at':at}
 def init(self,exchange,pinnacle_bundle=None,depth=1000,delay=30,fee_scenario=None):
  self.exchange=exchange;self.kalshi=K();self.maps={'t':{'status':'matched','token':'123','fee_rate':0}};self.pm={};self.pin={};self.depth=depth;self.delay=delay;self.fee_scenario=fee_scenario
 monkeypatch.setattr(original.SourceFairs,'__init__',init)
 seen=[]
 def fee(scenario,ticker,at,kind):seen.append(at);return (.07 if at>=100 else .035),{'reference':'dated-test'}
 monkeypatch.setattr(original,'kalshi_rate',fee)
 (tmp_path/'polymarket').mkdir()
 with gzip.open(tmp_path/'polymarket/123.json.gz','wt') as f:json.dump({'status':200,'params':{'startTs':0,'endTs':500},'payload':{'history':[{'t':0,'p':.2},{'t':100,'p':.8}]}},f)
 provider=m.TimingSourceFairs(tmp_path,{'polymarket_rate_policy':'native'},120)
 fairs,context,errors=provider.timed_fair('t',180)
 assert seen==[180]
 assert context['kalshi']['fee_basis']['taker_rate']==.07
 assert context['polymarket']['state_at']==0 and context['polymarket']['available_at']==180
 assert fairs['polymarket'][0].point==.2

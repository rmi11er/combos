import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from nfl_moneyline_replay import pm_prior,merge_intervals,risk_buckets,selected,mapping_identity
from combos.pricing import Interval
import pytest

def mapping(team):
 return {'team':team,'fixture':{'away':'Rams','away_code':'LAR','home':'Carolina','home_code':'CAR','scheduled_start':'2026-01-10T16:30:00-05:00'}}

def test_causal_publication_and_no_gap_carry():
 assert pm_prior([10,20],[.4,.9],[[0,40]],79)==(.4,10)
 assert pm_prior([10,20],[.4,.9],[[0,40]],80)==(.9,20)
 with pytest.raises(ValueError,match='no_prior'):pm_prior([10],[.4],[[0,40]],69)
 with pytest.raises(ValueError,match='uncovered'):pm_prior([10],[.4],[[0,20],[40,50]],90)
 with pytest.raises(ValueError,match='before_coverage'):pm_prior([10],[.4],[[0,20],[40,50]],105)

def test_merge_coverage_keeps_holes():
 assert merge_intervals([[10,20],[0,10],[30,40]])==[[0,20],[30,40]]

def test_opposite_team_no_equivalent_risk_and_combo():
 maps={'RAMS':mapping('Rams'),'CAR':mapping('Carolina')}
 a=risk_buckets([{'market_ticker':'RAMS','side':'yes'}],maps)
 b=risk_buckets([{'market_ticker':'CAR','side':'no'}],maps)
 c=risk_buckets([{'market_ticker':'CAR','side':'yes'}],maps)
 assert a==b
 assert a['contract']==c['contract'] and a['combo']!=c['combo']

def test_no_interval_complement_and_invalid_side():
 v=selected(Interval(.1,.3,.5),'no');assert v.point==.7 and v.lower==.5 and v.upper==.9
 with pytest.raises(ValueError):selected(v,'other')

def test_fixed_blends_combine_legs_before_product_and_causal_context():
 from nfl_moneyline_replay import Sources
 class K:
  def at(self,ticker,at):return {'interval':{'lower':.3,'point':.4,'upper':.5},'yes_bid':.39,'yes_ask':.41,'source_at':at-60,'available_at':at}
 source=Sources.__new__(Sources);source.k=K();source.maps={'t':{'capture_end_at':200,'polymarket_token':'p'}};source.pm={'p':([10,100],[.6,.95],[[0,200]])}
 fairs,context=source.leg('t',80)
 assert fairs['polymarket'].point==.6
 assert fairs['exchange_blend_equal'].point==.5
 assert abs(fairs['exchange_blend_pm75'].point-.55)<1e-10
 assert context['polymarket']['available_at']==70
 with pytest.raises(ValueError,match='kickoff'):source.leg('t',200)

import json
from pathlib import Path
import sys
from copy import deepcopy
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from enable_nfl_moneylines import enable
from authorize_nfl_event_mappings import accepted_review
from combos.settlement_policy import normalize_pinnacle_interval
from combos.observations import Observation
from combos.pricing import Interval


@pytest.mark.parametrize('mode',['shadow','live'])
def test_moneyline_migration_preserves_execution_settings(mode):
    source=json.loads((ROOT/'runs/morning_research_20260908/pinnacle_delivery_mapping_review/runtime_reviewed_candidates.json').read_text())
    reviews={r['market_key']:r['review'] for r in json.loads((ROOT/'runs/nfl_all_payoff_enumeration_20260909/rows.json').read_text())}
    config={'mode':mode,'mappings':[],'orders_enabled':False,'per_fixture_dollars':1000}
    result,report=enable(config,source['mappings'],reviews,'test-hash')
    assert report['enabled']==52 and len(report['unavailable'])==2
    assert result['mode']==mode and result['orders_enabled'] is False
    assert result['per_fixture_dollars']==1000 and not config['mappings']
    assert all(not m.get('pricing_block_reason') for m in result['mappings'])
    assert sum(m['period']=='full_game' for m in result['mappings'])==32
    again,_=enable(result,source['mappings'],reviews,'test-hash')
    assert result==again


def test_void_acceptance_does_not_authorize_other_families_or_mismatches():
    m={'market_type':'moneyline','period':'full_game','pinnacle':{'catalog':{'marketType':'moneyline','period':'result'}}}
    r={'status':'void_basis_required','market_type':'moneyline','period':'full_game','void_score_pairs':101,'mismatches':[]}
    assert accepted_review(m,r)
    assert not accepted_review(dict(m,market_type='totals'),r)
    assert not accepted_review(m,dict(r,mismatches=[{'bad':True}]))
    assert not accepted_review(m,dict(r,status='exact_selector_unavailable'))


@pytest.mark.parametrize('point',[.2,.8])
def test_period_spread_selector_does_not_get_second_tie_discount(point):
    o=Observation('key','pinnacle',100,100,True,Interval(point-.01,point,point+.01),100,100,'source','mapping',None)
    m={'market_type':'moneyline','period':'first_half','pinnacle':{'catalog':{'marketType':'spreads'}}}
    assert normalize_pinnacle_interval(o,m) is o
    full=dict(m,period='full_game',pinnacle={'catalog':{'marketType':'moneyline'}})
    assert normalize_pinnacle_interval(o,full).interval.point==pytest.approx(.99*point+.005)

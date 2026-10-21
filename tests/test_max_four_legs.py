from copy import deepcopy
from itertools import permutations
import pytest
from test_runtime import config, observation, rfq, add, drain, decisions
from combos.event_store import EventStore
from combos.creator_service import CreatorService
from combos.shadow_engine import ShadowEngine
from combos.pricing import Interval, stressed_joint_upper
from combos.joint_pricing import price_joint
from combos.rfq_scope import collection_candidate
from combos.weighted_fair import WeightPolicy


def setup(store, n=4):
    c=config(); template=c['mappings'][0]
    c['mappings']=[{**deepcopy(template),'fixture_key':k+':A-B','market_key':k+':A-B:moneyline:A',
                   'kalshi_ticker':'KXNFLGAME-'+k} for k in 'abcd'[:n]]
    for k in 'abcd'[:n]:
        for v in ('kalshi','polymarket','pinnacle'):
            add(store,'observation',observation(k,v),k+v,100)
    request=rfq();request['mve_selected_legs']=[{'market_ticker':m['kalshi_ticker'],'side':'yes'} for m in c['mappings']]
    return c,request


def test_higher_order_dependence_is_not_pairwise_independence():
    v=Interval(.5,.5,.5)
    # Three bits: 111,100,010,001 each have mass .25. Every pair is independent,
    # yet the all-win probability is .25, twice the product of the marginals.
    assert price_joint([v]*3,0)['stressed_upper']==pytest.approx(.25)
    assert price_joint([v]*4,0)['stressed_upper']==pytest.approx(1/6)
    assert price_joint([v]*3,.05)['stressed_upper'] >= .25
    assert price_joint([v]*4,1)['stressed_upper']==pytest.approx(.5)


def test_bounds_are_order_invariant_and_preserve_two_leg_behavior():
    values=[Interval(.1,.15,.2),Interval(.4,.45,.5),Interval(.8,.85,.9),Interval(.3,.4,.6)]
    expected=price_joint(values,.05)
    for ordering in permutations(values):
        result=price_joint(ordering,.05)
        assert result['stressed_upper']==expected['stressed_upper']
        assert result['joint']['upper'] <= result['stressed_upper'] <= min(v.upper for v in values)
    assert price_joint(values[:2],.05)['stressed_upper']==stressed_joint_upper(*values[:2],.05)


@pytest.mark.parametrize('n',[2,3,4])
def test_full_size_quotes_charge_all_legs_and_release_once(tmp_path,n):
    store=EventStore(tmp_path/'events.sqlite');c,r=setup(store,n)
    engine=ShadowEngine(store,c,WeightPolicy(delayed_pinnacle=True),replay=True);creators=CreatorService(store)
    add(store,'rfq',r,'r',100);drain(creators,engine)
    result=decisions(store)[0]
    assert result['status']=='shadow_quote',result.get('reason')
    assert result['quantity']==10 and result['leg_count']==n
    checks=result['risk']['checks']
    assert len([v for v in checks if v['bucket'].startswith('contract:')])==n
    assert len([v for v in checks if v['bucket'].startswith('fixture:')])==n
    cost=result['economics']['maximum_loss']
    assert engine.risk.available()/10000==pytest.approx(10000-cost,abs=.0001)
    add(store,'heartbeat',{},'expire',104);drain(creators,engine)
    assert engine.risk.available()==100000000
    store.close()


@pytest.mark.parametrize('change,reason',[
    ('fifth','outside_leg_count_scope'),('prop','outside_supported_non_player_scope'),
    ('period','reviewed_mapping_missing'),('duplicate','same_fixture_joint_model_required')])
def test_scope_exclusions_are_logged_and_reserve_nothing(tmp_path,change,reason):
    store=EventStore(tmp_path/'events.sqlite');c,r=setup(store)
    if change=='fifth':r['mve_selected_legs'].append(deepcopy(r['mve_selected_legs'][0]))
    if change=='prop':r['mve_selected_legs'][-1]['market_ticker']='KXNFLANYTD-player'
    if change=='period':r['mve_selected_legs'][-1]['market_ticker']='KXNFL1H-game'
    if change=='duplicate':r['mve_selected_legs'][-1]=deepcopy(r['mve_selected_legs'][0])
    engine=ShadowEngine(store,c,replay=True);creators=CreatorService(store)
    add(store,'rfq',r,'r',100);drain(creators,engine)
    assert decisions(store)[0]['reason']==reason
    assert engine.risk.available()==100000000
    if change in ('fifth','prop'):assert not collection_candidate(r['mve_selected_legs'],c)
    if change=='period':assert collection_candidate(r['mve_selected_legs'],c)
    store.close()


def test_fourth_leg_cutoff_and_started_latch_without_delayed_weight_switch(tmp_path):
    store=EventStore(tmp_path/'events.sqlite');c,r=setup(store)
    c['mappings'][-1]['start_at']=162
    engine=ShadowEngine(store,c,replay=True);creators=CreatorService(store)
    add(store,'rfq',r,'r',100);drain(creators,engine)
    assert decisions(store)[0]['expires_at']==102
    add(store,'fixture_status',{'fixture_key':'d:A-B','phase':'in_play'},'started',100.1)
    add(store,'fixture_status',{'fixture_key':'d:A-B','phase':'pregame'},'out_of_order',100.2)
    r['id']='r2';add(store,'rfq',r,'r2',100.3);drain(creators,engine)
    assert decisions(store)[1]['reason']=='pregame_only'
    assert store.db.execute('SELECT status FROM reservations').fetchone()[0]=='cancelled'
    store.close()


def test_review_distinguishes_multileg_quote_proposals_from_trades(tmp_path):
    import importlib.util
    from test_runtime import ROOT
    spec=importlib.util.spec_from_file_location('review_multileg',ROOT/'scripts/review_runtime.py')
    cli=importlib.util.module_from_spec(spec);spec.loader.exec_module(cli)
    path=tmp_path/'events.sqlite';store=EventStore(path);c,r=setup(store)
    engine=ShadowEngine(store,c,replay=True);creators=CreatorService(store)
    add(store,'rfq',r,'r',100);drain(creators,engine)
    report=cli.review(path,c['mappings'],tmp_path/'review')
    assert report['decision_coverage_complete'] and report['all_consumers_drained']
    assert report['decisions_by_leg_count'][4]['proposed_payout_notional_dollars']==10
    assert not report['public_trades']
    assert report['minutes'][0]['shadow_quotes']==1
    store.close()

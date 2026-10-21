from dataclasses import replace
import json
from pathlib import Path
import sys
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from combos.weighted_fair import WeightPolicy, weighted_fair, capped_weights
from combos.observations import Observation, VENUES
from combos.replay import replay_decision
from combos.research_store import ObservationStore
from combos.request_budget import RequestBudget, monthly_requests
from combos.oddspapi import OddsPapi
from test_runtime import config, seed, add, rfq, drain, decisions, observation
from combos.event_store import EventStore
from combos.creator_service import CreatorService
from combos.shadow_engine import ShadowEngine


POLICY = WeightPolicy(delayed_pinnacle=True)


def test_full_game_tie_probability_is_explicit_and_bounded():
    assert WeightPolicy(full_game_tie_probability=.02).full_game_tie_probability == .02
    with pytest.raises(ValueError):
        WeightPolicy(full_game_tie_probability=1.0)


def books(exchange_point=.5, at=100):
    return [Observation.from_record(observation('a',v,at, .5 if v=='pinnacle' else exchange_point)) for v in VENUES]


def test_delayed_anchor_weight_age_and_polymarket_prior():
    f=weighted_fair(books(),100,'pregame',POLICY)
    assert f['venues']['pinnacle']['age_seconds']==30
    assert f['venues']['pinnacle']['weight']<=.2
    assert f['venues']['polymarket']['weight']/f['venues']['kalshi']['weight']==pytest.approx(1.5)
    assert f['fair']['lower']<=.475 and f['fair']['upper']>=.525
    # An actual 30-second-old source with current receipt is not aged twice.
    b=books();b[2]=replace(b[2],observed_at=70)
    assert weighted_fair(b,100,'pregame',POLICY)['venues']['pinnacle']['age_seconds']==30
    b=books(at=161);b[2]=replace(b[2],observed_at=100,available_at=100)
    with pytest.raises(ValueError,match='pinnacle: future or stale'):
        weighted_fair(b,161,'pregame',POLICY)
    with pytest.raises(ValueError,match='pregame_only'):weighted_fair(books(),100,'in_play',POLICY)
    assert capped_weights({'a':1,'b':1,'c':100},{'a':.6,'b':.6,'c':.2})==pytest.approx({'a':.4,'b':.4,'c':.2})


def test_fee_interval_gap_drives_defensive_and_halt_regimes():
    normal=weighted_fair(books(.515),100,'pregame',POLICY)
    assert normal['guard']['regime']=='normal'  # Exchange interval still overlaps Pinnacle.
    defensive=weighted_fair(books(.55),100,'pregame',POLICY)
    assert defensive['guard']['maximum_interval_gap_cents']==pytest.approx(3)
    assert defensive['guard']['regime']=='defensive'
    assert defensive['guard']['risk_multiplier']==.5
    assert defensive['guard']['padding_cents']==pytest.approx(1.5)
    assert defensive['fair']['upper']>=.585-1e-12
    halted=weighted_fair(books(.58),100,'pregame',POLICY)
    assert not halted['guard']['quote_allowed']
    # One exchange alone moving also activates the defense; no unanimity requirement.
    b=books();b[1]=Observation.from_record(observation('a','polymarket',100,.58))
    assert not weighted_fair(b,100,'pregame',POLICY)['guard']['quote_allowed']


@pytest.mark.parametrize('first_side',['yes','no'])
def test_quote_bounds_protect_both_selected_sides(first_side):
    f=weighted_fair(books(.54),100,'pregame',POLICY)
    from combos.replay import complement
    from combos.pricing import Interval
    chosen=complement(Interval(**f['fair']),first_side)
    live=complement(books(.54)[0].interval,first_side)
    assert chosen.upper>=live.upper+.005-1e-12


def test_pregame_cutoff_expiry_and_started_status_latch(tmp_path):
    c=config();c['mappings'][0]['start_at']=161
    store=EventStore(tmp_path/'bus.sqlite');creators=CreatorService(store)
    engine=ShadowEngine(store,c,POLICY,replay=True);seed(store)
    add(store,'rfq',rfq(),'r1',100);drain(creators,engine)
    assert decisions(store)[0]['expires_at']==101
    add(store,'rfq',rfq('r2'),'r2',101);drain(creators,engine)
    assert decisions(store)[1]['reason']=='pregame_cutoff'
    assert store.db.execute('SELECT status FROM reservations').fetchone()[0]=='expired'
    store.close()
    store=EventStore(tmp_path/'early.sqlite');creators=CreatorService(store)
    engine=ShadowEngine(store,config(),POLICY,replay=True);seed(store)
    add(store,'rfq',rfq(),'r1',100);drain(creators,engine)
    add(store,'fixture_status',{'fixture_key':'a:A-B','phase':'in_play'},'started',100.1)
    add(store,'fixture_status',{'fixture_key':'a:A-B','phase':'pregame'},'old-status',100.2)
    add(store,'rfq',rfq('r2'),'r2',100.3);drain(creators,engine)
    assert decisions(store)[1]['reason']=='pregame_only'
    assert store.db.execute('SELECT status FROM reservations').fetchone()[0]=='cancelled'
    store.close()


def test_move_cancels_existing_offer_and_prevents_late_simulated_fill(tmp_path):
    store=EventStore(tmp_path/'bus.sqlite');creators=CreatorService(store)
    engine=ShadowEngine(store,config(),POLICY,replay=True);seed(store)
    add(store,'rfq',rfq(),'r1',100);drain(creators,engine)
    add(store,'observation',observation('a','polymarket',101,.58),'move',101)
    add(store,'simulation_fill',{'reservation_id':'shadow:r1'},'late-fill',101.1)
    add(store,'rfq',rfq('r2'),'r2',101.2);drain(creators,engine)
    assert store.db.execute('SELECT status FROM reservations').fetchone()[0]=='cancelled'
    assert decisions(store)[1]['reason']=='venue_disagreement_hard'
    assert decisions(store)[1]['pricing']['legs'][0]['guard']['regime']=='halt'
    kinds=[e['kind'] for e in store.read(0,100)]
    assert 'quote_invalidated' in kinds and 'simulation_fill_rejected' in kinds
    assert 'consumer_error' not in kinds
    store.close()


def test_last_look_rejects_confirmation_after_fair_moves(tmp_path):
    store=EventStore(tmp_path/'last-look.sqlite');creators=CreatorService(store)
    c=config(); c['last_look']={'enabled':True,'max_fair_move_cents':1.0}
    no_halt_policy=WeightPolicy(delayed_pinnacle=True, disagreement_soft_cents=50., disagreement_hard_cents=100.)
    engine=ShadowEngine(store,c,no_halt_policy,replay=True);seed(store)
    add(store,'rfq',rfq(),'r1',100);drain(creators,engine)
    # Move all three leg books together so this is a fair move, not a
    # disagreement halt. The quote was published at a 50-cent fair.
    for venue in ('kalshi','polymarket','pinnacle'):
        add(store,'observation',observation('a',venue,101,.60),f'move-{venue}',101)
    add(store,'simulation_fill',{'reservation_id':'shadow:r1'},'late-fill',101.1)
    drain(creators,engine)
    kinds=[e for e in store.read(0,200) if e['kind'] in ('quote_invalidated','simulation_fill_rejected')]
    invalidated=[e for e in kinds if e['kind']=='quote_invalidated']
    assert invalidated and invalidated[-1]['payload']['reason']=='last_look_fair_move_exceeded'
    assert invalidated[-1]['payload']['fair_move_cents'] > 1.0
    assert any(e['kind']=='simulation_fill_rejected' for e in kinds)
    store.close()


def test_simulated_fill_records_confirmation_edge_and_source_components(tmp_path):
    store=EventStore(tmp_path/'fill-edge.sqlite');creators=CreatorService(store)
    c=config(); c['last_look']={'enabled':True,'max_fair_move_cents':1.0}
    policy=WeightPolicy(delayed_pinnacle=True, disagreement_soft_cents=50., disagreement_hard_cents=100.)
    engine=ShadowEngine(store,c,policy,replay=True);seed(store)
    add(store,'rfq',rfq(),'r1',100);drain(creators,engine)
    add(store,'simulation_fill',{'reservation_id':'shadow:r1'},'fill',100.1);drain(creators,engine)
    confirmed=[e for e in store.read(0,200) if e['kind']=='simulation_fill_confirmed']
    assert len(confirmed)==1
    payload=confirmed[0]['payload']
    assert payload['fill_price']>0
    assert payload['fill_net_edge_cents'] >= 0.3 - 1e-8
    assert payload['initial_pricing']['legs'][0]['venues']['kalshi']['weight'] > 0
    assert payload['confirmation_pricing']['legs'][0]['venues']['polymarket']['fee_expanded_spread_cents'] > 0
    assert payload['too_tight_at_confirmation'] is False
    store.close()


def test_defensive_risk_caps_aggregate_across_combos(tmp_path):
    store=EventStore(tmp_path/'bus.sqlite');creators=CreatorService(store)
    engine=ShadowEngine(store,config(),POLICY,replay=True);seed(store)
    for key in ('a','b'):
        for venue in ('kalshi','polymarket'):
            add(store,'observation',observation(key,venue,100.1,.55),key+venue,100.1)
    add(store,'rfq',rfq(quantity=60),'r1',100.2)
    add(store,'rfq',rfq('r2',quantity=60),'r2',100.3);drain(creators,engine)
    a,b=decisions(store)
    assert a['status']=='shadow_quote' and a['risk']['checks'][0]['limit_dollars']==50
    assert b['reason']=='contract_risk_limit'
    assert b['risk']['checks'][0]['used_dollars']>0
    store.close()


def test_historical_delay_changes_asof_selection_and_no_double_age(tmp_path):
    store=ObservationStore(tmp_path/'obs.sqlite')
    for key in ('a','b'):
        store.add(observation(key,'pinnacle',70))
        store.add(observation(key,'pinnacle',99,.7)) # Must not be visible at 100.
        for v in ('kalshi','polymarket'):store.add(observation(key,v,100))
    d={'decision_id':'d','decision_at':100,'phase':'pregame','reference_kind':'trade_price',
       'reference_yes_price':.3,'legs':[{'market_key':k+':A-B:moneyline:A','fixture_key':k,'side':'yes','start_at':1000} for k in ('a','b')]}
    result=replay_decision(store,d,POLICY)
    assert result['status']=='priced'
    assert result['comparisons']['spread_depth_weight']['joint']['point']==pytest.approx(.25)
    assert result['leg_details'][0]['venues']['pinnacle']['age_seconds']==30
    del d['legs'][0]['start_at']
    assert replay_decision(store,d,POLICY)['reason']=='pregame_start_time_required'
    store.close()


def test_budget_persists_and_counts_attempts_across_instances(tmp_path):
    p=tmp_path/'budget.sqlite'
    a=RequestBudget(p,0,200,10,reserve_fraction=.2,known_used=6)
    b=RequestBudget(p,0,200,10,reserve_fraction=.2)
    a.claim('odds',100);b.claim('odds-by-tournaments',100)
    with pytest.raises(ValueError,match='exhausted'):a.claim('odds',100)
    assert b.used()==8
    b.claim('historical-odds',100)
    with pytest.raises(ValueError,match='billing_cycle'):b.claim('odds',200)
    with pytest.raises(ValueError,match='overlapping'):RequestBudget(p,100,300,10)
    a.close();b.close()
    assert monthly_requests(24)==86400
    assert monthly_requests(12)==47520


def test_cache_ttl_preserves_receipt_and_failed_calls_consume_budget(tmp_path,monkeypatch):
    import combos.oddspapi as module
    now=[100.]
    monkeypatch.setattr(module.time,'time',lambda:now[0])
    monkeypatch.setattr(module.time,'sleep',lambda _:None)
    class Response:
        status_code=200
        headers={}
        def json(self):return {'synthetic':True}
    class Session:
        calls=0
        def get(self,*args,**kwargs):self.calls+=1;return Response()
    session=Session();budget=RequestBudget(tmp_path/'budget.sqlite',0,200,10,reserve_fraction=0)
    client=OddsPapi(tmp_path/'cache','synthetic',session,budget)
    first=client.get('odds-by-tournaments',{'tournamentIds':'test'},max_cache_age_seconds=30)
    now[0]=120
    assert client.get('odds-by-tournaments',{'tournamentIds':'test'},max_cache_age_seconds=30)==first
    assert session.calls==budget.used()==1
    now[0]=131
    assert client.get('odds-by-tournaments',{'tournamentIds':'test'},max_cache_age_seconds=30)['retrieved_at']==131
    assert session.calls==budget.used()==2
    Response.status_code=500
    with pytest.raises(RuntimeError,match='retries exhausted'):client.get('odds',refresh=True)
    assert session.calls==budget.used()==7
    budget.close()

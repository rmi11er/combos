from combos.creator_service import CreatorService
from combos.event_store import EventStore
from combos.shadow_engine import ShadowEngine
from combos.risk import RiskLedger
from test_runtime import config, seed, add, rfq, drain, decisions


def test_shadow_ceiling_reserves_across_rfqs_restart_and_expiry(tmp_path):
    path = tmp_path/'shadow.sqlite'
    store = EventStore(path)
    c = config()
    c['maximum_committed_dollars'] = 8
    creators = CreatorService(store)
    engine = ShadowEngine(store, c, replay=True)
    seed(store)
    add(store, 'rfq', rfq(), 'r1', 100)
    add(store, 'rfq', rfq('r2'), 'r2', 101)
    drain(creators, engine)
    results = decisions(store)
    assert results[0]['status'] == 'shadow_quote'
    assert results[1]['reason'] == 'deployment_cash_limit'
    assert engine.risk.available() == 7000
    store.close()
    store = EventStore(path)
    creators = CreatorService(store)
    engine = ShadowEngine(store, c, replay=True)
    assert engine.risk.available() == 7000
    add(store, 'heartbeat', {}, 'tick', 104)
    drain(creators, engine)
    assert engine.risk.available() == 80000


def test_ticket_liability_cap_resizes_requested_quantity(tmp_path):
    store=EventStore(tmp_path/'ticket.sqlite'); c=config()
    c['maximum_ticket_gross_liability_dollars']=2.0
    creators=CreatorService(store); engine=ShadowEngine(store,c,replay=True); seed(store)
    add(store,'rfq',rfq(quantity=100),'r1',100); drain(creators,engine)
    result=decisions(store)[0]
    assert result['status']=='shadow_quote'
    assert result['requested_quantity']==100
    assert result['ticket_size_capped'] is True
    assert result['economics']['maximum_loss'] <= 2.0 + 1e-9


def test_moneyline_offset_nets_opposite_sides_but_keeps_each_tail_capped(tmp_path):
    store = EventStore(tmp_path/'offset.sqlite')
    policy = {'capital_dollars':1000, 'per_contract_dollars':100,
              'per_combo_dollars':1000, 'per_fixture_dollars':100,
              'maximum_committed_dollars':1000}
    ledger = RiskLedger(store, policy)
    signed = {'contract':[{'key':'fixture:moneyline:A','side':1}],
              'fixture':[{'key':'fixture:A-B','side':1}]}
    with store.transaction():
        first = ledger.reserve('r1','creator',80,
            {'contract':['fixture:moneyline:A'],'combo':['combo:r1'],'fixture':['fixture:A-B']},
            200, {'quantity':1}, signed_buckets=signed)
    assert first['allowed']
    opposite = {'contract':[{'key':'fixture:moneyline:A','side':-1}],
                'fixture':[{'key':'fixture:A-B','side':-1}]}
    with store.transaction():
        second = ledger.reserve('r2','creator',80,
            {'contract':['fixture:moneyline:A'],'combo':['combo:r2'],'fixture':['fixture:A-B']},
            200, {'quantity':1}, signed_buckets=opposite)
    assert second['allowed']
    with store.transaction():
        third = ledger.reserve('r3','creator',30,
            {'contract':['fixture:moneyline:A'],'combo':['combo:r3'],'fixture':['fixture:A-B']},
            200, {'quantity':1}, signed_buckets=signed)
    assert not third['allowed']
    assert third['reason'] == 'contract_risk_limit'
    # Cash/deployment remains gross even though payoff tails offset.
    assert ledger.available() == 8400000
    store.close()

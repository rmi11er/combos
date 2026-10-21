from copy import deepcopy
import pytest
from combos.quote_reference import QuoteReference
from combos.creator_service import CreatorService
from combos.event_store import EventStore
from combos.shadow_engine import ShadowEngine
from test_runtime import config, seed, add, rfq, drain, decisions


def test_reference_preserves_uncertainty_and_labels_assumption():
    pricing = {'joint': {'point': .125, 'upper': .15}, 'stressed_upper': .25,
               'dependence': {'model': 'pairwise_moment_upper_v1', 'independence_upper': .15}}
    before = deepcopy(pricing)
    assert QuoteReference().evaluate(pricing)['value'] == .25
    r = QuoteReference('independent_marginal_reserve_v1', .25).evaluate(pricing)
    assert r['value'] == pytest.approx(.13125)
    assert r['uncovered_stress_per_share'] == pytest.approx(.11875)
    assert not r['calibrated']
    assert pricing == before
    pricing['dependence']['model'] = 'other'
    with pytest.raises(ValueError, match='independence benchmark'):
        QuoteReference('independent_marginal_reserve_v1', .25).evaluate(pricing)


@pytest.mark.parametrize('fraction', [-1, 1.1, float('nan'), float('inf')])
def test_invalid_fraction(fraction):
    with pytest.raises(ValueError):
        QuoteReference('independent_marginal_reserve_v1', fraction)


def test_shadow_candidate_quote_revalidation_restart_and_risk(tmp_path):
    path = tmp_path/'candidate.sqlite'
    c = config()
    c['quote_reference'] = {'model': 'independent_marginal_reserve_v1', 'marginal_fraction': 0}
    store = EventStore(path)
    creators = CreatorService(store)
    engine = ShadowEngine(store, c, replay=True)
    seed(store)
    add(store, 'rfq', rfq(), 'r1', 100)
    drain(creators, engine)
    d = decisions(store)[0]
    assert d['status'] == 'shadow_quote'
    assert d['quote_reference']['value'] == d['pricing']['joint']['point']
    assert d['stressed_economics']['expected_edge'] < d['economics']['expected_edge']
    assert d['economics'] == d['point_economics']
    # A heartbeat must not cancel a quote merely because it is below full stress.
    add(store, 'heartbeat', {}, 'tick', 101)
    drain(creators, engine)
    assert store.db.execute('SELECT status FROM reservations').fetchone()[0] == 'reserved'
    available = engine.risk.available()
    store.close()
    store = EventStore(path)
    creators = CreatorService(store)
    engine = ShadowEngine(store, c, replay=True)
    assert engine.risk.available() == available
    # An actual fair move must still cancel the reservation and release risk.
    seed(store, at=102, point=.6)
    drain(creators, engine)
    assert store.db.execute('SELECT status FROM reservations').fetchone()[0] == 'cancelled'
    assert engine.risk.available() > available
    store.close()

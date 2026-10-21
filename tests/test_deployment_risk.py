import pytest

from combos.deployment_risk import DeploymentCappedRiskLedger
from combos.event_store import EventStore


def ledger(tmp_path, **overrides):
    policy = dict(capital_dollars=100, maximum_committed_dollars=100,
                  per_contract_dollars=1000, per_combo_dollars=1000,
                  per_fixture_dollars=1000)
    policy.update(overrides)
    store = EventStore(tmp_path / 'risk.sqlite')
    return store, DeploymentCappedRiskLedger(store, policy), policy


def reserve(risk, key, cost):
    return risk.reserve(key, 'creator', cost,
                        {'contract': [key], 'combo': [key], 'fixture': [key]},
                        20, {'quantity': 200})


def test_settled_profit_cannot_expand_deployment_and_restart_preserves_it(tmp_path):
    store, risk, policy = ledger(tmp_path)
    with store.transaction():
        assert reserve(risk, 'profit', 100)['allowed']
        risk.transition('profit', 'simulated_filled', 1, 1)
        risk.transition('profit', 'simulated_settled', 2, 2, 200)
        assert reserve(risk, 'new', 100)['allowed']
    store.db.close()
    store = EventStore(tmp_path / 'risk.sqlite')
    risk = DeploymentCappedRiskLedger(store, policy)
    with store.transaction():
        rejected = reserve(risk, 'excess', 1)
        assert not rejected['allowed']
        assert rejected['binding_funding_limits'] == ['deployment_ceiling']
        assert rejected['settled_cash_available_dollars'] == 100
        assert reserve(risk, 'new', 100)['allowed']  # idempotent reservation
        risk.transition('new', 'cancelled', 3, 3)
        assert reserve(risk, 'replacement', 100)['allowed']


def test_losses_reduce_cash_and_unsettled_positions_keep_deployment(tmp_path):
    store, risk, _ = ledger(tmp_path)
    with store.transaction():
        assert reserve(risk, 'loss', 60)['allowed']
        risk.transition('loss', 'simulated_filled', 1, 1)
        assert not reserve(risk, 'too_early', 41)['allowed']
        risk.expire(30, 2)  # filled positions must not expire
        assert risk.deployment_headroom() == 400000
        risk.transition('loss', 'simulated_settled', 31, 3, 0)
        result = reserve(risk, 'too_large', 41)
        assert result['binding_funding_limits'] == ['settled_cash']
        assert reserve(risk, 'fits', 40)['allowed']


def test_transaction_rollback_and_ceiling_rounding(tmp_path):
    store, risk, _ = ledger(tmp_path, maximum_committed_dollars=10.00009)
    assert risk.ceiling_units == 100000
    with pytest.raises(RuntimeError):
        with store.transaction():
            assert reserve(risk, 'rollback', 10)['allowed']
            raise RuntimeError('rollback')
    assert risk.deployment_headroom() == 100000
    with store.transaction():
        assert not reserve(risk, 'fraction', 10.00001)['allowed']
        assert reserve(risk, 'exact', 10)['allowed']


@pytest.mark.parametrize('cap', [0, -1, float('nan'), float('inf'), .00001])
def test_invalid_ceiling(tmp_path, cap):
    with pytest.raises(ValueError):
        ledger(tmp_path, maximum_committed_dollars=cap)

import pytest

from combos.execution_fills import FillEvidence
from combos.execution_journal import ExecutionJournal
from combos.execution_ownership_store import MakerOwnership
from combos.kalshi_readonly import order_read_path, allowed_read_path
from combos.order_reconciliation import OrderReconciler
from test_execution_ownership import fill
from test_execution_ownership_store import setup, envelope as fill_envelope


def snapshot(order, **changes):
    order = dict(order, status='canceled', remaining_count_fp='0', **changes)
    return {'method': 'GET', 'path': order_read_path(order['order_id']),
            'http_status': 200, 'request_started_at': 104, 'received_at': 105,
            'payload': {'order': order}}


def test_partial_cancel_preserves_filled_risk_and_survives_restart(tmp_path, monkeypatch):
    j, ownership, _, _, order = setup(tmp_path, monkeypatch)
    reconciler = OrderReconciler(ownership)
    r = reconciler.record(0, 'maker-order', snapshot(order), 105, 'private:one')
    assert r['canceled_quantity'] == '8' and r['filled_quantity'] == '2'
    assert not r['terminal_fills_reconciled']
    FillEvidence(j).ingest(fill_envelope([fill()]), 'private:fill')
    r = reconciler.record(0, 'maker-order', snapshot(order), 105, 'private:two')
    assert r['terminal_fills_reconciled'] and not r['capital_release_authorized']
    j.close()
    j = ExecutionJournal(tmp_path/'journal')
    reconciler = OrderReconciler(MakerOwnership(j))
    regressed = snapshot(order)
    regressed['payload']['order'].update(status='resting', remaining_count_fp='8')
    with pytest.raises(ValueError, match='regressed'):
        reconciler.record(0, 'maker-order', regressed, 105, 'private:bad')
    assert j.db.execute("SELECT COUNT(*) FROM execution_intent_events WHERE state='order_reconciliation'").fetchone()[0] == 2
    j.close()


@pytest.mark.parametrize('change', [
    {'status': 'executed'}, {'remaining_count_fp': '8'}, {'user_id': 'other'},
    {'fill_count_fp': '11'}, {'initial_count_fp': '9'}, {'status': 'expired'},
    {'last_update_time': '1970-01-01T00:02:00Z'},
])
def test_contradictory_snapshot_rejected(tmp_path, monkeypatch, change):
    j, ownership, _, _, order = setup(tmp_path, monkeypatch)
    env = snapshot(order)
    env['payload']['order'].update(change)
    with pytest.raises(ValueError):
        OrderReconciler(ownership).record(0, 'maker-order', env, 105, 'private:bad')
    assert j.db.execute("SELECT COUNT(*) FROM execution_intent_events WHERE state='order_reconciliation'").fetchone()[0] == 0
    j.close()


@pytest.mark.parametrize('change', [
    {'request_started_at': 100}, {'received_at': 106}, {'http_status': 404},
    {'path': '/trade-api/v2/portfolio/orders'}, {'method': 'DELETE'},
])
def test_unusable_envelope_rejected(tmp_path, monkeypatch, change):
    j, ownership, _, _, order = setup(tmp_path, monkeypatch)
    env = snapshot(order); env.update(change)
    with pytest.raises(ValueError):
        OrderReconciler(ownership).record(0, 'maker-order', env, 105, 'private:bad')
    j.close()


def test_unfilled_canceled_order(tmp_path, monkeypatch):
    j, ownership, _, _, order = setup(tmp_path, monkeypatch,{'fill_count_fp':'0','remaining_count_fp':'10'})
    env = snapshot(order, fill_count_fp='0')
    r = OrderReconciler(ownership).record(0, 'maker-order', env, 105, 'private:zero')
    assert r['terminal_fills_reconciled'] and r['canceled_quantity'] == '10'
    assert not r['capital_release_authorized']
    j.close()


def test_initial_owned_fill_cannot_disappear_before_first_reconciliation(tmp_path, monkeypatch):
    j, ownership, _, _, order = setup(tmp_path, monkeypatch)
    j.close()
    j=ExecutionJournal(tmp_path/'journal');ownership=MakerOwnership(j)
    with pytest.raises(ValueError, match='ownership evidence'):
        OrderReconciler(ownership).record(0,'maker-order',snapshot(order,fill_count_fp='0'),105,'private:regression')
    assert j.db.execute("SELECT COUNT(*) FROM execution_intent_events WHERE state='order_reconciliation'").fetchone()[0]==0
    j.close()


def test_initial_terminal_owned_snapshot_cannot_reopen(tmp_path, monkeypatch):
    j, ownership, _, _, order = setup(tmp_path, monkeypatch,{'status':'canceled','remaining_count_fp':'0'})
    env=snapshot(order);env['payload']['order'].update(status='resting',remaining_count_fp='8')
    with pytest.raises(ValueError, match='terminal ownership'):
        OrderReconciler(ownership).record(0,'maker-order',env,105,'private:regression')
    j.close()


def test_fully_executed_order(tmp_path, monkeypatch):
    j, ownership, _, _, order = setup(tmp_path, monkeypatch)
    rows = [dict(fill(), fill_id=str(i)) for i in range(5)]
    FillEvidence(j).ingest(fill_envelope(rows), 'private:fills')
    env = snapshot(order, fill_count_fp='10')
    env['payload']['order']['status'] = 'executed'
    r = OrderReconciler(ownership).record(0, 'maker-order', env, 105, 'private:executed')
    assert r['terminal_fills_reconciled'] and r['canceled_quantity'] == '0'
    assert not r['capital_release_authorized']
    j.close()


def test_collector_archives_failed_read_before_rejecting(tmp_path, monkeypatch):
    from types import SimpleNamespace
    import json
    j, ownership, *_ = setup(tmp_path, monkeypatch)
    env = {'method': 'GET', 'path': order_read_path('maker-order'), 'http_status': 404,
           'request_started_at': 104, 'received_at': 105}
    client = SimpleNamespace(get=lambda path: env, clock=lambda: 105)
    archive = tmp_path/'private.json'
    with pytest.raises(ValueError):
        OrderReconciler(ownership).collect(client, 0, 'maker-order', archive)
    assert json.loads(archive.read_text()) == env
    assert archive.stat().st_mode & 0o777 == 0o600
    j.close()


@pytest.mark.parametrize('order_id', ['', '../balance', 'a/b', 'a?x=1', 'a%2fb', 'a#x', 'a\n', 'x'*129])
def test_dynamic_read_path_rejects_path_injection(order_id):
    with pytest.raises(ValueError):
        order_read_path(order_id)
    assert not allowed_read_path('/trade-api/v2/portfolio/orders/'+order_id)


def test_dynamic_order_get_keeps_fixed_host_and_no_redirects():
    from test_kalshi_readonly import client
    c, session = client([{'order': {}}])
    env = c.get(order_read_path('maker-order'))
    assert env['http_status'] == 200
    assert session.calls[0][0] == 'https://external-api.kalshi.com/trade-api/v2/portfolio/orders/maker-order'
    assert session.calls[0][1]['allow_redirects'] is False

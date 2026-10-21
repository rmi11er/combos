import sqlite3
import pytest
from combos.execution_journal import ExecutionJournal
from combos.execution_risk import ExecutionRiskHolds
from combos.execution_ownership_store import MakerOwnership
from combos.order_reconciliation import OrderReconciler
from combos.unfilled_hold_release import UnfilledHoldReleaser
from test_execution_ownership import evidence
from test_order_reconciliation import snapshot
from test_execution_risk import CONFIG,BUCKETS


def setup(tmp_path,monkeypatch,filled='0'):
    import combos.execution_journal as clock_module
    monkeypatch.setattr(clock_module.time,'time',lambda:100)
    j=ExecutionJournal(tmp_path/'journal');risk=ExecutionRiskHolds(j,CONFIG)
    body={'rfq_id':'r','yes_bid':'0','no_bid':'.7','rest_remainder':False,'post_only':True}
    risk.reserve_create('op','hold',body,7.2,BUCKETS)
    monkeypatch.setattr(clock_module.time,'time',lambda:100.5)
    j.claim('op');j.finish_dispatch('op',response={'id':'q'})
    expected,quote,order=evidence();order.update(fill_count_fp=filled,remaining_count_fp=str(10-int(filled)))
    ownership=MakerOwnership(j);ownership.record('op',expected,quote,order,104,105,0,'private:binding')
    OrderReconciler(ownership).record(0,'maker-order',snapshot(order),105,'private:terminal')
    return j,risk,ownership


def test_release_and_restart_are_idempotent(tmp_path,monkeypatch):
    j,risk,owner=setup(tmp_path,monkeypatch)
    assert risk.available_units()==928000
    result=UnfilledHoldReleaser(risk,owner).release('hold',0,'maker-order',105)
    assert result['released_units']==72000 and risk.available_units()==1000000
    j.close();j=ExecutionJournal(tmp_path/'journal');risk=ExecutionRiskHolds(j,CONFIG);owner=MakerOwnership(j)
    assert UnfilledHoldReleaser(risk,owner).release('hold',0,'maker-order',110)==result
    assert j.db.execute("SELECT COUNT(*) FROM execution_intent_events WHERE state='risk_released_unfilled'").fetchone()[0]==1
    j.close()


def test_stale_evidence_keeps_hold(tmp_path,monkeypatch):
    j,risk,owner=setup(tmp_path,monkeypatch)
    with pytest.raises(ValueError,match='stale'):UnfilledHoldReleaser(risk,owner).release('hold',0,'maker-order',108)
    assert risk.available_units()==928000;j.close()


def test_unknown_followup_prevents_release(tmp_path,monkeypatch):
    j,risk,owner=setup(tmp_path,monkeypatch)
    j.prepare('confirm','hold','PUT','/trade-api/v2/communications/quotes/q/confirm',{});j.claim('confirm')
    with pytest.raises(ValueError,match='unresolved'):UnfilledHoldReleaser(risk,owner).release('hold',0,'maker-order',105)
    assert risk.available_units()==928000;j.close()


def test_audit_failure_rolls_back_hold_and_recheck(tmp_path,monkeypatch):
    j,risk,owner=setup(tmp_path,monkeypatch);before=j.db.execute('SELECT COUNT(*) FROM execution_intent_events').fetchone()[0]
    j.db.executescript("CREATE TRIGGER fail_release BEFORE INSERT ON execution_intent_events WHEN NEW.state='risk_released_unfilled' BEGIN SELECT RAISE(ABORT,'injected'); END;")
    with pytest.raises(sqlite3.IntegrityError):UnfilledHoldReleaser(risk,owner).release('hold',0,'maker-order',105)
    assert risk.available_units()==928000
    assert j.db.execute('SELECT COUNT(*) FROM execution_intent_events').fetchone()[0]==before
    j.close()


@pytest.mark.parametrize('filled', ['0', '2'])
def test_fill_evidence_prevents_zero_fill_release(tmp_path,monkeypatch,filled):
    from combos.execution_fills import FillEvidence
    from test_execution_ownership import fill
    from test_execution_ownership_store import envelope
    j,risk,owner=setup(tmp_path,monkeypatch,filled)
    # Test both a fill arriving after a zero-fill read and a fully reconciled
    # partial cancellation. Neither can release the position's risk here.
    FillEvidence(j).ingest(envelope([fill()]),'private:late-fill')
    before=j.db.execute('SELECT COUNT(*) FROM execution_intent_events').fetchone()[0]
    with pytest.raises(ValueError,match='terminal zero-fill'):
        UnfilledHoldReleaser(risk,owner).release('hold',0,'maker-order',105)
    assert risk.available_units()==928000
    assert j.db.execute('SELECT COUNT(*) FROM execution_intent_events').fetchone()[0]==before
    j.close()


def test_acknowledged_confirmation_allows_proven_cancellation(tmp_path,monkeypatch):
    j,risk,owner=setup(tmp_path,monkeypatch)
    j.prepare('confirm','hold','PUT','/trade-api/v2/communications/quotes/q/confirm',{})
    j.claim('confirm');j.finish_dispatch('confirm',response={})
    UnfilledHoldReleaser(risk,owner).release('hold',0,'maker-order',105)
    assert risk.available_units()==1000000
    j.close()

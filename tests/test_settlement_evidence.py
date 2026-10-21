import sqlite3

import pytest

from combos.execution_journal import ExecutionJournal
from combos.settlement_evidence import SettlementEvidence
from test_settlement_accounting import case


def test_restart_deduplicates_without_crediting_cash(tmp_path):
    path = tmp_path/'journal'
    journal = ExecutionJournal(path)
    settlement, fills = case()
    original = SettlementEvidence(journal).record(settlement, fills, 0, ['private:settlement', 'private:fills'])
    assert not original['assessment']['capital_release_authorized']
    journal.close()
    journal = ExecutionJournal(path)
    assert SettlementEvidence(journal).record(settlement, fills, 0, ['private:settlement', 'private:fills']) == original
    assert journal.db.execute('SELECT COUNT(*) FROM settlement_reconciliation_evidence').fetchone()[0] == 1
    assert journal.db.execute('SELECT COUNT(*) FROM execution_intent_events').fetchone()[0] == 0
    journal.close()


def test_revised_revenue_preserves_prior_evidence(tmp_path):
    journal = ExecutionJournal(tmp_path/'journal')
    store = SettlementEvidence(journal)
    settlement, fills = case()
    first = store.record(settlement, fills, 0, ['private:first'])
    settlement = dict(settlement, revenue=1)
    second = store.record(settlement, fills, 0, ['private:second'])
    assert first['evidence_id'] != second['evidence_id']
    assert not second['assessment']['settlement_revenue_matches']
    assert journal.db.execute('SELECT COUNT(*) FROM settlement_reconciliation_evidence').fetchone()[0] == 2
    journal.close()


def test_invalid_economics_leave_no_record(tmp_path):
    journal = ExecutionJournal(tmp_path/'journal')
    store = SettlementEvidence(journal)
    settlement, fills = case()
    settlement['fee_cost'] = '10'
    with pytest.raises(ValueError, match='fees'):
        store.record(settlement, fills, 0, ['private:bad'])
    assert journal.db.execute('SELECT COUNT(*) FROM settlement_reconciliation_evidence').fetchone()[0] == 0
    journal.close()


def test_outer_transaction_rollback_removes_evidence(tmp_path):
    journal = ExecutionJournal(tmp_path/'journal')
    store = SettlementEvidence(journal)
    settlement, fills = case()
    with pytest.raises(RuntimeError):
        with journal.transaction():
            store.record(settlement, fills, 0, ['private:one'])
            raise RuntimeError('downstream audit failed')
    assert journal.db.execute('SELECT COUNT(*) FROM settlement_reconciliation_evidence').fetchone()[0] == 0
    journal.close()

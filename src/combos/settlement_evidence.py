"""Durable settlement reconciliation evidence, without cash or hold mutation.

Inputs must be retained authenticated observations. A balanced economic identity
does not establish complete account history or prove a cash credit.
"""
import hashlib
import json

from .execution_journal import encoded
from .settlement_accounting import reconcile_buy_only_settlement


class SettlementEvidence:
    def __init__(self, journal):
        self.journal = journal
        self.db = journal.db
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS settlement_reconciliation_evidence (
                evidence_id TEXT PRIMARY KEY,
                exchange_index INTEGER NOT NULL,
                subaccount INTEGER NOT NULL,
                ticker TEXT NOT NULL,
                record TEXT NOT NULL);
        ''')

    def record(self, settlement, raw_fills, subaccount, source_references):
        if (not isinstance(source_references, list) or not source_references or
                any(not isinstance(ref, str) or not ref for ref in source_references)):
            raise ValueError('retained settlement and fill source references required')
        # Retain the actual inputs alongside the assessment. Revisions produce
        # new evidence; they never overwrite an earlier assessment.
        inputs = {'settlement': settlement, 'raw_fills': raw_fills,
                  'subaccount': subaccount, 'source_references': source_references}
        digest = hashlib.sha256(encoded(inputs).encode()).hexdigest()
        assessment = reconcile_buy_only_settlement(settlement, raw_fills, subaccount)
        record = {'evidence_id': digest, 'inputs': inputs, 'assessment': assessment}
        serialized = encoded(record)
        with self.journal.transaction():
            old = self.db.execute(
                'SELECT record FROM settlement_reconciliation_evidence WHERE evidence_id=?',
                (digest,)).fetchone()
            if old is not None:
                if old['record'] != serialized:
                    raise ValueError('existing settlement assessment differs; explicit version required')
                return json.loads(old['record'])
            self.db.execute(
                'INSERT INTO settlement_reconciliation_evidence VALUES(?,?,?,?,?)',
                (digest, assessment['exchange_index'], subaccount,
                 assessment['ticker'], serialized))
        return record

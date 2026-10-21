"""Durable single-dispatch mutation intents; no network or risk-release adapter.

Transport acknowledgment is not proof of a fill, cancellation, or released cash.
Every dispatched intent remains in the reconciliation inventory.
"""
from contextlib import contextmanager
import json
import math
import sqlite3
import time
from typing import Protocol


def encoded(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)


class MutationTransport(Protocol):
    def send_once(self, method: str, path: str, body: dict) -> dict:
        """Send exactly one HTTP attempt, with all automatic retries disabled."""
        ...


class ExecutionJournal:
    def __init__(self, path):
        self.db = sqlite3.connect(path,isolation_level=None,timeout=5)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS execution_intents (
                operation_key TEXT PRIMARY KEY, reservation_id TEXT NOT NULL,
                request TEXT NOT NULL, state TEXT NOT NULL,
                created_at REAL NOT NULL, updated_at REAL NOT NULL, response TEXT);
            CREATE TABLE IF NOT EXISTS execution_intent_events (
                seq INTEGER PRIMARY KEY, operation_key TEXT NOT NULL,
                at REAL NOT NULL, state TEXT NOT NULL, detail TEXT NOT NULL);
        ''')

    @contextmanager
    def transaction(self):
        nested = self.db.in_transaction
        self._savepoint_number = getattr(self,'_savepoint_number',0)+1
        name = 'execution_journal_'+str(self._savepoint_number)
        self.db.execute('SAVEPOINT '+name if nested else 'BEGIN IMMEDIATE')
        try:
            yield
            self.db.execute('RELEASE '+name if nested else 'COMMIT')
        except BaseException:
            if nested:
                self.db.execute('ROLLBACK TO '+name)
                self.db.execute('RELEASE '+name)
            else:
                self.db.execute('ROLLBACK')
            raise

    def get(self, operation_key):
        row = self.db.execute('SELECT * FROM execution_intents WHERE operation_key=?',(operation_key,)).fetchone()
        if row is None:
            raise KeyError(operation_key)
        value = dict(row)
        value['request'] = json.loads(value['request'])
        value['response'] = json.loads(value['response']) if value['response'] else None
        return value

    def event(self, key, at, state, detail):
        self.db.execute('INSERT INTO execution_intent_events(operation_key,at,state,detail) VALUES(?,?,?,?)',
                        (key,at,state,encoded(detail)))

    def prepare(self, operation_key, reservation_id, method, path, body, at=None):
        if not operation_key or not reservation_id:
            raise ValueError('operation and reservation identities required')
        if method not in ('POST','PUT','DELETE') or not path.startswith('/trade-api/v2/communications/'):
            raise ValueError('unsupported mutation request')
        if not isinstance(body,dict):
            raise ValueError('structured request body required')
        # Authentication belongs in the transport, never in durable quote bodies.
        if any(any(s in k.lower() for s in ('secret','api_key','signature','authorization')) for k in body):
            raise ValueError('credential-like field in mutation body')
        request = encoded({'method':method,'path':path,'body':body})
        at = time.time() if at is None else at
        if not math.isfinite(at):
            raise ValueError('invalid intent time')
        with self.transaction():
            old = self.db.execute('SELECT reservation_id,request FROM execution_intents WHERE operation_key=?',(operation_key,)).fetchone()
            if old:
                if old['reservation_id'] != reservation_id or old['request'] != request:
                    raise ValueError('conflicting operation identity')
            else:
                self.db.execute('INSERT INTO execution_intents VALUES(?,?,?,?,?,?,NULL)',
                    (operation_key,reservation_id,request,'prepared',at,at))
                self.event(operation_key,at,'prepared',{})
        return self.get(operation_key)

    def claim(self, operation_key):
        """Commit uncertainty before I/O. A restart never reclaims a sent intent."""
        self.get(operation_key)
        at = time.time()
        with self.transaction():
            claimed = self.db.execute("UPDATE execution_intents SET state='inflight',updated_at=? WHERE operation_key=? AND state='prepared'",
                (at,operation_key)).rowcount == 1
            if claimed:
                self.event(operation_key,at,'inflight',{})
        return claimed

    def finish_dispatch(self, operation_key, response=None, error_type=None):
        state = 'unknown' if error_type else 'acknowledged'
        payload = None if error_type else encoded(response)
        at = time.time()
        with self.transaction():
            changed = self.db.execute("UPDATE execution_intents SET state=?,updated_at=?,response=? WHERE operation_key=? AND state='inflight'",
                (state,at,payload,operation_key)).rowcount
            if changed != 1:
                raise ValueError('intent is not awaiting dispatch outcome')
            self.event(operation_key,at,state,{'error_type':error_type} if error_type else {})
        return self.get(operation_key)

    def dispatch(self, operation_key, transport: MutationTransport):
        if not self.claim(operation_key):
            return self.get(operation_key)
        request = self.get(operation_key)['request']
        try:
            response = transport.send_once(request['method'],request['path'],request['body'])
            if not isinstance(response,dict):
                raise ValueError('transport must validate a successful structured response')
            encoded(response)
        except Exception as exc:
            # Exception strings can contain request headers; record class only.
            return self.finish_dispatch(operation_key,error_type=type(exc).__name__)
        return self.finish_dispatch(operation_key,response=response)

    def reconciliation_inventory(self):
        # Even an acknowledged DELETE is not portfolio reconciliation evidence.
        return [self.get(r[0]) for r in self.db.execute("SELECT operation_key FROM execution_intents WHERE state NOT IN ('prepared','abandoned') ORDER BY created_at,operation_key")]

    def close(self):
        self.db.close()

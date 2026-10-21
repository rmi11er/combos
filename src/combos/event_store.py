"""Durable local event stream and atomic consumer checkpoints (single-host WAL)."""
from contextlib import contextmanager
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import sqlite3
import time
import zlib


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


class EventStore:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # SQLite's busy timeout helps with short-lived lock overlap, while the
        # adjacent advisory lock prevents the independent runtime processes
        # from competing for BEGIN IMMEDIATE in the first place.
        self._writer_lock = open(str(self.path) + '.write.lock', 'a')
        self.db = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.execute('PRAGMA busy_timeout=30000')
        self.db.execute('PRAGMA wal_autocheckpoint=1000')
        try:
            self.max_bytes = int(os.environ.get('COMBOS_MAX_EVENT_DB_BYTES', 8 * 1024**3))
        except ValueError:
            raise ValueError('COMBOS_MAX_EVENT_DB_BYTES must be an integer') from None
        if self.max_bytes <= 0: raise ValueError('COMBOS_MAX_EVENT_DB_BYTES must be positive')
        self._append_count = 0
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS events (
                seq INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL,
                source TEXT NOT NULL, received_at REAL NOT NULL,
                event_key TEXT UNIQUE NOT NULL, digest TEXT NOT NULL, payload BLOB NOT NULL,
                schema_version INTEGER NOT NULL DEFAULT 1);
            CREATE TABLE IF NOT EXISTS consumers (
                name TEXT PRIMARY KEY, seq INTEGER NOT NULL, updated_at REAL NOT NULL,
                config TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS state (
                owner TEXT NOT NULL, key TEXT NOT NULL, value TEXT NOT NULL,
                PRIMARY KEY(owner,key));
        ''')
        # Additive migration for event databases created before schema
        # versioning.  Existing rows are version 1 and remain byte-for-byte
        # replay compatible.
        columns = {row[1] for row in self.db.execute('PRAGMA table_info(events)').fetchall()}
        if 'schema_version' not in columns:
            self.db.execute('ALTER TABLE events ADD COLUMN schema_version INTEGER NOT NULL DEFAULT 1')

    @contextmanager
    def transaction(self):
        if self.db.in_transaction: raise RuntimeError('nested event transaction')
        fcntl.flock(self._writer_lock, fcntl.LOCK_EX)
        try:
            self.db.execute('BEGIN IMMEDIATE')
            try:
                yield
                self.db.commit()
            except BaseException:
                self.db.rollback()
                raise
        finally:
            fcntl.flock(self._writer_lock, fcntl.LOCK_UN)

    def append(self, kind, source, payload, event_key, received_at=None, schema_version=1):
        at = time.time() if received_at is None else float(received_at)
        if (not math.isfinite(at) or not kind or not source or not event_key or
                type(schema_version) is not int or schema_version < 1):
            raise ValueError('invalid event envelope')
        self._append_count += 1
        if self._append_count % 256 == 0:
            wal = Path(str(self.path) + '-wal')
            total_bytes = self.path.stat().st_size + (wal.stat().st_size if wal.exists() else 0)
            if total_bytes >= self.max_bytes:
                raise RuntimeError('event_store_size_limit_exceeded')
        raw = encode(payload)
        digest = hashlib.sha256(encode([kind, source, at, payload]).encode()).hexdigest()
        old = self.db.execute('SELECT seq,digest,schema_version FROM events WHERE event_key=?', (event_key,)).fetchone()
        if old:
            if old['digest'] != digest or old['schema_version'] != schema_version:
                raise ValueError('conflicting event key')
            return old['seq']
        result = self.db.execute('''INSERT INTO events(kind,source,received_at,event_key,digest,payload,schema_version)
            VALUES(?,?,?,?,?,?,?)''',
            (kind, source, at, event_key, digest, zlib.compress(raw.encode(), 1), schema_version))
        return result.lastrowid

    def read(self, after=0, limit=500, *, payload_kinds=None):
        """Read every envelope in order, optionally decoding only relevant kinds.

        Omitted payloads are empty dictionaries, not missing events. Consumers
        retain the envelopes for causal clocks, maintenance and cursors.
        The default remains a complete read for archives and review tooling.
        """
        if payload_kinds is None:
            rows = self.db.execute('SELECT * FROM events WHERE seq>? ORDER BY seq LIMIT ?', (after, limit)).fetchall()
        else:
            kinds = tuple(sorted(set(payload_kinds)))
            placeholders = ','.join('?' for _ in kinds) or 'NULL'
            rows = self.db.execute(f"""SELECT seq,kind,source,received_at,event_key,digest,schema_version,
                CASE WHEN kind IN ({placeholders}) THEN payload ELSE NULL END AS payload
                FROM events WHERE seq>? ORDER BY seq LIMIT ?""", (*kinds, after, limit)).fetchall()
        return [dict(row, payload=json.loads(zlib.decompress(row['payload'])) if row['payload'] is not None else {}) for row in rows]

    def register(self, name, config):
        raw = encode(config)
        old = self.db.execute('SELECT config FROM consumers WHERE name=?', (name,)).fetchone()
        if old and old['config'] != raw:
            raise ValueError(f'{name} configuration differs: use a new runtime database for a changed policy')
        self.db.execute('INSERT OR IGNORE INTO consumers VALUES(?,0,?,?)', (name, time.time(), raw))

    def cursor(self, name):
        row = self.db.execute('SELECT seq FROM consumers WHERE name=?', (name,)).fetchone()
        return row['seq'] if row else 0

    def checkpoint(self, name, seq):
        if not self.db.in_transaction: raise RuntimeError('checkpoint must share output transaction')
        self.db.execute('UPDATE consumers SET seq=?,updated_at=? WHERE name=?', (seq, time.time(), name))

    def get(self, owner, key, default=None):
        row = self.db.execute('SELECT value FROM state WHERE owner=? AND key=?', (owner,key)).fetchone()
        return json.loads(row['value']) if row else default

    def put(self, owner, key, value):
        self.db.execute('INSERT INTO state VALUES(?,?,?) ON CONFLICT(owner,key) DO UPDATE SET value=excluded.value',
                        (owner,key,encode(value)))

    def close(self):
        self.db.close()
        self._writer_lock.close()


def rfq_payload(event):
    if event['kind'] == 'rfq': return event['payload']
    if event['kind'] == 'kalshi' and event['payload'].get('type') == 'rfq_created':
        return event['payload']['msg']
    return None

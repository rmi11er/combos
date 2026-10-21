"""Persistent markout evidence ingestion; no creator-policy publication."""
import hashlib
import json
import math
from pathlib import Path
import sqlite3
import time


def digest(raw):
    return hashlib.sha256(raw.encode()).hexdigest()


class CreatorEvidenceStore:
    def __init__(self, path):
        self.db=sqlite3.connect(path,timeout=10)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS sources (
                source_id TEXT PRIMARY KEY, path TEXT UNIQUE NOT NULL,
                identity TEXT NOT NULL, runtime_hash TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS evidence (
                source_id TEXT NOT NULL, decision_seq INTEGER NOT NULL, horizon REAL NOT NULL,
                rfq_id TEXT NOT NULL, creator_id TEXT, status TEXT NOT NULL,
                valuation_at REAL NOT NULL, computed_at REAL NOT NULL, first_seen_at REAL NOT NULL,
                record_hash TEXT NOT NULL, fixtures TEXT NOT NULL, payload TEXT NOT NULL,
                PRIMARY KEY(source_id,decision_seq,horizon));
            CREATE INDEX IF NOT EXISTS evidence_creator ON evidence(creator_id,horizon,first_seen_at);
            CREATE TABLE IF NOT EXISTS availability (
                source_id TEXT NOT NULL, decision_seq INTEGER NOT NULL, horizon REAL NOT NULL,
                available_by REAL NOT NULL, PRIMARY KEY(source_id,decision_seq,horizon));
        ''')

    def import_source(self, marks, runtime, clock=time.time):
        marks=Path(marks).resolve();runtime=Path(runtime).resolve()
        source=sqlite3.connect(marks.as_uri()+'?mode=ro',uri=True,timeout=10)
        source.execute('BEGIN')  # Read only committed rows from one consistent snapshot.
        try:
            raw_identity=source.execute('SELECT identity FROM checkpoint WHERE id=1').fetchone()[0]
            identity=json.loads(raw_identity)
            runtime_raw=runtime.read_bytes();runtime_hash=hashlib.sha256(runtime_raw).hexdigest()
            if identity['identity']['hashes'][str(runtime)]!=runtime_hash:
                raise ValueError('runtime identity mismatch')
            mappings={m['market_key']:m['fixture_key'] for m in json.loads(runtime_raw)['mappings']}
            source_id=digest(raw_identity)
            prior=self.db.execute('SELECT source_id,identity,runtime_hash FROM sources WHERE path=?',(str(marks),)).fetchone()
            if prior and prior!=(source_id,raw_identity,runtime_hash):
                raise ValueError('source identity changed')
            first_seen=clock();added=0;observed=set()
            with self.db:
                self.db.execute('INSERT OR IGNORE INTO sources VALUES(?,?,?,?)',
                    (source_id,str(marks),raw_identity,runtime_hash))
                for seq,horizon,computed,raw in source.execute('SELECT decision_seq,horizon,computed_at,value FROM labels ORDER BY decision_seq,horizon'):
                    key=(seq,horizon);observed.add(key);row=json.loads(raw)
                    if row['decision_seq']!=seq or row['horizon_seconds']!=horizon:
                        raise ValueError('label identity mismatch')
                    if horizon not in identity['horizons'] or horizon<=0 or row['status'] not in ('observed','unavailable'):
                        raise ValueError('unsupported label horizon or status')
                    if row['status']=='observed' and not row.get('creator_id'):
                        raise ValueError('observed label lacks creator')
                    if not row['entry_at']+horizon==row['valuation_at']<=computed<=first_seen:
                        raise ValueError('label chronology mismatch')
                    fixtures=sorted({mappings[leg['market_key']] for leg in row['entry_scenario']['legs']})
                    if not fixtures:raise ValueError('label lacks fixture context')
                    record_hash=digest(json.dumps([computed,raw],separators=(',',':')))
                    old=self.db.execute('SELECT record_hash FROM evidence WHERE source_id=? AND decision_seq=? AND horizon=?',
                        (source_id,seq,horizon)).fetchone()
                    if old:
                        if old[0]!=record_hash:raise ValueError('previously imported label changed')
                        continue
                    self.db.execute('INSERT INTO evidence VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
                        (source_id,seq,horizon,row['rfq_id'],row.get('creator_id'),row['status'],
                         row['valuation_at'],computed,first_seen,record_hash,json.dumps(fixtures),raw))
                    added+=1
                existing=set(self.db.execute('SELECT decision_seq,horizon FROM evidence WHERE source_id=?',(source_id,)))
                if existing!=observed:raise ValueError('previously imported labels disappeared')
            committed_by=clock()
            if not math.isfinite(committed_by) or committed_by<first_seen:
                raise ValueError('import commit clock regression')
            # Separate receipt: primary evidence is already committed. A crash here
            # leaves evidence unreviewable as-of until a later pass confirms it.
            with self.db:
                self.db.execute('''INSERT OR IGNORE INTO availability
                    SELECT source_id,decision_seq,horizon,? FROM evidence WHERE source_id=?''',
                    (committed_by,source_id))
            return {'source_id':source_id,'labels':len(observed),'added':added,
                'snapshot_observed_at':first_seen,'commit_returned_at':committed_by,'automatic_sanctions':0}
        finally:
            source.rollback();source.close()

    def close(self):
        self.db.close()

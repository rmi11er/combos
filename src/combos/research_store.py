"""Append-only normalized snapshots with indexed causal as-of reads."""
import hashlib, json, sqlite3
from pathlib import Path
from .observations import Observation

class ObservationStore:
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('''CREATE TABLE IF NOT EXISTS observations (
            market_key TEXT NOT NULL, venue TEXT NOT NULL, available_at REAL NOT NULL,
            observed_at REAL NOT NULL, digest TEXT NOT NULL, record TEXT NOT NULL,
            PRIMARY KEY(market_key, venue, available_at))''')

    def add(self, row):
        o = Observation.from_record(row)
        raw = json.dumps(row, sort_keys=True, separators=(',', ':'), allow_nan=False)
        digest = hashlib.sha256(raw.encode()).hexdigest()
        key = (o.market_key, o.venue, o.available_at)
        old = self.db.execute('SELECT digest FROM observations WHERE market_key=? AND venue=? AND available_at=?', key).fetchone()
        if old:
            if old[0] != digest: raise ValueError('conflicting snapshots at identical availability time')
            return False
        self.db.execute('INSERT INTO observations VALUES (?,?,?,?,?,?)', (*key, o.observed_at, digest, raw))
        return True

    def latest(self, market_key, venue, decision_at, minimum_delay_seconds=0.):
        if minimum_delay_seconds < 0: raise ValueError('negative publication delay')
        row = self.db.execute('''SELECT record FROM observations WHERE market_key=?
            AND venue=? AND available_at<=? AND observed_at<=?
            ORDER BY MAX(available_at,observed_at+?) DESC, observed_at DESC LIMIT 1''',
            (market_key, venue, decision_at, decision_at-minimum_delay_seconds,minimum_delay_seconds)).fetchone()
        if row is None: raise ValueError(f'{venue}: no prior snapshot')
        # Deliberately return the latest inactive state, never an older active quote.
        return Observation.from_record(json.loads(row[0]))

    def close(self):
        self.db.commit(); self.db.close()

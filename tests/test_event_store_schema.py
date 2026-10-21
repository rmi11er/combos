import sqlite3

import pytest

from combos.event_store import EventStore


def test_event_schema_version_is_persisted_and_conflicts_are_rejected(tmp_path):
    store = EventStore(tmp_path / "events.sqlite")
    seq = store.append("test", "unit", {"v": 1}, "one", 10, schema_version=2)
    row = store.db.execute("SELECT schema_version FROM events WHERE seq=?", (seq,)).fetchone()
    assert row[0] == 2
    assert store.read()[0]["schema_version"] == 2
    assert store.append("test", "unit", {"v": 1}, "one", 10, schema_version=2) == seq
    with pytest.raises(ValueError, match="conflicting"):
        store.append("test", "unit", {"v": 1}, "one", 10, schema_version=3)
    store.close()


def test_old_event_database_gets_additive_schema_migration(tmp_path):
    path = tmp_path / "legacy.sqlite"
    db = sqlite3.connect(path)
    db.executescript("""
        CREATE TABLE events (seq INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL,
          source TEXT NOT NULL, received_at REAL NOT NULL, event_key TEXT UNIQUE NOT NULL,
          digest TEXT NOT NULL, payload BLOB NOT NULL);
        CREATE TABLE consumers (name TEXT PRIMARY KEY, seq INTEGER NOT NULL, updated_at REAL NOT NULL, config TEXT NOT NULL);
        CREATE TABLE state (owner TEXT NOT NULL, key TEXT NOT NULL, value TEXT NOT NULL, PRIMARY KEY(owner,key));
    """)
    db.commit(); db.close()
    store = EventStore(path)
    columns = {row[1] for row in store.db.execute("PRAGMA table_info(events)")}
    assert "schema_version" in columns
    store.close()

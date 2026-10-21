import json
from pathlib import Path
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from sniffer_health import observe


def test_live_wal_and_stale_export_are_distinct(tmp_path):
    path = tmp_path/'live.sqlite'
    writer = sqlite3.connect(path)
    writer.execute('PRAGMA journal_mode=WAL')
    writer.execute('CREATE TABLE requests(at REAL)')
    writer.execute('CREATE INDEX requests_time ON requests(at)')
    writer.execute('INSERT INTO requests VALUES(190)')
    writer.commit()
    manifest = tmp_path/'manifest.json'
    manifest.write_text(json.dumps({'started_at': 150, 'updated_at': 195, 'closed_cleanly': True}))
    summary = tmp_path/'summary.json'
    summary.write_text(json.dumps({'generated_at': 100}))
    result = observe(path, manifest, summary, now=200)
    assert result['latest_committed_request_at'] == 190
    assert result['export']['age_seconds'] == 100
    assert result['causal_policy_freshness'] == 'unproven'
    assert writer.execute('SELECT count(*) FROM requests').fetchone()[0] == 1
    writer.close()


def test_missing_database_is_not_created_and_missing_export_is_explicit(tmp_path):
    manifest = tmp_path/'manifest.json'
    manifest.write_text('{}')
    database = tmp_path/'absent.sqlite'
    result = observe(database, manifest, tmp_path/'absent.json', now=200)
    assert not database.exists()
    assert 'database_observation_error' in result
    assert 'export_observation_error' in result

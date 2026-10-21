import gzip
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('audit', ROOT / 'scripts/audit_candidate_pinnacle_snapshot.py')
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def test_non_fixture_payloads_are_ignored(tmp_path):
    runtime = tmp_path / 'runtime.json'
    catalog = tmp_path / 'catalog.json'
    raw = tmp_path / 'raw'; raw.mkdir()
    runtime.write_text(json.dumps({'mappings': []}))
    catalog.write_text('[]')
    with gzip.open(raw / 'account.json.gz', 'wt') as f:
        json.dump({'payload': {'subscriptions': []}}, f)
    result = audit.audit(runtime, catalog, raw)
    assert result['snapshots'] == []
    assert result['all_snapshots_exact'] is False

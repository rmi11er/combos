import gzip
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('audit', ROOT / 'scripts/audit_pinnacle_limit_metadata.py')
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def test_numeric_limits_do_not_imply_units(tmp_path):
    raw = tmp_path / 'x.json.gz'
    payload = {'payload': [{'bookmakerOdds': {'pinnacle+30': {'markets': {
        '1': {'outcomes': {'1': {'players': {'0': {'limit': 10.0}}}}}
    }}}}]} 
    with gzip.open(raw, 'wt') as f:
        json.dump(payload, f)
    result = audit.audit(tmp_path)
    assert result['numeric_limits'] == 1
    assert result['currency_and_unit_verified'] is False
    assert result['provider_documentation']['semantics_conflict_requires_provider_confirmation'] is True

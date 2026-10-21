import json, subprocess, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def test_candidate_freeze_validator_accepts_locked_shadow_candidate():
    freeze=ROOT/'config/candidate_freeze_shadow_20260911.json'
    result=subprocess.run([sys.executable,str(ROOT/'scripts/validate_candidate_freeze.py'),
                           '--freeze',str(freeze)],capture_output=True,text=True,check=True)
    payload=json.loads(result.stdout)
    assert payload['valid'] is True
    assert payload['orders_enabled'] is False

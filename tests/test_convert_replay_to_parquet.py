import hashlib
import json
from pathlib import Path

from scripts.convert_replay_to_parquet import main


def test_converts_rows_and_preserves_source(tmp_path, monkeypatch):
    batch = tmp_path / "batch"
    source = batch / "2026-01-01" / "replay" / "opportunities.json"
    source.parent.mkdir(parents=True)
    rows = [{
        "evaluation_id": "00000000-0000-0000-0000-000000000001",
        "at": 1.0,
        "quantity": 2.0,
        "yes_price": 0.3,
        "maker_fee": 0.01,
        "settled_at": 2.0,
        "yes_settlement": 0.0,
        "buckets": {"contract": ["c"], "fixture": ["f"], "combo": ["x"]},
        "source": {"nlegs": 2, "sampling_method": "census", "source_window": [0.0, 3.0],
                   "series": ["KXMLBGAME"], "combo_ticker": "x", "start_at": 3.0,
                   "schedule_basis": "test", "fee_basis": {"rate": 0.1}},
        "model": "kalshi", "fair_point": 0.2, "stressed_upper": 0.4,
        "quote_allowed": True, "risk_multiplier": 1.0,
    }]
    source.write_text(json.dumps({"opportunities": rows}))
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    out = tmp_path / "parquet"
    monkeypatch.setattr("sys.argv", ["convert", "--batch-root", str(batch), "--out", str(out)])
    assert main() == 0
    assert hashlib.sha256(source.read_bytes()).hexdigest() == before
    manifest = json.loads((out / "manifest.json").read_text())
    assert manifest["total_rows"] == 1
    assert manifest["source_bytes"] == source.stat().st_size
    assert manifest["output_bytes"] == (out / "2026-01-01.parquet").stat().st_size

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("shadow_preflight", ROOT / "scripts/shadow_preflight.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_preflight_fails_closed_for_orders_and_promotion(tmp_path, monkeypatch):
    config = {"mode": "live", "orders_enabled": True, "automatic_promotion": True,
              "mappings": [], "capital_dollars": 1}
    weights = {"delayed_pinnacle": True, "pinnacle_delay_seconds": 30,
               "pregame_cutoff_seconds": 60}
    polling = {"tournament_ids": ["x"], "known_used": 0,
               "billing_cycle_start": 0, "billing_cycle_end": 9e10}
    paths = []
    for name, value in (("config", config), ("weights", weights), ("polling", polling)):
        path = tmp_path / f"{name}.json"; path.write_text(json.dumps(value)); paths.append(path)
    result = MODULE.run(*paths, minimum_free_gb=0)
    assert not result["ready"]
    assert "shadow_mode_required" in result["blockers"]
    assert "orders_must_be_disabled" in result["blockers"]


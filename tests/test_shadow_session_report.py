import importlib.util
from pathlib import Path

from combos.event_store import EventStore


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("shadow_session_report", ROOT / "scripts/shadow_session_report.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_shadow_session_report_writes_summary_and_plot(tmp_path):
    db = tmp_path / "session.sqlite"
    store = EventStore(db)
    store.append("decision", "shadow", {
        "status": "shadow_quote", "would_quote": True, "quantity": 10,
        "economics": {"expected_edge": .01}, "pricing": {"disagreement_cents": 1.2},
    }, "decision:1", 100)
    store.append("markout", "shadow", {
        "status": "observed", "horizon_seconds": 5, "markout_net_edge_dollars": .05,
    }, "markout:1:5", 105)
    store.close()
    summary = MODULE.build_report(db, tmp_path / "review")
    assert summary["decisions"] == 1
    assert summary["markouts_observed"] == 1
    assert (tmp_path / "review/shadow_session_review.png").exists()
    assert (tmp_path / "review/summary.json").exists()

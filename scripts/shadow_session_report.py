#!/usr/bin/env python3
"""Create a visual and machine-readable review bundle for a shadow session."""

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import sys
import time

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from combos.event_store import EventStore


def _number(value, default=0.0):
    try:
        result = float(value)
        return result if result == result else default
    except (TypeError, ValueError):
        return default


def build_report(db: Path, out: Path) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    store = EventStore(db)
    try:
        events = store.read(0, 10_000_000)
    finally:
        store.close()
    decisions = [e for e in events if e["kind"] == "decision"]
    markouts = [e["payload"] for e in events if e["kind"] == "markout"]
    resets = [e["payload"] for e in events if e["kind"] == "venue_reset"]
    creators = [e["payload"] for e in events if e["kind"] == "creator_policy"]
    status_counts = Counter(d["payload"].get("status", "unknown") for d in decisions)
    reason_counts = Counter(d["payload"].get("reason") or "none" for d in decisions)
    eligible = [d["payload"] for d in decisions if d["payload"].get("would_quote") is True]
    counterfactual = [d["payload"] for d in decisions if d["payload"].get("shadow_counterfactual")]
    edge_rows = []
    cumulative = []
    running = 0.0
    for d in decisions:
        p = d["payload"]
        economics = p.get("economics") or p.get("point_economics") or {}
        edge = _number(economics.get("expected_edge"))
        quantity = _number(p.get("quantity"))
        dollars = edge * quantity
        if p.get("status") in ("shadow_quote", "shadow_quote_blocked"):
            running += dollars
            edge_rows.append({"source_seq": d["seq"], "status": p.get("status"),
                              "creator_id": p.get("creator_id"), "edge_dollars": dollars,
                              "edge_per_contract": edge, "quantity": quantity})
            cumulative.append((d["received_at"], running))
    markout_by_horizon = defaultdict(list)
    for row in markouts:
        if row.get("status") == "observed":
            markout_by_horizon[str(row.get("horizon_seconds"))].append(_number(row.get("markout_net_edge_dollars")))
    summary = {
        "generated_at": time.time(), "database": str(db), "events": len(events),
        "decisions": len(decisions), "eligible_hypothetical_quotes": len(eligible),
        "blacklisted_counterfactuals": len(counterfactual), "status_counts": dict(status_counts),
        "reason_counts": dict(reason_counts), "markouts_observed": len([m for m in markouts if m.get("status") == "observed"]),
        "venue_resets": len(resets), "creator_policy_events": len(creators),
        "hypothetical_edge_dollars": sum(r["edge_dollars"] for r in edge_rows),
        "markout_net_edge_dollars_by_horizon": {k: sum(v) for k, v in markout_by_horizon.items()},
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n")
    (out / "decision_edges.jsonl").write_text("\n".join(json.dumps(r, allow_nan=False) for r in edge_rows) + ("\n" if edge_rows else ""))

    fig, axes = plt.subplots(2, 3, figsize=(18, 10), constrained_layout=True)
    ax = axes[0, 0]
    labels, values = zip(*status_counts.items()) if status_counts else ([], [])
    ax.bar(labels, values, color="#4c78a8")
    ax.set_title("Decision outcomes"); ax.tick_params(axis="x", rotation=35); ax.set_ylabel("RFQs")

    ax = axes[0, 1]
    edge_values = [r["edge_per_contract"] * 100 for r in edge_rows]
    ax.hist(edge_values, bins=30, color="#f58518") if edge_values else ax.text(.5, .5, "No hypothetical quotes", ha="center", va="center")
    ax.set_title("Hypothetical edge per contract"); ax.set_xlabel("Edge (cents)"); ax.set_ylabel("RFQs")

    ax = axes[0, 2]
    if cumulative:
        ax.plot([x for x, _ in cumulative], [y for _, y in cumulative], color="#54a24b")
    else:
        ax.text(.5, .5, "No quote decisions", ha="center", va="center")
    ax.set_title("Cumulative hypothetical edge"); ax.set_ylabel("Dollars")

    ax = axes[1, 0]
    horizons = sorted(markout_by_horizon, key=lambda x: float(x))
    means = [sum(markout_by_horizon[h]) / len(markout_by_horizon[h]) for h in horizons]
    ax.bar(horizons, means, color="#e45756") if horizons else ax.text(.5, .5, "No observed markouts", ha="center", va="center")
    ax.axhline(0, color="black", linewidth=.8); ax.set_title("Markout net edge by horizon"); ax.set_xlabel("Seconds"); ax.set_ylabel("Mean dollars")

    ax = axes[1, 1]
    disagreements = [_number(d["payload"].get("pricing", {}).get("disagreement_cents")) for d in decisions]
    ax.hist(disagreements, bins=30, color="#72b7b2") if disagreements else ax.text(.5, .5, "No pricing observations", ha="center", va="center")
    ax.set_title("Source disagreement"); ax.set_xlabel("Disagreement (cents)"); ax.set_ylabel("RFQs")

    ax = axes[1, 2]
    reasons, counts = zip(*reason_counts.most_common(10)) if reason_counts else ([], [])
    ax.barh(list(reasons)[::-1], list(counts)[::-1], color="#b279a2")
    ax.set_title("Top decision reasons"); ax.set_xlabel("RFQs")
    fig.suptitle(f"Shadow session review — {len(events):,} events", fontsize=16)
    fig.savefig(out / "shadow_session_review.png", dpi=140)
    plt.close(fig)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build_report(args.db, args.out), indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

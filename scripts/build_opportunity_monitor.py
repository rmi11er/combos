#!/usr/bin/env python3
"""Build the normalized snapshot consumed by the liquidity opportunity monitor."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def num(value: str | int | float | None) -> float | None:
    if value in (None, ""):
        return None
    return float(value)


def add_metric(rows: list[dict], base: dict, metric: str, value: float | None) -> None:
    if value is not None:
        rows.append({"metric": metric, "value": value, **base})


def load_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def load_json(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def build_snapshot() -> dict:
    rows: list[dict] = []
    sources: list[dict] = []

    mlb_path = ROOT / "runs/mlb_historical_20260907/universe_report/daily_observed.csv"
    if mlb_path.exists():
        sources.append({"name": "MLB combo tape", "path": str(mlb_path.relative_to(ROOT)), "coverage": "daily sampled/census"})
        for item in load_csv_rows(mlb_path):
            base = {
                "date": item["date"], "venue": "Kalshi", "market_type": "combo", "geography": "US",
                "sport": "MLB", "league": "MLB", "scope": "native combo universe",
                "sampling": item.get("sampling_method", "unknown"), "source": "mlb_historical_20260907/universe_report",
            }
            add_metric(rows, base, "premium", num(item.get("all_print_yes_premium")))
            add_metric(rows, base, "payout", num(item.get("all_print_payout_face")))
            add_metric(rows, base, "prints", num(item.get("prints")))
            add_metric(rows, base, "known_pnl", num(item.get("known_net_pnl")))

    cfb_path = ROOT / "runs/cfb_week_20260831/prop_scope_daily.csv"
    if cfb_path.exists():
        sources.append({"name": "CFB combo volume", "path": str(cfb_path.relative_to(ROOT)), "coverage": "sampled windows; interval estimates retained"})
        for item in load_csv_rows(cfb_path):
            if item.get("scope") != "full_game_only":
                continue
            base = {
                "date": item["date"], "venue": "Kalshi", "market_type": "combo", "geography": "US",
                "sport": "CFB", "league": "CFB", "scope": "full-game-only", "sampling": "sampled windows",
                "source": "cfb_week_20260831/prop_scope_daily",
            }
            metric = item["metric"].replace("yes_premium_dollars", "premium").replace("payout_notional_dollars", "payout")
            add_metric(rows, base, metric, num(item.get("total")))

    pm_path = ROOT / "data/raw/probes/polymarket_sports.json"
    if pm_path.exists():
        payload = json.loads(pm_path.read_text())
        leagues = payload.get("payload", [])
        as_of = payload.get("retrieved_at", datetime.now(timezone.utc).isoformat())[:10]
        sources.append({"name": "Polymarket sports catalog", "path": str(pm_path.relative_to(ROOT)), "coverage": "point-in-time catalog; no historical volume"})
        base = {
            "date": as_of, "venue": "Polymarket", "market_type": "sports", "sport": "Multi-sport",
            "league": "Catalog", "scope": "active sport/league catalog", "sampling": "point-in-time",
            "source": "data/raw/probes/polymarket_sports.json",
        }
        add_metric(rows, {**base, "geography": "non-US"}, "active_markets", len(leagues))
        us_like = {"NFL", "NCAA", "MLB", "NBA", "NHL", "WNBA", "MLS", "UFC", "NASCAR"}
        us_count = sum(1 for league in leagues if str(league.get("name", "")).upper() in us_like or str(league.get("sport", "")).upper() in {"NFL", "MLB", "NBA", "NHL", "WNBA"})
        add_metric(rows, {**base, "geography": "US", "scope": "catalog heuristic"}, "active_markets", us_count)
        add_metric(rows, {**base, "geography": "non-US", "scope": "catalog heuristic"}, "active_markets", len(leagues) - us_count)

    research: dict = {}
    demand_path = ROOT / "runs/nfl_both_demand_scenarios_20260909/summary.json"
    if demand_path.exists():
        demand = load_json(demand_path)
        counts = demand.get("counts", {})
        research["funnel"] = {
            "source": str(demand_path.relative_to(ROOT)),
            "steps": [
                {"label": "RFQs observed", "value": demand.get("rfqs", 0)},
                {"label": "In leg-count scope", "value": demand.get("rfqs", 0) - counts.get("outside_leg_count_scope", 0)},
                {"label": "Supported sport", "value": demand.get("rfqs", 0) - counts.get("outside_leg_count_scope", 0) - counts.get("outside_sport_scope", 0)},
                {"label": "Scenario priced", "value": counts.get("scenario_priced", 0)},
            ],
            "exclusions": [{"label": k, "value": v} for k, v in counts.items() if k != "scenario_priced"],
            "priced_leg_counts": demand.get("priced_leg_counts", {}),
        }

    markout_path = ROOT / "runs/nfl_trace_worker_20260909/dynamic_edge_markouts.json"
    markouts = load_json(markout_path)
    if markouts:
        research["markouts"] = {
            "source": str(markout_path.relative_to(ROOT)),
            "decision_count": markouts.get("decision_count"),
            "total_labels": markouts.get("total_labels"),
            "groups": markouts.get("groups", []),
            "limitations": markouts.get("limitations", []),
        }

    capacity_path = ROOT / "runs/nfl_charge_capacity_sweep_20260909/summary.json"
    capacity = load_json(capacity_path)
    if capacity:
        research["capacity"] = {
            "source": str(capacity_path.relative_to(ROOT)),
            "scenarios": [s for s in capacity.get("scenarios", []) if s.get("model") == "captured_sharp_peer" and s.get("charge") in {"zero", "0.3c_combo"}],
        }

    coverage_path = ROOT / "runs/nfl_rfq_coverage_diagnostic_20260909/summary.json"
    coverage = load_json(coverage_path)
    missing_path = ROOT / "runs/nfl_live_markout_missing_diagnosis_20260909_v2/summary.json"
    missing = load_json(missing_path)
    if coverage or missing:
        research["blockers"] = {
            "source": [str(p.relative_to(ROOT)) for p in (coverage_path, missing_path) if p.exists()],
            "coverage": coverage,
            "markout_missing": missing,
        }

    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "timezone": "America/Chicago",
        "notes": [
            "Premium is YES-side public-print premium where available; it is not attainable maker volume.",
            "Known P&L is a research outcome measure, not a forward opportunity estimate.",
            "Polymarket catalog rows are point-in-time coverage only; historical volume is not inferred.",
            "US/non-US classification for catalog rows is a conservative heuristic pending explicit geography metadata.",
        ],
        "sources": sources,
        "observations": rows,
        "research": research,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=ROOT / "data/opportunity_monitor/snapshot.json")
    parser.add_argument("--html", type=Path, default=ROOT / "visualizations/00-opportunity-monitor/index.html")
    args = parser.parse_args()
    snapshot = build_snapshot()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(snapshot, indent=2) + "\n")
    template = args.html.with_name("index.template.html")
    if template.exists():
        args.html.write_text(template.read_text().replace("__SNAPSHOT__", json.dumps(snapshot, separators=(",", ":"))))
    print(f"wrote {args.out} with {len(snapshot['observations'])} normalized observations")


if __name__ == "__main__":
    main()

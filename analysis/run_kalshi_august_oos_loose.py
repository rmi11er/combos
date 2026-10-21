#!/usr/bin/env python3
"""Run the Kalshi-only control on the held-out August MLB replay."""

from __future__ import annotations

import json
import math
import statistics
from datetime import datetime, timezone
from pathlib import Path

import offsetting_allocation_backtest as engine

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/shadow_three_source_loose_slate_20260909.json"
OUT = ROOT / "analysis/offsetting_allocation_v1/kalshi_august_oos_loose.json"
OOS_DATES = ("02", "04", "06", "08", "10", "12", "14", "16", "18", "20", "22", "24", "26", "28", "30")


def daily_stats(curve: list[dict]) -> tuple[float | None, float | None, int]:
    by_day: dict[str, float] = {}
    for point in curve:
        day = datetime.fromtimestamp(point["settled_at"], tz=timezone.utc).date().isoformat()
        by_day[day] = by_day.get(day, 0.0) + point["incremental_pnl"] / 10_000.0
    values = list(by_day.values())
    if len(values) < 2 or statistics.stdev(values) == 0:
        return None, None, len(values)
    sh = statistics.mean(values) / statistics.stdev(values)
    return sh, sh * math.sqrt(252.0), len(values)


def max_drawdown(curve: list[dict]) -> float:
    peak = 0.0
    dd = 0.0
    for point in curve:
        peak = max(peak, point["cumulative_pnl"])
        dd = min(dd, point["cumulative_pnl"] - peak)
    return dd


def main() -> None:
    engine.MLB_DATES = OOS_DATES
    engine.MLB_DATE_PREFIX = "2026-08-"
    rows, hashes, audit = engine.load_rows(model="kalshi", minimum_edge=0.003)
    policy = engine.Policy(
        name="kalshi_only_august_oos_loose_offset",
        max_ticket_liability=250.0,
        offset_moneyline=True,
        capital=10_000.0,
        contract_cap=500.0,
        combo_cap=500.0,
        fixture_cap=1_000.0,
        minimum_edge=0.003,
    )
    result = engine.run(rows, policy, "MLB")
    daily, annualized, days = daily_stats(result["equity_curve"])
    output = {
        "config": json.loads(CONFIG.read_text()),
        "oos_dates": ["2026-08-" + day for day in OOS_DATES],
        "model": "kalshi",
        "rows": len(rows),
        "input_hashes": hashes,
        "audit": audit,
        "result": {k: v for k, v in result.items() if k != "equity_curve"},
        "daily_sharpe": daily,
        "annualized_sharpe_252": annualized,
        "active_settlement_days": days,
        "max_drawdown": max_drawdown(result["equity_curve"]),
        "limitations": [
            "August is out-of-time relative to the July development dates, but this replay does not reproduce the frozen validation implementation's fixture exclusion certificate.",
            "Public prints are hypothetical full fills with no queue or fill elasticity.",
            "This is a Kalshi-only control; it is not a test of three-source fair value.",
        ],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(output, indent=2) + "\n")
    print(json.dumps({k: v for k, v in output.items() if k not in {"input_hashes", "audit", "config"}}, indent=2))
    print(OUT)


if __name__ == "__main__":
    main()

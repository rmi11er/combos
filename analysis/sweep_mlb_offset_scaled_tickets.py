#!/usr/bin/env python3
"""Sweep MLB offset-aware limits while scaling ticket liability with them."""

from __future__ import annotations

import csv
import json
import math
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "analysis"))
from offsetting_allocation_backtest import Policy, load_rows, run  # noqa: E402

OUT = ROOT / "analysis/offsetting_allocation_v1"


def sharpe(curve: list[dict], capital: float) -> tuple[float | None, float | None]:
    by_day: dict[str, float] = {}
    for point in curve:
        day = datetime.fromtimestamp(point["settled_at"], tz=timezone.utc).date().isoformat()
        by_day[day] = by_day.get(day, 0.0) + point["incremental_pnl"] / capital
    values = list(by_day.values())
    if len(values) < 2 or statistics.stdev(values) == 0:
        return None, None
    daily = statistics.mean(values) / statistics.stdev(values)
    return daily, daily * math.sqrt(252.0)


def max_drawdown(curve: list[dict]) -> float:
    peak = 0.0
    drawdown = 0.0
    for point in curve:
        peak = max(peak, point["cumulative_pnl"])
        drawdown = min(drawdown, point["cumulative_pnl"] - peak)
    return drawdown


def main() -> None:
    rows, hashes, audit = load_rows()
    # Ticket cap scales with the loosening tier; all retain exact ML offsets.
    specs = [
        ("scaled_baseline", 100, 100, 250, 50),
        ("scaled_balanced", 250, 250, 500, 100),
        ("scaled_loose", 500, 500, 1000, 250),
        ("scaled_very_loose", 1000, 1000, 2000, 500),
        ("scaled_capital_only", 10000, 10000, 10000, 1000),
    ]
    output = []
    for name, contract, combo, fixture, ticket in specs:
        policy = Policy(
            name=name,
            max_ticket_liability=float(ticket),
            offset_moneyline=True,
            contract_cap=float(contract),
            combo_cap=float(combo),
            fixture_cap=float(fixture),
        )
        result = run(rows, policy, "MLB")
        daily, annualized = sharpe(result["equity_curve"], policy.capital)
        output.append(
            {
                "policy": name,
                "contract_cap": contract,
                "combo_cap": combo,
                "fixture_cap": fixture,
                "ticket_cap": ticket,
                "accepted": result["accepted"],
                "peak_committed_cash": result["peak_committed_cash"],
                "peak_offset_credit": result["peak_offset_credit"],
                "accepted_edge": result["accepted_edge_before_outcomes"],
                "ending_pnl": result["retrospective_scaled_edge_proxy"],
                "max_drawdown": max_drawdown(result["equity_curve"]),
                "daily_sharpe": daily,
                "annualized_sharpe_252": annualized,
                "avg_ticket_liability": result["average_ticket_liability"],
            }
        )
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "mlb_offset_scaled_ticket_sweep.json").write_text(
        json.dumps({"input_hashes": hashes, "audit": audit, "results": output}, indent=2) + "\n"
    )
    with (OUT / "mlb_offset_scaled_ticket_sweep.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=output[0].keys())
        writer.writeheader()
        writer.writerows(output)
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()

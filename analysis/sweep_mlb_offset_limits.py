#!/usr/bin/env python3
"""Compare MLB offset-aware risk-limit policies on the saved replay."""

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
    specs = [
        ("joint_baseline_100_100_250", 100, 100, 250),
        ("joint_balanced_250_250_500", 250, 250, 500),
        ("joint_loose_500_500_1000", 500, 500, 1000),
        ("joint_very_loose_1000_1000_2000", 1000, 1000, 2000),
        ("joint_capital_only", 10000, 10000, 10000),
        ("contract_tight_50_100_250", 50, 100, 250),
        ("contract_loose_250_100_250", 250, 100, 250),
        ("combo_tight_100_50_250", 100, 50, 250),
        ("combo_loose_100_250_250", 100, 250, 250),
        ("fixture_tight_100_100_100", 100, 100, 100),
        ("fixture_loose_100_100_500", 100, 100, 500),
    ]
    output = []
    for name, contract, combo, fixture in specs:
        policy = Policy(
            name=name,
            max_ticket_liability=50.0,
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
                "ticket_cap": 50,
                "accepted": result["accepted"],
                "peak_committed_cash": result["peak_committed_cash"],
                "peak_offset_credit": result["peak_offset_credit"],
                "accepted_edge": result["accepted_edge_before_outcomes"],
                "ending_pnl": result["retrospective_scaled_edge_proxy"],
                "max_drawdown": max_drawdown(result["equity_curve"]),
                "active_settlement_days": len({
                    datetime.fromtimestamp(p["settled_at"], tz=timezone.utc).date().isoformat()
                    for p in result["equity_curve"]
                }),
                "daily_sharpe": daily,
                "annualized_sharpe_252": annualized,
                "avg_ticket_liability": result["average_ticket_liability"],
            }
        )
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "mlb_offset_limit_sweep.json").write_text(
        json.dumps({"input_hashes": hashes, "audit": audit, "results": output}, indent=2) + "\n"
    )
    with (OUT / "mlb_offset_limit_sweep.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=output[0].keys())
        writer.writeheader()
        writer.writerows(output)
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Sweep edge hurdles for Kalshi and equal-blend models under fixed limits."""

from __future__ import annotations

import csv
import json
import math
import statistics
from datetime import datetime, timezone
from pathlib import Path

from offsetting_allocation_backtest import Policy, load_rows, run

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "analysis/offsetting_allocation_v1"
HURDLES = (0.0, 0.0015, 0.003, 0.005, 0.01)
MODELS = ("kalshi", "exchange_blend_equal")


def daily_sharpe(curve: list[dict]) -> float | None:
    by_day: dict[str, float] = {}
    for point in curve:
        day = datetime.fromtimestamp(point["settled_at"], tz=timezone.utc).date().isoformat()
        by_day[day] = by_day.get(day, 0.0) + point["incremental_pnl"] / 10_000.0
    values = list(by_day.values())
    if len(values) < 2 or statistics.stdev(values) == 0:
        return None
    return statistics.mean(values) / statistics.stdev(values)


def max_drawdown(curve: list[dict]) -> float:
    peak = 0.0
    drawdown = 0.0
    for point in curve:
        peak = max(peak, point["cumulative_pnl"])
        drawdown = min(drawdown, point["cumulative_pnl"] - peak)
    return drawdown


def main() -> None:
    output = []
    audits = {}
    hashes = {}
    for model in MODELS:
        for hurdle in HURDLES:
            rows, model_hashes, audit = load_rows(model=model, minimum_edge=hurdle)
            hashes[f"{model}:{hurdle:g}"] = model_hashes
            audits[f"{model}:{hurdle:g}"] = audit
            policy = Policy(
                name=f"{model}_edge_{hurdle:g}",
                max_ticket_liability=250.0,
                offset_moneyline=True,
                capital=10_000.0,
                contract_cap=500.0,
                combo_cap=500.0,
                fixture_cap=1_000.0,
                minimum_edge=hurdle,
            )
            for sport in ("NFL", "MLB"):
                result = run(rows, policy, sport)
                sh = daily_sharpe(result["equity_curve"])
                output.append(
                    {
                        "model": model,
                        "edge_hurdle": hurdle,
                        "sport": sport,
                        "accepted": result["accepted"],
                        "peak_committed_cash": result["peak_committed_cash"],
                        "peak_offset_credit": result["peak_offset_credit"],
                        "accepted_edge": result["accepted_edge_before_outcomes"],
                        "ending_pnl": result["retrospective_scaled_edge_proxy"],
                        "max_drawdown": max_drawdown(result["equity_curve"]),
                        "daily_sharpe": sh,
                        "annualized_sharpe_252": sh * math.sqrt(252.0) if sh is not None else None,
                    }
                )
    payload = {
        "fixed_policy": {
            "ticket_cap": 250,
            "contract_cap": 500,
            "combo_cap": 500,
            "fixture_cap": 1000,
            "offset_moneyline": True,
            "capital": 10000,
        },
        "models": MODELS,
        "hurdles": HURDLES,
        "input_hashes": hashes,
        "audit": audits,
        "results": output,
        "limitations": [
            "Historical fills are hypothetical public-print fills with no queue or fill elasticity.",
            "Sharpe is settlement-day descriptive Sharpe over a short sample.",
            "Pinnacle is not present in the archived fair-value rows.",
        ],
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "edge_hurdle_fixed_models.json").write_text(json.dumps(payload, indent=2) + "\n")
    with (OUT / "edge_hurdle_fixed_models.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=output[0].keys())
        writer.writeheader()
        writer.writerows(output)
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()

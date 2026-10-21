#!/usr/bin/env python3
"""Vary only the archived fair-value model under the locked shadow policy."""

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
    models = ("kalshi", "polymarket", "exchange_blend_equal", "exchange_blend_pm75")
    policy = Policy(
        name="locked_loose_offset_edge15bp_ticket250",
        max_ticket_liability=250.0,
        offset_moneyline=True,
        capital=10_000.0,
        contract_cap=500.0,
        combo_cap=500.0,
        fixture_cap=1_000.0,
        minimum_edge=0.0015,
    )
    output = []
    audits = {}
    hashes = {}
    for model in models:
        rows, model_hashes, audit = load_rows(model=model, minimum_edge=0.0015)
        hashes[model] = model_hashes
        audits[model] = audit
        for sport in ("NFL", "MLB"):
            result = run(rows, policy, sport)
            sh = daily_sharpe(result["equity_curve"])
            output.append(
                {
                    "model": model,
                    "sport": sport,
                    "candidates": sum(
                        v.get("candidates", 0)
                        for k, v in audit.items()
                        if ("nfl_" in k and sport == "NFL") or ("mlb_" in k and sport == "MLB")
                    ),
                    "accepted": result["accepted"],
                    "peak_committed_cash": result["peak_committed_cash"],
                    "peak_offset_credit": result["peak_offset_credit"],
                    "accepted_edge": result["accepted_edge_before_outcomes"],
                    "ending_pnl": result["retrospective_scaled_edge_proxy"],
                    "max_drawdown": max_drawdown(result["equity_curve"]),
                    "daily_sharpe": sh,
                    "annualized_sharpe_252": sh * math.sqrt(252.0) if sh is not None else None,
                    "accepted_offset_eligible_share": result["accepted_offset_eligible_share"],
                }
            )
    payload = {
        "policy": {
            "edge_after_fee": 0.0015,
            "ticket_cap": 250,
            "contract_cap": 500,
            "combo_cap": 500,
            "fixture_cap": 1000,
            "offset_moneyline": True,
        },
        "models": models,
        "input_hashes": hashes,
        "audit": audits,
        "results": output,
        "limitations": [
            "Archived PM75/equal rows are exchange blends and do not contain a verified causal Pinnacle liquidity-weighted fair value.",
            "Public prints are hypothetical full fills; no queue, fill elasticity, or adverse-selection model.",
            "Sharpe uses settlement-day P&L and is descriptive for this short sample.",
        ],
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "offset_models_fixed_config.json").write_text(json.dumps(payload, indent=2) + "\n")
    with (OUT / "offset_models_fixed_config.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=output[0].keys())
        writer.writeheader()
        writer.writerows(output)
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()

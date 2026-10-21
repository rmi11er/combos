#!/usr/bin/env python3
"""Test tail-only correlation charges under the loose offset policy."""

from __future__ import annotations

import csv
import json
import statistics
from pathlib import Path

from offsetting_allocation_backtest import Policy, load_rows, run

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "analysis/offsetting_allocation_v1"


def transform(rows: list[dict], threshold: float, mode: str) -> list[dict]:
    out = []
    for row in rows:
        reserve = max(0.0, float(row.get("stressed_upper", row["fair_point"])) - float(row["fair_point"]))
        if mode == "reject_tail" and reserve >= threshold:
            continue
        adjusted = dict(row)
        if mode == "excess_charge":
            adjusted["fair_point"] = float(row["fair_point"]) + max(0.0, reserve - threshold)
        elif mode == "full_tail_charge" and reserve >= threshold:
            adjusted["fair_point"] = float(row["fair_point"]) + reserve
        out.append(adjusted)
    return out


def mean_resolved_pnl(rows: list[dict]) -> tuple[int, float, float, float]:
    pnls = []
    for row in rows:
        q = float(row["quantity"])
        fee = float(row["maker_fee"])
        pnl = q * (float(row["yes_price"]) - float(row["yes_settlement"])) - fee
        pnls.append(pnl)
    return len(pnls), sum(pnls), statistics.mean(pnls) if pnls else 0.0, sum(v > 0 for v in pnls) / len(pnls) if pnls else 0.0


def main() -> None:
    rows, hashes, audit = load_rows(model="kalshi", minimum_edge=0.0)
    reserves = sorted(max(0.0, float(r.get("stressed_upper", r["fair_point"])) - float(r["fair_point"])) for r in rows)
    quantile = lambda q: reserves[int(q * (len(reserves) - 1))]
    p95, p98, p99, p995 = (quantile(q) for q in (0.95, 0.98, 0.99, 0.995))
    thresholds = [
        ("0.5%", 0.005), ("1.0%", 0.01), ("2.0%", 0.02),
        ("5.0%", 0.05), ("10.0%", 0.10),
        ("top_5pct", p95), ("top_2pct", p98), ("top_1pct", p99), ("top_0.5pct", p995),
    ]
    policy = Policy("tail_correlation", 250.0, True, 10_000.0, 500.0, 500.0, 1_000.0, 0.003)
    output = []
    for label, threshold in thresholds:
        for mode in ("reject_tail", "excess_charge", "full_tail_charge"):
            selected = transform(rows, threshold, mode)
            for sport in ("NFL", "MLB"):
                sport_rows = [r for r in selected if r.get("_sport") == sport and r.get("quote_allowed")]
                # Apply the final after-charge edge hurdle before the funded replay.
                eligible = [r for r in sport_rows if float(r["yes_price"]) - float(r["fair_point"]) - float(r["maker_fee"]) / float(r["quantity"]) >= 0.003]
                result = run(eligible, policy, sport)
                n, pnl, mean, win = mean_resolved_pnl(eligible)
                output.append({
                    "sport": sport, "threshold": label, "threshold_probability": threshold, "mode": mode,
                    "eligible_rows": len(eligible), "resolved_rows": n, "unconstrained_pnl": pnl,
                    "unconstrained_mean_pnl": mean, "unconstrained_win_rate": win,
                    "accepted": result["accepted"], "peak_committed_cash": result["peak_committed_cash"],
                    "funded_pnl": result["retrospective_scaled_edge_proxy"], "funded_max_drawdown": min(
                        [0.0] + [p["cumulative_pnl"] - max(q["cumulative_pnl"] for q in result["equity_curve"][:i+1]) for i, p in enumerate(result["equity_curve"])]
                    ),
                })
    payload = {"policy": {"edge": 0.003, "ticket_cap": 250, "contract_cap": 500, "combo_cap": 500, "fixture_cap": 1000, "offset": True}, "reserve_quantiles": {"p95": p95, "p98": p98, "p99": p99, "p995": p995}, "input_hashes": hashes, "audit": audit, "results": output}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "tail_correlation_charge_sweep.json").write_text(json.dumps(payload, indent=2) + "\n")
    with (OUT / "tail_correlation_charge_sweep.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=output[0].keys()); writer.writeheader(); writer.writerows(output)
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()

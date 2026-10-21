#!/usr/bin/env python3
"""Plot settlement-based MLB equity curves from the allocation replay."""

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "analysis/offsetting_allocation_v1/results.json"
OUTPUT = ROOT / "analysis/offsetting_allocation_v1/mlb_equity_curves.png"
CSV_OUTPUT = ROOT / "analysis/offsetting_allocation_v1/mlb_equity_curves.csv"


def main() -> None:
    data = json.loads(INPUT.read_text())
    rows = []
    fig, ax = plt.subplots(figsize=(12, 6.5), dpi=160)
    for result in data["results_by_sport"]["MLB"]:
        curve = result["equity_curve"]
        if not curve:
            continue
        dates = [datetime.fromtimestamp(p["settled_at"], tz=timezone.utc) for p in curve]
        values = [p["cumulative_pnl"] for p in curve]
        label = result["policy"].replace("_", " ")
        ax.plot(dates, values, linewidth=1.5, label=label)
        for point in curve:
            rows.append(
                {
                    "policy": result["policy"],
                    "settled_at": point["settled_at"],
                    "settled_date_utc": datetime.fromtimestamp(
                        point["settled_at"], tz=timezone.utc
                    ).isoformat(),
                    "incremental_pnl": point["incremental_pnl"],
                    "cumulative_pnl": point["cumulative_pnl"],
                }
            )
    ax.axhline(0, color="#666666", linewidth=0.8)
    ax.set_title("MLB settlement-based cumulative P&L by allocation policy")
    ax.set_xlabel("Settlement time (UTC)")
    ax.set_ylabel("Cumulative retrospective P&L ($)")
    ax.grid(True, axis="y", alpha=0.25)
    ax.legend(loc="best", frameon=False, ncol=2)
    fig.autofmt_xdate()
    fig.tight_layout()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUTPUT, bbox_inches="tight")
    plt.close(fig)
    with CSV_OUTPUT.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(OUTPUT)
    print(CSV_OUTPUT)


if __name__ == "__main__":
    main()

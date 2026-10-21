#!/usr/bin/env python3
"""Replay the locked shadow research configuration across saved MLB/NFL data."""

from __future__ import annotations

import json
from pathlib import Path

from offsetting_allocation_backtest import Policy, load_rows, run

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/offset_pm75_loose_shadow_20260909.json"
OUT = ROOT / "analysis/offsetting_allocation_v1/offset_pm75_loose_config_results.json"


def main() -> None:
    config = json.loads(CONFIG.read_text())
    rows, hashes, audit = load_rows(model="exchange_blend_pm75", minimum_edge=0.0015)
    policy = Policy(
        name="pm75_loose_offset_ticket250_edge15bp",
        max_ticket_liability=250.0,
        offset_moneyline=True,
        capital=10000.0,
        contract_cap=500.0,
        combo_cap=500.0,
        fixture_cap=1000.0,
        minimum_edge=0.0015,
    )
    results = {sport: run(rows, policy, sport) for sport in ("NFL", "MLB")}
    output = {
        "config": config,
        "model_replay": "exchange_blend_pm75",
        "minimum_edge_after_fee": 0.0015,
        "rows": len(rows),
        "input_hashes": hashes,
        "audit": audit,
        "results": results,
        "limitations": [
            "Saved rows provide the archived PM75 challenger, not a verified liquidity-weighted three-source Pinnacle fair value.",
            "Cash remains gross collateral; offset credit only changes internal contract/fixture risk usage.",
            "Public prints are hypothetical full fills with no queue or fill elasticity.",
        ],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(output, indent=2) + "\n")
    print(json.dumps({sport: {k: v for k, v in result.items() if k != "equity_curve"} for sport, result in results.items()}, indent=2))
    print(OUT)


if __name__ == "__main__":
    main()

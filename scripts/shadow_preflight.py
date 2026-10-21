#!/usr/bin/env python3
"""Offline preflight for a shadow-live run.

This command never opens a socket or submits an order. It validates the locked
shadow configuration, source polling configuration, storage capacity, and (if
provided) the runtime manifest before collectors/workers are started.
"""

import argparse
import json
import os
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from combos.event_store import EventStore
from combos.readiness import readiness
from combos.weighted_fair import WeightPolicy


def run(config_path: Path, weights_path: Path, polling_path: Path, *, db: Path | None = None,
        minimum_free_gb: float = 5.0) -> dict:
    config = json.loads(config_path.read_text())
    weights = WeightPolicy(**json.loads(weights_path.read_text()))
    polling = json.loads(polling_path.read_text())
    blockers = []
    if config.get("mode") != "shadow":
        blockers.append("shadow_mode_required")
    if config.get("orders_enabled") is not False:
        blockers.append("orders_must_be_disabled")
    if config.get("automatic_promotion") is not False:
        blockers.append("automatic_promotion_must_be_disabled")
    free_gb = shutil.disk_usage(ROOT).free / (1024 ** 3)
    if free_gb < minimum_free_gb:
        blockers.append("insufficient_disk_capacity")
    static = readiness(config, weights, polling, time.time())
    blockers.extend(static["shadow_configuration_blockers"])
    manifest_status = "not_checked"
    if db is not None:
        store = EventStore(db)
        try:
            manifest = store.get("runtime", "manifest")
            if not manifest:
                blockers.append("runtime_manifest_missing")
                manifest_status = "missing"
            else:
                manifest_status = "present"
        finally:
            store.close()
    return {"ready": not blockers, "blockers": list(dict.fromkeys(blockers)),
            "free_disk_gb": round(free_gb, 3), "manifest": manifest_status,
            "static_readiness": static}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "config/runtime.json")
    parser.add_argument("--weights", type=Path, default=ROOT / "config/weighting.json")
    parser.add_argument("--polling", type=Path, default=ROOT / "config/oddspapi_polling.json")
    parser.add_argument("--db", type=Path)
    parser.add_argument("--minimum-free-gb", type=float, default=5.0)
    args = parser.parse_args()
    result = run(args.config, args.weights, args.polling, db=args.db, minimum_free_gb=args.minimum_free_gb)
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0 if result["ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Build a reviewed NFL runtime from an independent payoff enumeration.

This does not enable orders. It only replaces the generic Pinnacle payoff
block with an auditable event-type and source-reference record after every
mapping in the review artifact passes the score-grid check.
"""

import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from combos.event_types import validate_event_type

LIMIT_REFERENCE = "https://docs.oddspapi.io/websocket/channels/odds#limit-max-allowed-stake"


def accepted_review(mapping, result):
    if not result:
        return False
    if result.get('status') == 'completed_period_binary_verified':
        return True
    # User accepts the Pinnacle tie-void basis for full-game moneylines.
    # Pricing already normalizes that conditional probability to half-on-tie.
    spec = mapping.get('pinnacle') or {}
    return (mapping.get('market_type') == 'moneyline'
            and mapping.get('period', 'full_game') == 'full_game'
            and spec.get('catalog', {}).get('marketType') == 'moneyline'
            and spec.get('catalog', {}).get('period') == 'result'
            and result.get('status') == 'void_basis_required'
            and result.get('market_type') == 'moneyline'
            and result.get('period') == 'full_game'
            and not result.get('mismatches')
            and result.get('void_score_pairs', 0) > 0)


def authorize(runtime_path: Path, review_path: Path, output: Path) -> dict:
    runtime = json.loads(runtime_path.read_text())
    review_rows = json.loads(review_path.read_text())
    by_key = {row["market_key"]: row["review"] for row in review_rows}
    candidate = copy.deepcopy(runtime)
    review_hash = hashlib.sha256(review_path.read_bytes()).hexdigest()
    statuses = {}
    for mapping in candidate["mappings"]:
        result = by_key.get(mapping["market_key"])
        if not accepted_review(mapping, result):
            raise ValueError(f"mapping_not_verified:{mapping['market_key']}:{(result or {}).get('status')}")
        profile = validate_event_type(mapping)
        mapping["event_type"] = profile["event_type"]
        normalized = result['status'] == 'void_basis_required'
        mapping["event_resolution"] = {
            "reference": profile["reference"],
            "normal_game_basis": "moneyline_tie_normalized_user_accepted" if normalized else "score_grid_verified",
            "exception_policy": "status_and_exchange_terms_guard; no silent payoff substitution",
            "review_artifact_sha256": review_hash,
            "score_pairs_checked": result["score_pairs_checked"],
            "void_score_pairs": result.get("void_score_pairs", 0),
        }
        spec = mapping["pinnacle"]
        spec["payoff_reference"] = f"{profile['reference']}:score-grid:{review_hash}"
        spec["settlement_policy"] = "nonplayer_rules_v1"
        spec["limit_currency"] = "USD"
        spec["limit_unit"] = "stake"
        spec["limit_reference"] = LIMIT_REFERENCE
        spec["selector_status"] = "exact_catalog_candidate; payoff_grid_verified; USD_stake_limit_documented"
        mapping.pop("pricing_block_reason", None)
        mapping["payoff_review"] = {**mapping.get("payoff_review", {}), "status": 'moneyline_tie_normalized_user_accepted' if normalized else result["status"],
                                     "review_artifact_sha256": review_hash}
        statuses[result["status"]] = statuses.get(result["status"], 0) + 1
    candidate["comment"] = "NFL non-player mappings authorized by versioned event types and independent score-grid payoff review; orders remain disabled."
    candidate["launch_status"] = "shadow_authorized_orders_disabled"
    candidate["orders_enabled"] = False
    candidate["live_enabled"] = False
    candidate["automatic_promotion"] = False
    candidate["mapping_authorization"] = {
        "review_artifact": str(review_path), "review_artifact_sha256": review_hash,
        "statuses": statuses, "limit_reference": LIMIT_REFERENCE,
    }
    output.write_text(json.dumps(candidate, indent=2, allow_nan=False) + "\n")
    return {"mappings": len(candidate["mappings"]), "statuses": statuses,
            "orders_enabled": candidate["orders_enabled"], "output": str(output)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--review", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(authorize(args.runtime, args.review, args.output), indent=2))

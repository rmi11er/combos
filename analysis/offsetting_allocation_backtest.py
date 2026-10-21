#!/usr/bin/env python3
"""Exploratory small-ticket and offset-aware allocation replay.

The input is the saved sibling ``combos`` historical replay.  Cash remains
gross collateral: offsetting credit affects only canonical game/underlying risk
budgets.  It is granted only to distinct-fixture, full-game moneyline tickets
whose selected teams can be recovered exactly.  Spread, total and unknown
structures remain gross-risk-only.

This is a capacity experiment, not a fill model.  Public prints are treated as
hypothetical fills and maker fees are scaled linearly when a ticket is resized.
That fee convention is explicit because exchange fee rounding at new sizes is
not reconstructed here.
"""

from __future__ import annotations

import argparse
import gzip
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = (ROOT / "../combos").resolve()
MLB_DATES = ("01", "03", "05", "07", "09", "11", "15", "17", "19", "21", "29")
MLB_DATE_PREFIX = "2026-07-"


@dataclass(frozen=True)
class Policy:
    name: str
    max_ticket_liability: Optional[float]
    offset_moneyline: bool
    capital: float = 10_000.0
    contract_cap: float = 100.0
    combo_cap: float = 100.0
    fixture_cap: float = 250.0
    minimum_edge: float = 0.003


@dataclass
class Position:
    evaluation_id: str
    at: float
    settled_at: Optional[float]
    yes_settlement: Optional[float]
    liability: float
    edge: float
    quantity: float
    yes_price: float
    maker_fee: float
    fixtures: Tuple[str, ...]
    contracts: Tuple[str, ...]
    combo: str
    moneyline_sides: Optional[Tuple[Tuple[str, str], ...]]


def digest(path: Path) -> str:
    import hashlib

    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def source_paths() -> Iterable[Tuple[str, Path]]:
    yield "NFL", SOURCE_ROOT / "runs/nfl_moneyline_replay_20260907/jan5_18"
    for day in MLB_DATES:
        yield (
            "MLB",
            SOURCE_ROOT
            / (
                "runs/mlb_historical_20260907/dated_fee_primary/"
                + MLB_DATE_PREFIX
                + day
                + "/replay"
            ),
        )


def _series(row: dict) -> Tuple[str, ...]:
    return tuple(row.get("source", {}).get("series", ()))


def _moneyline_team_from_contract(contract: str) -> Optional[str]:
    if ":moneyline:" in contract:
        return contract.rsplit(":", 1)[1]
    return None


def _context_sides(context: dict) -> Optional[Tuple[Tuple[str, str], ...]]:
    """Recover MLB selected team from exact market ticker suffixes.

    This is used only for KXMLBGAME-only tickets.  An absent or ambiguous
    suffix deliberately makes the ticket ineligible for offset credit.
    """
    sides = []
    for leg in context.get("legs", ()):
        event = leg.get("event_ticker", "")
        market = leg.get("market_ticker", "")
        if not event or not market or "-" not in event or "-" not in market:
            return None
        fixture = "mlb:" + event.split("-", 1)[1]
        selected = market.rsplit("-", 1)[1]
        if len(selected) < 2 or leg.get("side") not in ("yes", "no"):
            return None
        teams = event.rsplit("-", 1)[1][-6:]
        if len(teams) != 6:
            return None
        pair = (teams[:3], teams[3:])
        if selected not in pair:
            return None
        if leg["side"] == "no":
            selected = pair[1] if selected == pair[0] else pair[0]
        sides.append((fixture, selected))
    return tuple(sorted(sides)) if sides else None


def load_rows(
    model: str = "kalshi", minimum_edge: float = 0.003
) -> Tuple[List[dict], Dict[str, str], dict]:
    """Load Kalshi rows and exact context orientation without changing inputs."""
    rows: List[dict] = []
    hashes: Dict[str, str] = {}
    audit: Dict[str, dict] = {}
    for sport, root in source_paths():
        opportunities = root / "opportunities.json"
        context_path = root / "pricing_context.jsonl.gz"
        if not opportunities.exists() or not context_path.exists():
            continue
        hashes[str(opportunities)] = digest(opportunities)
        hashes[str(context_path)] = digest(context_path)
        data = json.loads(opportunities.read_text())
        selected: Dict[str, dict] = {}
        counts = Counter()
        for row in data["opportunities"]:
            if row.get("model") != model:
                continue
            counts["model_rows"] += 1
            if not row.get("quote_allowed", False):
                counts["quote_guard_rejected"] += 1
                continue
            quantity = float(row["quantity"])
            edge_per = float(row["yes_price"]) - float(row["fair_point"])
            edge_per -= float(row["maker_fee"]) / quantity
            if edge_per < minimum_edge:
                counts["edge_rejected"] += 1
                continue
            if row["evaluation_id"] in selected:
                raise ValueError("duplicate evaluation id")
            selected[row["evaluation_id"]] = row
        del data
        contexts: Dict[str, Optional[Tuple[Tuple[str, str], ...]]] = {}
        with gzip.open(context_path, "rt") as handle:
            for line in handle:
                context = json.loads(line)
                eid = context["evaluation_id"]
                row = selected.get(eid)
                if row is None:
                    continue
                if _series(row) == ("KXMLBGAME",):
                    contexts[eid] = _context_sides(context)
                elif sport == "NFL" and _series(row) == ("KXNFLGAME",):
                    values = []
                    for contract in row["buckets"]["contract"]:
                        team = _moneyline_team_from_contract(contract)
                        fixture = contract.rsplit(":moneyline:", 1)[0]
                        if team is None:
                            values = []
                            break
                        values.append((fixture, team))
                    contexts[eid] = tuple(sorted(values)) if values else None
                else:
                    contexts[eid] = None
        for eid, row in selected.items():
            sides = contexts.get(eid)
            if len(row["buckets"]["fixture"]) != len(set(row["buckets"]["fixture"])):
                raise ValueError("duplicate fixture inside source row")
            if sides is not None and tuple(sorted(row["buckets"]["fixture"])) != tuple(
                f for f, _ in sides
            ):
                raise ValueError("moneyline context fixture mismatch")
            row = dict(row)
            row["_sport"] = sport
            row["_moneyline_sides"] = sides
            rows.append(row)
            counts["candidates"] += 1
            counts["offset_eligible"] += int(sides is not None)
        if (
            digest(opportunities) != hashes[str(opportunities)]
            or digest(context_path) != hashes[str(context_path)]
        ):
            raise ValueError("source changed while reading")
        audit[str(opportunities)] = dict(counts)
    rows.sort(key=lambda r: (float(r["at"]), r["evaluation_id"]))
    return rows, hashes, audit


def _scaled_position(row: dict, quantity: float) -> Position:
    original = float(row["quantity"])
    scale = quantity / original
    fee = float(row["maker_fee"]) * scale
    liability = quantity * (1.0 - float(row["yes_price"])) + fee
    edge = quantity * (float(row["yes_price"]) - float(row["fair_point"])) - fee
    return Position(
        row["evaluation_id"],
        float(row["at"]),
        row.get("settled_at"),
        row.get("yes_settlement"),
        liability,
        edge,
        quantity,
        float(row["yes_price"]),
        fee,
        tuple(row["buckets"]["fixture"]),
        tuple(row["buckets"]["contract"]),
        row["buckets"]["combo"][0],
        row.get("_moneyline_sides"),
    )


def _release(active: List[Position], at: float) -> Tuple[List[Position], float, float]:
    remain = []
    released = 0.0
    pnl = 0.0
    for pos in active:
        if pos.settled_at is not None and float(pos.settled_at) <= at:
            released += pos.liability
            pnl += pos.edge * 0.0  # edge is retained separately; no future input
        else:
            remain.append(pos)
    return remain, released, pnl


def _risk_usage(
    active: Sequence[Position], offset: bool
) -> Tuple[Dict[str, float], Dict[str, float], Dict[str, float], float]:
    contracts: Dict[str, float] = defaultdict(float)
    combos: Dict[str, float] = defaultdict(float)
    fixtures: Dict[str, float] = defaultdict(float)
    gross = 0.0
    by_fixture_side: Dict[Tuple[str, str], float] = defaultdict(float)
    by_contract_side: Dict[Tuple[str, str], float] = defaultdict(float)
    offset_eligible: Dict[str, bool] = {}
    for pos in active:
        gross += pos.liability
        combos[pos.combo] += pos.liability
        eligible_fixtures = set()
        eligible = offset and pos.moneyline_sides is not None
        if eligible and pos.moneyline_sides:
            for fixture, team in pos.moneyline_sides:
                by_contract_side[(fixture, team)] += pos.liability
                eligible_fixtures.add(fixture)
        for contract in pos.contracts:
            fixture = contract.split(":moneyline:", 1)[0]
            if ":winner" in contract:
                fixture = contract.rsplit(":winner", 1)[0]
            if fixture not in eligible_fixtures:
                contracts[contract] += pos.liability
        for fixture in pos.fixtures:
            if eligible and pos.moneyline_sides:
                teams = [team for f, team in pos.moneyline_sides if f == fixture]
                if len(teams) == 1:
                    by_fixture_side[(fixture, teams[0])] += pos.liability
                    offset_eligible[fixture] = True
                    continue
            fixtures[fixture] += pos.liability
            offset_eligible[fixture] = False
    if offset:
        contract_grouped: Dict[str, Dict[str, float]] = defaultdict(dict)
        for (fixture, team), value in by_contract_side.items():
            contract_grouped[fixture][team] = value
        for fixture, sides in contract_grouped.items():
            contracts[fixture] = max(sides.values())
        grouped: Dict[str, Dict[str, float]] = defaultdict(dict)
        for (fixture, team), value in by_fixture_side.items():
            grouped[fixture][team] = value
        for fixture, sides in grouped.items():
            fixtures[fixture] = max(sides.values())
    return dict(contracts), dict(combos), dict(fixtures), gross


def _would_fit(
    active: Sequence[Position], candidate: Position, policy: Policy, cash: float
) -> bool:
    proposed = list(active) + [candidate]
    contracts, combos, fixtures, _ = _risk_usage(proposed, policy.offset_moneyline)
    if cash + 1e-9 < candidate.liability:
        return False
    if any(value > policy.contract_cap + 1e-9 for value in contracts.values()):
        return False
    if any(value > policy.combo_cap + 1e-9 for value in combos.values()):
        return False
    if any(value > policy.fixture_cap + 1e-9 for value in fixtures.values()):
        return False
    return True


def run(
    rows: Sequence[dict], policy: Policy, sport_filter: Optional[str] = None
) -> dict:
    active: List[Position] = []
    cash = policy.capital
    peak_cash = 0.0
    peak_net = 0.0
    peak_gross = 0.0
    peak_offset_credit = 0.0
    accepted: List[Position] = []
    rejected = Counter()
    realized_pnl = 0.0
    for row in rows:
        active, released, _ = _release(active, float(row["at"]))
        cash += released
        if row.get("_sport") not in ("NFL", "MLB"):
            rejected["sport"] += 1
            continue
        if sport_filter is not None and row.get("_sport") != sport_filter:
            continue
        quantity = float(row["quantity"])
        unit_liability = (1.0 - float(row["yes_price"])) + float(
            row["maker_fee"]
        ) / quantity
        if policy.max_ticket_liability is not None:
            quantity = min(quantity, policy.max_ticket_liability / unit_liability)
        if quantity <= 1e-9:
            rejected["ticket_cap"] += 1
            continue
        candidate = _scaled_position(row, quantity)
        if not _would_fit(active, candidate, policy, cash):
            rejected["risk_or_cash"] += 1
            continue
        active.append(candidate)
        accepted.append(candidate)
        cash -= candidate.liability
        contracts, combos, fixtures, gross = _risk_usage(
            active, policy.offset_moneyline
        )
        net = sum(fixtures.values())
        peak_cash = max(peak_cash, policy.capital - cash)
        peak_gross = max(peak_gross, gross)
        peak_net = max(peak_net, net)
        peak_offset_credit = max(peak_offset_credit, gross - net)
        if candidate.settled_at is not None and float(candidate.settled_at) <= float(
            row["at"]
        ):
            raise ValueError("settlement before decision")
    # Outcome P&L is retrospective evaluation only; it does not fund decisions.
    settlement_pnl: Dict[float, float] = defaultdict(float)
    for pos in accepted:
        if pos.settled_at is not None and pos.yes_settlement is not None:
            # Fee was included in edge scaling; reconstruct observed net P&L.
            pnl = (
                pos.quantity * (pos.yes_price - float(pos.yes_settlement))
                - pos.maker_fee
            )
            realized_pnl += pnl
            settlement_pnl[float(pos.settled_at)] += pnl
    equity_curve = []
    cumulative = 0.0
    for settled_at in sorted(settlement_pnl):
        cumulative += settlement_pnl[settled_at]
        equity_curve.append(
            {
                "settled_at": settled_at,
                "incremental_pnl": settlement_pnl[settled_at],
                "cumulative_pnl": cumulative,
            }
        )
    gross_now = _risk_usage(active, False)[3]
    net_now = max(_risk_usage(active, True)[2].values(), default=0.0)
    offset_credit = peak_offset_credit
    eligible = sum(pos.moneyline_sides is not None for pos in accepted)
    return {
        "policy": policy.name,
        "offset_moneyline": policy.offset_moneyline,
        "max_ticket_liability": policy.max_ticket_liability,
        "rows": len(rows),
        "accepted": len(accepted),
        "rejected": dict(rejected),
        "accepted_offset_eligible": eligible,
        "accepted_offset_eligible_share": eligible / len(accepted)
        if accepted
        else None,
        "peak_committed_cash": peak_cash,
        "peak_gross_active_liability": peak_gross,
        "peak_net_fixture_liability": peak_net,
        "peak_offset_credit": offset_credit,
        "ending_gross_active_liability": gross_now,
        "ending_net_fixture_liability": net_now,
        "accepted_edge_before_outcomes": sum(p.edge for p in accepted),
        "retrospective_scaled_edge_proxy": realized_pnl,
        "equity_curve": equity_curve,
        "average_ticket_liability": sum(p.liability for p in accepted) / len(accepted)
        if accepted
        else None,
        "unique_fixtures": len({f for p in accepted for f in p.fixtures}),
        "unique_combos": len({p.combo for p in accepted}),
        "method": (
            "chronological public-print hypothetical; gross cash; "
            "canonical fixture risk; no fill elasticity"
        ),
    }


def main() -> None:
    global SOURCE_ROOT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=SOURCE_ROOT)
    parser.add_argument(
        "--out", type=Path, default=ROOT / "analysis/offsetting_allocation_v1"
    )
    args = parser.parse_args()
    SOURCE_ROOT = args.source.resolve()
    rows, hashes, audit = load_rows()
    policies = [
        Policy("full_gross", None, False),
        Policy("ticket_50_gross", 50.0, False),
        Policy("ticket_25_gross", 25.0, False),
        Policy("ticket_10_gross", 10.0, False),
        Policy("ticket_50_moneyline_offset", 50.0, True),
        Policy("ticket_25_moneyline_offset", 25.0, True),
        Policy("ticket_10_moneyline_offset", 10.0, True),
    ]
    results = [run(rows, policy) for policy in policies]
    by_sport = {
        sport: [run(rows, policy, sport) for policy in policies]
        for sport in ("NFL", "MLB")
    }
    args.out.mkdir(parents=True, exist_ok=True)
    report = {
        "status": "exploratory_hypothetical_allocation_replay",
        "source_root": str(SOURCE_ROOT),
        "input_hashes": hashes,
        "audit": audit,
        "rows": len(rows),
        "results": results,
        "results_by_sport": by_sport,
        "limitations": [
            (
                "Cash remains gross collateral; offset credit applies only to "
                "internal fixture risk budgets."
            ),
            (
                "Only reviewed full-game moneyline tickets with recoverable "
                "selected teams receive offset credit."
            ),
            (
                "MLB spread, total, same-game and unknown structures remain "
                "gross-risk-only."
            ),
            (
                "Observed public prints are hypothetical fills; no fill elasticity "
                "or queue priority is estimated."
            ),
            (
                "Resized maker fees are scaled linearly; exchange rounding at new "
                "quantities is unresolved."
            ),
            (
                "No policy is promoted or suitable as a live limit without human "
                "approval and forward testing."
            ),
        ],
    }
    (args.out / "results.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"out": str(args.out), "rows": len(rows), "results": results}))


if __name__ == "__main__":
    main()

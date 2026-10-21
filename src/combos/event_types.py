"""Versioned event-resolution profiles for rapid weekly market onboarding.

An event type is the contract between provider selectors, exchange settlement,
and odds translation.  Mapping files select a profile; they do not embed
provider-specific resolution logic.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class EventType:
    name: str
    version: int
    market_types: tuple[str, ...]
    periods: tuple[str, ...]
    tie_behavior: str
    threshold_behavior: str | None
    exception_behavior: str
    pinnacle_market_types: tuple[str, ...]

    @property
    def reference(self) -> str:
        return f"{self.name}:v{self.version}"


EVENT_TYPES: dict[str, EventType] = {
    "nfl.full_game.moneyline": EventType(
        "nfl.full_game.moneyline", 1, ("moneyline",), ("full_game",),
        "exchange_half_on_tie", None, "explicit_exception_interval", ("moneyline",)),
    "nfl.period.moneyline": EventType(
        "nfl.period.moneyline", 1, ("moneyline",), ("first_half", "first_quarter"),
        "exchange_no_on_tie", None, "explicit_exception_interval", ("spreads",)),
    "nfl.full_game.spread": EventType(
        "nfl.full_game.spread", 1, ("spreads",), ("full_game",),
        "binary_threshold", "strict", "explicit_exception_interval", ("spreads",)),
    "nfl.full_game.total": EventType(
        "nfl.full_game.total", 1, ("totals",), ("full_game",),
        "binary_threshold", "strict", "explicit_exception_interval", ("totals",)),
    "nfl.full_game.team_total": EventType(
        "nfl.full_game.team_total", 1, ("team_totals",), ("full_game",),
        "binary_threshold", "strict", "explicit_exception_interval", ("teamtotals-team1", "teamtotals-team2")),
}

for family, kind, native in [('spread','spreads',('spreads',)),('total','totals',('totals',)),
                              ('team_total','team_totals',('teamtotals-team1','teamtotals-team2'))]:
    name='nfl.period.'+family
    EVENT_TYPES[name]=EventType(name,1,(kind,),('first_half','first_quarter'),
        'binary_threshold','strict','explicit_exception_interval',native)
EVENT_TYPES['nfl.period.tie']=EventType('nfl.period.tie',1,('moneyline',),
    ('first_half','first_quarter'),'exchange_yes_on_tie',None,'explicit_exception_interval',())


def get_event_type(name: str) -> EventType:
    try:
        return EVENT_TYPES[name]
    except KeyError:
        raise ValueError(f"unknown event type: {name}") from None


def infer_event_type(mapping: Mapping[str, Any]) -> EventType:
    """Resolve an explicit mapping type, or infer legacy NFL mappings."""
    explicit = mapping.get("event_type")
    if explicit:
        event_type = get_event_type(explicit)
    else:
        period = mapping.get("period", "full_game")
        kind = mapping.get("market_type")
        if kind == "moneyline":
            name = "nfl.full_game.moneyline" if period == "full_game" else "nfl.period.moneyline"
            if period!='full_game' and mapping.get('tie_settlement')=='tie_wins':name='nfl.period.tie'
        else:
            name = {
                "spreads": "nfl.full_game.spread",
                "totals": "nfl.full_game.total",
                "team_totals": "nfl.full_game.team_total",
            }.get(kind)
            if name is None:
                raise ValueError("unsupported NFL event type")
            if period!='full_game':name=name.replace('full_game','period')
        event_type = EVENT_TYPES[name]
    if mapping.get("market_type") not in event_type.market_types:
        raise ValueError("event type market family mismatch")
    if mapping.get("period", "full_game") not in event_type.periods:
        raise ValueError("event type period mismatch")
    return event_type


def validate_event_type(mapping: Mapping[str, Any]) -> dict[str, Any]:
    event_type = infer_event_type(mapping)
    spec = mapping.get("event_resolution") or {}
    if spec.get("reference") not in (None, event_type.reference):
        raise ValueError("event resolution reference mismatch")
    return {
        "event_type": event_type.name,
        "reference": event_type.reference,
        "tie_behavior": event_type.tie_behavior,
        "threshold_behavior": event_type.threshold_behavior,
        "exception_behavior": event_type.exception_behavior,
        "pinnacle_market_types": event_type.pinnacle_market_types,
    }

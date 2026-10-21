"""Small storage contracts used to decouple domain decisions from SQLite."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol


class EventRepository(Protocol):
    def append(self, kind: str, source: str, payload: Mapping[str, Any], event_key: str, received_at: float | None = None) -> int:
        ...

    def read(self, after: int = 0, limit: int = 500, *, payload_kinds: set[str] | None = None) -> list[dict[str, Any]]:
        ...

    def cursor(self, name: str) -> int:
        ...


class RiskRepository(Protocol):
    def available(self) -> int:
        """Return available capital in fixed-point units."""

    def reserve(self, identifier: str, creator: str, cost_dollars: Any, buckets: Mapping[str, list[str]],
                expires_at: float, context: Mapping[str, Any], **kwargs: Any) -> Mapping[str, Any]:
        ...

    def transition(self, identifier: str, status: str, at: float, source_seq: int, payout_dollars: Any = None) -> None:
        ...

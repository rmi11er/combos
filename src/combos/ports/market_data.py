"""Provider-neutral market data contracts."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any, Protocol


class MarketDataSource(Protocol):
    venue: str

    def observations(self, market_keys: Iterable[str], at: float) -> list[Mapping[str, Any]]:
        """Return normalized observations; provider payloads stay in adapters."""
        ...


class RfqSource(Protocol):
    def events(self, after: int, limit: int = 500) -> list[Mapping[str, Any]]:
        ...

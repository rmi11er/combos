"""Execution and reconciliation boundaries; no implementation is enabled."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol


class QuoteTransport(Protocol):
    def submit(self, request: Mapping[str, Any]) -> Mapping[str, Any]:
        """Submit exactly one quote attempt; retries belong to the journal."""
        ...

    def cancel(self, request: Mapping[str, Any]) -> Mapping[str, Any]:
        ...


class AccountEvidenceSource(Protocol):
    def fills(self, *, subaccount: int, cursor: str | None = None) -> Mapping[str, Any]:
        ...

    def orders(self, *, subaccount: int, cursor: str | None = None) -> Mapping[str, Any]:
        ...

"""Signed inventory and settlement accounting for maker-side fills.

This module is deliberately separate from execution transport and risk
reservations.  It records economic truth for both buy and sell fills, including
negative (short) positions, while requiring an explicit ownership check before
any caller may release strategy capital.
"""

from __future__ import annotations

from decimal import Decimal
import json
import sqlite3
from typing import Any, Mapping

from .execution_fills import normalize_fill
from .execution_ownership import match_maker_fill


def _d(value: Any) -> Decimal:
    return Decimal(str(value))


def _fmt(value: Decimal) -> str:
    return format(value, "f")


class InventoryLedger:
    """SQLite-backed, idempotent inventory ledger.

    The ledger stores normalized fill economics and settlement results. It does
    not infer strategy ownership from an account-wide fill feed.
    """

    def __init__(self, db_or_path):
        if hasattr(db_or_path, "execute"):
            self.db = db_or_path
            self._owns_db = False
        else:
            self.db = sqlite3.connect(db_or_path, isolation_level=None, timeout=10)
            self._owns_db = True
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS inventory_fills (
                exchange_index INTEGER NOT NULL,
                fill_id TEXT NOT NULL,
                ticker TEXT NOT NULL,
                subaccount_number INTEGER NOT NULL,
                economics TEXT NOT NULL,
                PRIMARY KEY(exchange_index, fill_id)
            );
            CREATE TABLE IF NOT EXISTS inventory_settlements (
                exchange_index INTEGER NOT NULL,
                ticker TEXT NOT NULL,
                subaccount_number INTEGER NOT NULL,
                result TEXT NOT NULL,
                value INTEGER NOT NULL,
                payload TEXT NOT NULL,
                PRIMARY KEY(exchange_index, ticker, subaccount_number)
            );
        """)

    def close(self) -> None:
        if self._owns_db:
            self.db.close()

    def ingest_fill(self, raw: Mapping[str, Any]) -> dict[str, Any]:
        fill = normalize_fill(dict(raw))
        identity = (fill["exchange_index"], fill["fill_id"])
        economics = json.dumps(fill, sort_keys=True, separators=(",", ":"))
        old = self.db.execute(
            "SELECT economics FROM inventory_fills WHERE exchange_index=? AND fill_id=?", identity
        ).fetchone()
        if old:
            if old["economics"] != economics:
                raise ValueError("conflicting fill economics")
            return {"inserted": False, "fill_id": fill["fill_id"]}
        self.db.execute(
            "INSERT INTO inventory_fills(exchange_index,fill_id,ticker,subaccount_number,economics) VALUES(?,?,?,?,?)",
            (fill["exchange_index"], fill["fill_id"], fill["ticker"], fill["subaccount_number"], economics),
        )
        return {"inserted": True, "fill_id": fill["fill_id"]}

    def ingest_owned_maker_fill(self, binding: Mapping[str, Any], raw: Mapping[str, Any]) -> dict[str, Any]:
        """Bind an account fill to a reviewed maker order before recording it."""
        matched = match_maker_fill(dict(binding), dict(raw))
        result = self.ingest_fill(raw)
        return {**result, "matched": True, "quote_id": matched["quote_id"], "rfq_id": matched["rfq_id"]}

    def _fills(self, ticker: str, exchange_index: int, subaccount: int) -> list[dict[str, Any]]:
        rows = self.db.execute(
            "SELECT economics FROM inventory_fills WHERE ticker=? AND exchange_index=? AND subaccount_number=?",
            (ticker, exchange_index, subaccount),
        ).fetchall()
        return [json.loads(row["economics"]) for row in rows]

    def positions(self, ticker: str, exchange_index: int, subaccount: int) -> dict[str, Any]:
        if type(exchange_index) is not int or exchange_index < 0:
            raise ValueError("invalid exchange index")
        if type(subaccount) is not int or not 0 <= subaccount <= 63:
            raise ValueError("invalid subaccount")
        signed = {"yes": Decimal(0), "no": Decimal(0)}
        trade_cash = Decimal(0)
        fees = Decimal(0)
        for fill in self._fills(ticker, exchange_index, subaccount):
            sign = Decimal(1) if fill["action"] == "buy" else Decimal(-1)
            signed[fill["side"]] += sign * _d(fill["quantity"])
            trade_cash += -sign * _d(fill["principal"]) - _d(fill["fee"])
            fees += _d(fill["fee"])
        return {
            "ticker": ticker,
            "exchange_index": exchange_index,
            "subaccount": subaccount,
            "yes_quantity": _fmt(signed["yes"]),
            "no_quantity": _fmt(signed["no"]),
            "trade_cash_flow_dollars": _fmt(trade_cash),
            "fees_dollars": _fmt(fees),
        }

    def settle(
        self,
        settlement: Mapping[str, Any],
        *,
        ownership_verified: bool = False,
    ) -> dict[str, Any]:
        ticker = settlement.get("ticker")
        exchange_index = settlement.get("exchange_index")
        subaccount = settlement.get("subaccount_number", settlement.get("subaccount"))
        if not isinstance(ticker, str) or not ticker:
            raise ValueError("settlement ticker required")
        if type(exchange_index) is not int or exchange_index < 0:
            raise ValueError("invalid settlement exchange")
        if type(subaccount) is not int or not 0 <= subaccount <= 63:
            raise ValueError("explicit settlement subaccount required")
        result = settlement.get("market_result")
        if result not in ("yes", "no", "scalar"):
            raise ValueError("unknown settlement result")
        value = settlement.get("value")
        if result in ("yes", "no"):
            expected = 100 if result == "yes" else 0
            if value is not None and (type(value) is not int or value != expected):
                raise ValueError("settlement value contradicts result")
            value = expected
        elif type(value) is not int or not 0 <= value <= 100:
            raise ValueError("scalar payout value required")
        key = (exchange_index, ticker, subaccount)
        payload = json.dumps(dict(settlement), sort_keys=True, separators=(",", ":"))
        old = self.db.execute(
            "SELECT payload FROM inventory_settlements WHERE exchange_index=? AND ticker=? AND subaccount_number=?",
            key,
        ).fetchone()
        if old:
            if old["payload"] != payload:
                raise ValueError("conflicting settlement evidence")
            return self._settlement_result(settlement, ownership_verified)
        position = self.positions(ticker, exchange_index, subaccount)
        yes_qty, no_qty = _d(position["yes_quantity"]), _d(position["no_quantity"])
        yes_payout, no_payout = _d(value) / 100, Decimal(1) - _d(value) / 100
        settlement_cash = yes_qty * yes_payout + no_qty * no_payout
        pnl = _d(position["trade_cash_flow_dollars"]) + settlement_cash
        self.db.execute(
            "INSERT INTO inventory_settlements VALUES(?,?,?,?,?,?)",
            (exchange_index, ticker, subaccount, result, value, payload),
        )
        return {
            **self._settlement_result(settlement, ownership_verified),
            "yes_quantity": position["yes_quantity"],
            "no_quantity": position["no_quantity"],
            "trade_cash_flow_dollars": position["trade_cash_flow_dollars"],
            "settlement_cash_flow_dollars": _fmt(settlement_cash),
            "pnl_dollars": _fmt(pnl),
        }

    @staticmethod
    def _settlement_result(settlement: Mapping[str, Any], ownership_verified: bool) -> dict[str, Any]:
        return {
            "ticker": settlement["ticker"],
            "exchange_index": settlement["exchange_index"],
            "subaccount": settlement.get("subaccount_number", settlement.get("subaccount")),
            "settlement_reconciled": True,
            "capital_release_authorized": bool(ownership_verified),
        }

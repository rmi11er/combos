import pytest

from combos.inventory_ledger import InventoryLedger
from test_execution_ownership import evidence, fill


def make_fill(**updates):
    row = fill()
    row.update(updates)
    return row


def test_sell_side_short_position_and_settlement_pnl(tmp_path):
    ledger = InventoryLedger(tmp_path / "inventory.sqlite")
    maker_sell = make_fill(fill_id="sell", action="sell", side="yes", count_fp="10",
                           yes_price_dollars=".40", no_price_dollars=".60", fee_cost=".01")
    assert ledger.ingest_fill(maker_sell)["inserted"]
    assert not ledger.ingest_fill(maker_sell)["inserted"]
    position = ledger.positions("M", 0, 0)
    assert position["yes_quantity"] == "-10"
    assert position["trade_cash_flow_dollars"] == "3.99"
    result = ledger.settle({"ticker": "M", "exchange_index": 0, "subaccount_number": 0,
                            "market_result": "yes", "value": 100})
    assert result["settlement_cash_flow_dollars"] == "-10"
    assert result["pnl_dollars"] == "-6.01"
    assert not result["capital_release_authorized"]
    ledger.close()


def test_buy_and_sell_positions_net_without_pair_double_counting(tmp_path):
    ledger = InventoryLedger(tmp_path / "inventory.sqlite")
    yes = make_fill(fill_id="yes", action="buy", side="yes", count_fp="10",
                    yes_price_dollars=".90", no_price_dollars=".10", fee_cost=".01")
    no = make_fill(fill_id="no", action="sell", side="no", count_fp="2",
                   yes_price_dollars=".08", no_price_dollars=".92", fee_cost=".002")
    ledger.ingest_fill(yes); ledger.ingest_fill(no)
    result = ledger.settle({"ticker": "M", "exchange_index": 0, "subaccount_number": 0,
                            "market_result": "no", "value": 0}, ownership_verified=True)
    assert result["yes_quantity"] == "10" and result["no_quantity"] == "-2"
    assert result["settlement_cash_flow_dollars"] == "-2"
    assert result["capital_release_authorized"]


def test_conflicting_fill_and_settlement_evidence_is_rejected(tmp_path):
    ledger = InventoryLedger(tmp_path / "inventory.sqlite")
    row = make_fill(fill_id="f")
    ledger.ingest_fill(row)
    with pytest.raises(ValueError, match="conflicting fill"):
        ledger.ingest_fill(dict(row, fee_cost=".02"))
    settlement = {"ticker": "M", "exchange_index": 0, "subaccount_number": 0,
                  "market_result": "scalar", "value": 100}
    ledger.settle(settlement)
    with pytest.raises(ValueError, match="conflicting settlement"):
        ledger.settle(dict(settlement, value=0))
    ledger.close()


def test_owned_maker_fill_requires_order_binding(tmp_path):
    ledger = InventoryLedger(tmp_path / "inventory.sqlite")
    expected, quote, order = evidence()
    binding = __import__("combos.execution_ownership", fromlist=["match_maker_order"]).match_maker_order(
        expected, quote, order, 104, 105, 0
    )
    result = ledger.ingest_owned_maker_fill(binding, fill())
    assert result["matched"] and result["inserted"]
    ledger.close()

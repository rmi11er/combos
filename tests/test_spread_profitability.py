from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from spread_profitability import aggregate, bucket


def row(q, p, settlement, fee=0.):
    return dict(quantity=q, yes_price=p, yes_settlement=settlement, maker_fee=fee, settled_at=100 if settlement is not None else None)


def test_quantity_weighting_not_average_trade_return_or_double_weighting():
    r = aggregate([row(1, .5, 0), row(99, .9, 1)])
    assert r['known_net_cents_per_contract'] == pytest.approx(-9.4)
    assert r['known_net_pnl'] == pytest.approx(-9.4)


def test_unknowns_not_assigned_zero_pnl_and_cash_fees_included():
    r = aggregate([row(10, .5, 0, .1), row(90, .5, None, .9)])
    assert r['known_net_cents_per_contract'] == pytest.approx(49.)
    assert r['known_payout_notional'] == 10
    assert r['unknown_payout_notional'] == 90
    assert r['loose_final_pnl_bounds'] == pytest.approx([-41., 49.])


def test_bin_boundaries_and_empty_bucket():
    assert bucket(1.9999999999999998) == bucket(2.0000000000000018) == 1
    assert bucket(200) == 5
    assert aggregate([])['known_net_cents_per_contract'] is None

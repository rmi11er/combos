from decimal import Decimal
import pytest

from combos.domain import Contracts, Money, Price


def test_exchange_values_are_fixed_point_and_explicit():
    assert Money.of("1.23456").units == 12346
    assert Price.of(".25394").value == Decimal("0.2539")
    assert Contracts.of("1.001").quantity == Decimal("1.01")
    assert (Money.of("1.00") + Money.of(".25")).amount == Decimal("1.2500")


@pytest.mark.parametrize("factory,value", [(Money.of, "-1"), (Price.of, "1.1"), (Contracts.of, "nan")])
def test_exchange_values_reject_invalid_inputs(factory, value):
    with pytest.raises(ValueError):
        factory(value)

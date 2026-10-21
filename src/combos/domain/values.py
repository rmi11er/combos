"""Fixed-point value objects used at exchange and risk boundaries.

Analytics may continue to use floats, but values crossing an exchange, fee,
risk, or settlement boundary must be represented explicitly.  These wrappers
keep conversion visible and reject NaN, infinity, and negative quantities.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_CEILING, ROUND_HALF_UP
import math


def _decimal(value: Decimal | int | float | str, *, name: str) -> Decimal:
    try:
        result = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError(f"invalid {name}") from exc
    if not result.is_finite():
        raise ValueError(f"invalid {name}")
    return result


@dataclass(frozen=True, order=True)
class Money:
    """USD amount quantized to one ten-thousandth of a dollar."""

    amount: Decimal

    def __post_init__(self) -> None:
        value = _decimal(self.amount, name="money")
        if value < 0:
            raise ValueError("money cannot be negative")
        object.__setattr__(self, "amount", value.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP))

    @classmethod
    def of(cls, value: Decimal | int | float | str) -> "Money":
        return cls(_decimal(value, name="money"))

    @property
    def units(self) -> int:
        return int((self.amount * 10000).to_integral_value(rounding=ROUND_HALF_UP))

    def as_float(self) -> float:
        return float(self.amount)

    def __add__(self, other: "Money") -> "Money":
        if not isinstance(other, Money):
            return NotImplemented
        return Money(self.amount + other.amount)


@dataclass(frozen=True, order=True)
class Price:
    """Binary-contract price in dollars, represented at four decimals."""

    value: Decimal

    def __post_init__(self) -> None:
        value = _decimal(self.value, name="price")
        if not Decimal("0") <= value <= Decimal("1"):
            raise ValueError("price must be between zero and one")
        object.__setattr__(self, "value", value.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP))

    @classmethod
    def of(cls, value: Decimal | int | float | str) -> "Price":
        return cls(_decimal(value, name="price"))

    def as_float(self) -> float:
        return float(self.value)

    def cents(self) -> Decimal:
        return self.value * 100


@dataclass(frozen=True, order=True)
class Contracts:
    """Non-negative contract quantity, quantized to hundredths."""

    quantity: Decimal

    def __post_init__(self) -> None:
        value = _decimal(self.quantity, name="contracts")
        if value < 0:
            raise ValueError("contracts cannot be negative")
        object.__setattr__(self, "quantity", value.quantize(Decimal("0.01"), rounding=ROUND_CEILING))

    @classmethod
    def of(cls, value: Decimal | int | float | str) -> "Contracts":
        return cls(_decimal(value, name="contracts"))

    def as_float(self) -> float:
        return float(self.quantity)

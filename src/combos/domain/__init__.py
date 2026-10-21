"""Pure domain value objects and invariants.

The domain package has no database, network, or workflow imports.  New pricing
and risk code should use these types at its boundaries even while legacy
research modules continue to accept dictionaries internally.
"""

from .values import Contracts, Money, Price

__all__ = ["Contracts", "Money", "Price"]

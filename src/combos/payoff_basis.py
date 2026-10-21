"""Explicit scenario transformation from conditional sportsbook fair to cash payoff.

No tie/exception probabilities are inferred here. Callers supply assumptions;
these bounds are only as valid as those assumptions and the conditional fair.
"""
from itertools import product
import math


def interval(value):
    if len(value) != 2:
        raise ValueError('two probability endpoints required')
    lo, hi = value
    if any(type(v) not in (int, float) or not math.isfinite(v) for v in value) or not 0 <= lo <= hi <= 1:
        raise ValueError('invalid probability interval')
    return lo, hi


def exchange_payoff_bounds(conditional_fair, *, tie_probability,
                          exception_probability, exception_payoff):
    """Tie probability is conditional on no exceptional settlement.

    A normal tie pays 0.5 on each exchange side. Exception payoff is the target
    exchange contract's payout, not a sportsbook stake refund. The four-variable
    expression is multilinear, so extrema on rectangular intervals occur at corners.
    """
    q, tie, exception, payoff = map(interval, (conditional_fair, tie_probability,
                                              exception_probability, exception_payoff))
    values = [(1-e)*((1-t)*p + .5*t) + e*v
              for p, t, e, v in product(q, tie, exception, payoff)]
    return {'lower':min(values), 'upper':max(values),
            'basis':'explicit_conditional_payoff_scenario',
            'assumptions_empirically_validated':False}

"""Small-portfolio dependence bounds; independence is a benchmark, not a guarantee."""
from dataclasses import asdict
from functools import lru_cache
from itertools import combinations, product
import math
import numpy as np
from scipy.optimize import linprog
from .pricing import Interval, stressed_joint_upper


def independent_joint(intervals):
    if not 2 <= len(intervals) <= 4:
        raise ValueError('joint_model_requires_two_through_four_legs')
    return Interval(*(math.prod(getattr(v, k) for v in intervals) for k in ('lower', 'point', 'upper')))


@lru_cache(maxsize=8192)
def _moment_upper(bounds, rho):
    intervals = [Interval(lo, (lo+hi)/2, hi) for lo, hi in bounds]
    n = len(intervals)
    if n == 2:
        return stressed_joint_upper(*intervals, rho)
    states = np.array(list(product((0., 1.), repeat=n))).T
    rows, rhs = [], []
    for i, v in enumerate(intervals):
        rows.extend((states[i], -states[i])); rhs.extend((v.upper, -v.lower))
    for i, j in combinations(range(n), 2):
        rows.append(states[i]*states[j])
        rhs.append(stressed_joint_upper(intervals[i], intervals[j], rho))
    a, b = np.array(rows), np.array(rhs)
    c = np.zeros(2**n); c[-1] = -1
    solution = linprog(c, A_ub=a, b_ub=b, A_eq=np.ones((1, 2**n)), b_eq=[1.],
                       bounds=(0., None), method='highs', options={'time_limit': .25})
    if not solution.success:
        raise ValueError('joint_bound_solver_failed')
    # Use a feasible dual certificate: a primal optimum alone can understate
    # maximum payout because of solver tolerances. Repair any dual violation by
    # lowering the unrestricted normalization multiplier (sum state mass = 1).
    y = np.minimum(solution.ineqlin.marginals, 0.)
    z = float(solution.eqlin.marginals[0])
    correction = max(0., float(np.max(a.T@y + z - c)))
    upper = float(-b@y - z + correction + 1e-10)
    if not math.isfinite(upper):
        raise ValueError('joint_bound_not_finite')
    return min(min(v.upper for v in intervals), max(independent_joint(intervals).upper, upper))


def price_joint(intervals, rho):
    base = independent_joint(intervals)
    if not math.isfinite(rho) or not 0 <= rho <= 1:
        raise ValueError('invalid correlation stress')
    bounds = tuple(sorted((v.lower, v.upper) for v in intervals))
    upper = _moment_upper(bounds, rho)
    return {'joint': asdict(base), 'stressed_upper': upper,
            'dependence': {'model': 'pairwise_moment_upper_v1', 'leg_count': len(intervals),
                'pairwise_rho_ceiling_assumption': rho,
                'higher_order_dependence': 'unrestricted_within_pairwise_moment_bounds',
                'independence_upper': base.upper, 'reserve_cents': 100*(upper-base.upper),
                'frechet_upper': min(v.upper for v in intervals),
                'calibrated': False}}

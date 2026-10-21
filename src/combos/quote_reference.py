"""Explicit shadow quote reserves, separate from probability uncertainty bounds."""
from dataclasses import dataclass
import math


@dataclass(frozen=True)
class QuoteReference:
    model: str = 'stressed_upper_v1'
    marginal_fraction: float = 1.

    def __post_init__(self):
        if self.model not in ('stressed_upper_v1', 'independent_marginal_reserve_v1'):
            raise ValueError('unknown quote reference model')
        if not math.isfinite(self.marginal_fraction) or not 0 <= self.marginal_fraction <= 1:
            raise ValueError('invalid marginal reserve fraction')
        if self.model == 'stressed_upper_v1' and self.marginal_fraction != 1:
            raise ValueError('unused marginal fraction for stressed reference')

    def manifest(self):
        return {'model': self.model, 'marginal_fraction': self.marginal_fraction}

    def evaluate(self, pricing):
        point = pricing['joint']['point']
        stress = pricing['stressed_upper']
        if not all(math.isfinite(v) for v in (point, stress)) or not 0 <= point <= stress <= 1:
            raise ValueError('invalid quote reference bounds')
        reference = stress
        assumption = 'reported_stressed_upper'
        if self.model == 'independent_marginal_reserve_v1':
            # Do not reinterpret an arbitrary joint model's upper as independence.
            dependence = pricing.get('dependence', {})
            if dependence.get('model') != 'pairwise_moment_upper_v1':
                raise ValueError('marginal reference requires explicit independence benchmark')
            upper = dependence['independence_upper']
            if not math.isfinite(upper) or not point <= upper <= stress:
                raise ValueError('invalid independent marginal upper')
            reference = point + self.marginal_fraction * (upper - point)
            assumption = 'independent_legs_with_fractional_marginal_reserve'
        return {**self.manifest(), 'value': reference, 'point': point,
                'stressed_upper': stress, 'reserve_per_share': reference-point,
                'uncovered_stress_per_share': stress-reference,
                'assumption': assumption, 'calibrated': False}


def reference_from_config(config):
    return QuoteReference(**config.get('quote_reference', {}))

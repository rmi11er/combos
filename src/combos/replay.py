"""Same-cohort price comparisons, with causal snapshots and no fill assumptions."""
from dataclasses import asdict, replace
import math
from .observations import VENUES
from .pricing import Interval
from .joint_pricing import independent_joint
from .weighted_fair import weighted_fair, WeightPolicy


def complement(interval, side):
    if side == 'yes': return interval
    if side == 'no': return Interval(1-interval.upper, 1-interval.point, 1-interval.lower)
    raise ValueError('invalid selected side')


def replay_decision(store, decision, policy=WeightPolicy()):
    result = {'decision_id': decision['decision_id'], 'decision_at': decision['decision_at'],
              'status': 'excluded'}
    try:
        at = float(decision['decision_at'])
        if not math.isfinite(at): raise ValueError('invalid decision timestamp')
        legs = decision['legs']
        if not 2 <= len(legs) <= 4: raise ValueError('requires two through four legs')
        if any(not leg.get('fixture_key') for leg in legs): raise ValueError('missing reviewed fixture mapping')
        if len({l['fixture_key'] for l in legs}) != len(legs):
            raise ValueError('same-fixture joint model required')
        reference = float(decision['reference_yes_price'])
        if not 0 <= reference <= 1: raise ValueError('invalid reference price')
        kind = decision['reference_kind']
        if kind not in ('combo_book_midpoint', 'trade_price', 'hypothetical_quote'):
            raise ValueError('explicit reference kind required')
        models = {v: [] for v in (*VENUES, 'equal_weight', 'spread_depth_weight')}
        details = []
        result['leg_details'] = details
        for leg in legs:
            policy.check_pregame(leg.get('start_at'), at, leg.get('phase', decision.get('phase')))
            observations = [store.latest(leg['market_key'], v, at,
                policy.pinnacle_delay_seconds if policy.delayed_pinnacle and v == 'pinnacle' else 0.) for v in VENUES]
            if policy.delayed_pinnacle:
                observations = [replace(o, available_at=max(o.available_at,o.observed_at+policy.pinnacle_delay_seconds))
                                if o.venue == 'pinnacle' else o for o in observations]
            fair = weighted_fair(observations, at, leg.get('phase', decision.get('phase')), policy)
            details.append(fair)
            if not fair['guard']['quote_allowed']:raise ValueError('venue_disagreement_hard')
            side = leg['side']
            for o in observations: models[o.venue].append(o.selected_interval(side))
            equal = Interval(*(sum(getattr(o.interval, k) for o in observations)/3
                               for k in ('lower', 'point', 'upper')))
            models['equal_weight'].append(complement(equal, side))
            models['spread_depth_weight'].append(complement(Interval(**fair['fair']), side))
        prices = {}
        for name, values in models.items():
            joint = independent_joint(values)
            prices[name] = {'joint': asdict(joint),
                'reference_minus_fair_cents': 100*(reference-joint.point),
                'reference_minus_upper_cents': 100*(reference-joint.upper)}
        result.update(status='priced', reference_kind=kind, reference_yes_price=reference,
                      comparisons=prices, leg_details=details,
                      assumption='cross-fixture independence; price gaps before combo execution fees; no fill model')
    except (ValueError, KeyError, TypeError) as exc:
        result['reason'] = str(exc)
    return result

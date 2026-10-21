"""Filled-inventory hedge selection. Nominal independent-fixture risk model.

These are pricing permissions, not cash offsets or a calibrated VaR estimate.
Opposing full-game moneylines use a 1% fractional-tie sensitivity assumption.
"""
from collections import defaultdict
import json
import math
from .payoff_risk import canonical_leg_risk
from .pricing import short_yes_economics
from .risk import units


def probability(legs, probs):
    return math.prod(probs[k] if s == 1 else 1-probs[k] for _, k, s, _ in legs)


def second(legs, probs):
    return math.prod((probs[k] if s == 1 else 1-probs[k]) -
                     (min(.01, 2*probs[k], 2*(1-probs[k]))/4 if ml else 0)
                     for _, k, s, ml in legs)


def intersection(a, b, probs):
    grouped = defaultdict(list)
    for leg in (*a, *b): grouped[leg[0]].append(leg)
    bounds = []
    for legs in grouped.values():
        ps = [probs[k] if s == 1 else 1-probs[k] for _, k, s, _ in legs]
        if len(legs) == 1: value = ps[0]
        elif legs[0][1] == legs[1][1]:
            p = probs[legs[0][1]]
            tie = min(.01, 2*p, 2*(1-p))/4 if legs[0][3] else 0
            value = tie if legs[0][2] != legs[1][2] else ps[0]-tie
        else: value = min(ps)  # Unknown same-fixture joint: upper covariance bound.
        bounds.append(value)
    return math.prod(bounds)


def variance_delta(legs, quantity, positions, probs):
    p = probability(legs, probs)
    covariance = sum(n*(intersection(legs, old, probs)-p*probability(old, probs))
                     for old, n in positions)
    return quantity**2*(second(legs, probs)-p*p)+2*quantity*covariance


def describe(pricing):
    legs, probs = [], {}
    for d in pricing['legs']:
        m = d['mapping']; r = canonical_leg_risk(m, d['selected_side'])
        selected = d['fair']['point'] if d['selected_side'] == 'yes' else 1-d['fair']['point']
        probs[r['key']] = selected if r['selected_sign'] == 1 else 1-selected
        legs.append((m['fixture_key'], r['key'], r['selected_sign'],
                     m.get('market_type') == 'moneyline' and m.get('period', 'full_game') == 'full_game'))
    if len({l[0] for l in legs}) != len(legs): raise ValueError('inventory_same_fixture')
    if any(not math.isfinite(p) or not 0 <= p <= 1 for p in probs.values()):
        raise ValueError('inventory_invalid_probability')
    return legs, probs


def validate(config):
    policy = config.get('inventory_fitting') or {}
    if not policy.get('enabled'): return
    if config.get('mode') != 'shadow': raise ValueError('inventory_fitting_shadow_only')
    offset = config.get('moneyline_offset') or {}
    if not (offset.get('enabled') and offset.get('net_contract_and_fixture_risk_buckets') and
            offset.get('eligible_scope') == 'exact_full_game_moneyline_distinct_fixture_team_match'):
        raise ValueError('inventory_fitting_requires_reviewed_moneyline_offsets')
    floor = float(policy['minimum_net_edge_per_share'])
    trigger = float(policy['fixture_pressure_trigger'])
    if not math.isfinite(floor) or not 0 < floor < config['minimum_net_edge_per_share']:
        raise ValueError('invalid_inventory_edge_floor')
    if not math.isfinite(trigger) or not 0 < trigger <= 1:
        raise ValueError('invalid_inventory_pressure_trigger')


def evaluate(engine, pricing, quantity, ask, rate, at):
    """Fail closed for discounts, including when *any* held position is stale."""
    policy = engine.config.get('inventory_fitting') or {}
    answer = {'eligible': False, 'model': 'independent_fixtures_same_fixture_covariance_upper_bound',
              'inventory_basis': 'simulated_filled_only', 'tie_probability_assumption': .01}
    try:
        if not policy.get('enabled'): raise ValueError('disabled')
        if not math.isfinite(quantity) or quantity <= 0: raise ValueError('inventory_invalid_quantity')
        legs, candidate_probs = describe(pricing)
        if not all(l[3] for l in legs): raise ValueError('not_full_game_moneyline')
        cap = engine.config['per_fixture_dollars']*pricing['risk_multiplier']
        focus = {f: engine.risk.bucket_state('fixture:'+f, held_only=True) for f, _, _, _ in legs}
        focus = {f: s for f, s in focus.items() if s['risk_dollars'] >= cap*policy['fixture_pressure_trigger']}
        if not focus: raise ValueError('no_pressured_filled_fixture')
        positions, probs = [], {}
        for row in engine.db.execute("SELECT context FROM reservations WHERE status='simulated_filled'"):
            c = json.loads(row['context'])
            fresh = engine.fair(c['legs'], at)
            if not fresh['quote_allowed']: raise ValueError('held_inventory_unpriceable')
            old, old_probs = describe(fresh)
            # Canonical complements must agree; do not silently choose the
            # last quote's probability when feeds have materially diverged.
            for key, p in old_probs.items():
                if key in probs and abs(probs[key]-p) > .01: raise ValueError('held_probability_disagreement')
                probs[key] = p
            n=float(c['quantity'])
            if not math.isfinite(n) or n<=0:raise ValueError('held_inventory_invalid_quantity')
            positions.append((old, n))
        for key, p in candidate_probs.items():
            if key in probs and abs(probs[key]-p) > .01: raise ValueError('candidate_probability_disagreement')
            probs[key] = p
        delta = variance_delta(legs, quantity, positions, probs)
        if not math.isfinite(delta): raise ValueError('inventory_nonfinite_variance')
        answer['variance_delta_dollars_squared'] = delta
        if delta > 1e-9: raise ValueError('variance_not_reduced')
        cost = units(short_yes_economics(quantity, ask, 0, rate)['maximum_loss'])
        premium = max(0, int(round(quantity*10000))-cost)
        improvements = []
        for fixture, _, sign, _ in legs:
            if fixture not in focus: continue
            state = focus[fixture]; side = -sign
            after = (state['gross']+max(0, *(state['sides'][d]+(cost if d == side else 0)-
                     state['credits'][-d]-(premium if -d == side else 0) for d in (-1, 1))))/10000
            before_delta = sum(-n*s*probability([l for l in old if l[0] != fixture], probs)
                               for old, n in positions for f, _, s, _ in old if f == fixture)
            after_delta = before_delta-quantity*sign*probability([l for l in legs if l[0] != fixture], probs)
            if after < state['risk_dollars']-1e-9 and abs(after_delta) < abs(before_delta)-1e-9:
                improvements.append({'fixture': fixture, 'risk_before_dollars': state['risk_dollars'],
                    'risk_after_dollars': after, 'conditional_delta_before': before_delta,
                    'conditional_delta_after': after_delta})
        answer['fixture_improvements'] = improvements
        if not improvements: raise ValueError('pressured_fixture_not_reduced')
        answer.update(eligible=True, reason='filled_inventory_hedge',
                      minimum_net_edge_per_share=policy['minimum_net_edge_per_share'])
    except (KeyError, TypeError, ValueError) as exc:
        answer['reason'] = str(exc)
    return answer

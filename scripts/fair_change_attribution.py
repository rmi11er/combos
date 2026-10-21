"""Algebraic price/weight attribution; not a causal sharpness or toxicity estimate."""
import itertools
import math


def weight_drivers(before, after):
    """Describe changed score inputs; correlated changes are not causal effects."""
    fields = ('two_sided_depth_payout_dollars', 'fee_expanded_spread_cents',
              'freshness', 'score_multiplier', 'score', 'weight')
    rows = []
    for a, b in zip(before['legs'], after['legs']):
        split_leg(a, b)
        for venue in a['venue_components']:
            x, y = a['venue_components'][venue], b['venue_components'][venue]
            changed = [field for field in fields
                       if not math.isclose(x[field], y[field], rel_tol=1e-10, abs_tol=1e-12)]
            rows.append({'market_key': a['market_key'], 'side': a['side'], 'venue': venue,
                         'changed_fields': changed,
                         'before': {field: x[field] for field in fields},
                         'after': {field: y[field] for field in fields},
                         'source_reference_changed': x['source_reference'] != y['source_reference']})
    return rows


def split_leg(before,after):
    if (before['market_key'],before['side'])!=(after['market_key'],after['side']):
        raise ValueError('leg identity differs')
    a=before['venue_components'];b=after['venue_components']
    if set(a)!=set(b):raise ValueError('source universe differs')
    for leg,values in ((before,a),(after,b)):
        if any(not math.isfinite(v[k]) or not 0<=v[k]<=1 for v in values.values() for k in ('weight','selected_point')):
            raise ValueError('invalid source probability or weight')
        if not math.isclose(sum(v['weight'] for v in values.values()),1,abs_tol=1e-10):raise ValueError('weights do not sum to one')
        if not math.isclose(sum(v['weight']*v['selected_point'] for v in values.values()),leg['selected_point'],abs_tol=1e-10):raise ValueError('leg blend does not reconcile')
    price=sum(.5*(a[v]['weight']+b[v]['weight'])*(b[v]['selected_point']-a[v]['selected_point']) for v in a)
    weight=sum(.5*(a[v]['selected_point']+b[v]['selected_point'])*(b[v]['weight']-a[v]['weight']) for v in a)
    assert math.isclose(price+weight,after['selected_point']-before['selected_point'],abs_tol=1e-10)
    return price,weight


def decompose(before,after):
    a=before['legs'];b=after['legs'];n=len(a)
    if n!=len(b) or not 2<=n<=4:raise ValueError('matched 2–4 legs required')
    parts=[split_leg(x,y) for x,y in zip(a,b)];multipliers=[0.]*n
    for order in itertools.permutations(range(n)):
        changed=set()
        for i in order:
            multipliers[i]+=math.prod((b[j] if j in changed else a[j])['selected_point'] for j in range(n) if j!=i)
            changed.add(i)
    multipliers=[v/math.factorial(n) for v in multipliers]
    price=100*sum(m*p[0] for m,p in zip(multipliers,parts));weight=100*sum(m*p[1] for m,p in zip(multipliers,parts))
    total=100*(math.prod(l['selected_point'] for l in b)-math.prod(l['selected_point'] for l in a))
    assert math.isclose(price+weight,total,abs_tol=1e-9)
    return {'price_component_cents':price,'weight_component_cents':weight,'total_change_cents':total,
            'identity_residual_cents':total-price-weight}

"""Transparent, parameterized combo edge charge for shadow research."""
import math


DEFAULT_POLICY={
    'base_edge_per_combo': 0.003,
    'disagreement_soft_cents': 2.0,
    'disagreement_slope_per_cent': 0.0005,
    'thin_depth_dollars': 1000.0,
    'thin_depth_slope': 0.001,
    'stale_padding_cents': 0.5,
    'stale_padding_slope': 0.00025,
    'maximum_edge_per_combo': 0.01,
}


def charge(scenario, policy=None):
    """Return edge charge and additive components; does not price or submit."""
    p={**DEFAULT_POLICY,**(policy or {})}
    if any(not isinstance(v,(int,float)) or isinstance(v,bool) or not math.isfinite(v) for v in p.values()):
        raise ValueError('dynamic edge parameters must be finite numbers')
    if not 0<=p['base_edge_per_combo']<=p['maximum_edge_per_combo'] or p['maximum_edge_per_combo']<=0:
        raise ValueError('invalid dynamic edge bounds')
    legs=scenario.get('legs')
    if not isinstance(legs,list) or not legs:raise ValueError('scenario legs required')
    gaps=[];depths=[];paddings=[]
    for leg in legs:
        guard=leg.get('pricing_guard',{})
        gaps.append(float(guard.get('maximum_interval_gap_cents',0)))
        paddings.append(float(guard.get('padding_cents',0)))
        for details in leg.get('venue_components',{}).values():
            if 'two_sided_depth_payout_dollars' in details:depths.append(float(details['two_sided_depth_payout_dollars']))
    if any(not math.isfinite(v) or v<0 for v in gaps+paddings+depths):raise ValueError('invalid scenario liquidity evidence')
    gap=max(gaps,default=0);depth=min(depths,default=p['thin_depth_dollars'])
    disagreement=max(0.,gap-p['disagreement_soft_cents'])*p['disagreement_slope_per_cent']
    thin=max(0.,(p['thin_depth_dollars']-depth)/p['thin_depth_dollars'])*p['thin_depth_slope'] if p['thin_depth_dollars'] else 0
    stale=max(0.,max(paddings,default=0)-p['stale_padding_cents'])*p['stale_padding_slope']
    total=min(p['maximum_edge_per_combo'],p['base_edge_per_combo']+disagreement+thin+stale)
    return {'edge_per_combo':total,'base':p['base_edge_per_combo'],
            'disagreement_component':disagreement,'thin_depth_component':thin,
            'stale_padding_component':stale,'maximum_interval_gap_cents':gap,
            'minimum_two_sided_depth_dollars':depth,'policy':p,
            'model':'dynamic_edge_shadow_v1'}

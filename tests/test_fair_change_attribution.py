import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from fair_change_attribution import decompose
import pytest


def scenario(prices,weights):
    return {'legs':[{'market_key':str(i),'side':'yes','selected_point':sum(p*w for p,w in zip(ps,ws)),
        'venue_components':{str(v):{'selected_point':p,'weight':w} for v,(p,w) in enumerate(zip(ps,ws))}}
        for i,(ps,ws) in enumerate(zip(prices,weights))]}


def test_weight_change_is_not_mistaken_for_venue_price_move():
    a=scenario([[.4,.6],[.3,.7]],[[.5,.5],[.5,.5]])
    b=scenario([[.4,.6],[.3,.7]],[[.2,.8],[.5,.5]])
    r=decompose(a,b);assert r['price_component_cents']==0
    assert r['weight_component_cents']==pytest.approx(3)


def test_mixed_changes_reconcile_and_reverse():
    a=scenario([[.4,.6],[.3,.7],[.6,.8]],[[.5,.5],[.5,.5],[.8,.2]])
    b=scenario([[.42,.59],[.32,.68],[.59,.82]],[[.2,.8],[.6,.4],[.5,.5]])
    r=decompose(a,b);reverse=decompose(b,a)
    assert abs(r['identity_residual_cents'])<1e-10
    for key in ('price_component_cents','weight_component_cents','total_change_cents'):
        assert r[key]==pytest.approx(-reverse[key])


def test_weight_driver_inputs_distinguish_refresh_from_liquidity():
    from copy import deepcopy
    from fair_change_attribution import weight_drivers
    a=scenario([[.4,.6],[.3,.7]],[[.5,.5],[.5,.5]])
    for leg in a['legs']:
        for v in leg['venue_components'].values():
            v.update(two_sided_depth_payout_dollars=100,fee_expanded_spread_cents=2,
                     freshness=.8,score_multiplier=1,score=4,source_reference='old')
    b=deepcopy(a)
    b['legs'][0]['venue_components']['0'].update(freshness=.9,score=4.5,source_reference='new')
    b['legs'][1]['venue_components']['1'].update(two_sided_depth_payout_dollars=400,score=8)
    rows=weight_drivers(a,b)
    assert rows[0]['changed_fields']==['freshness','score']
    assert rows[0]['source_reference_changed']
    assert rows[3]['changed_fields']==['two_sided_depth_payout_dollars','score']

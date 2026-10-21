import sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from consensus_price_screen import screen_leg

POLICY={'maximum_anchor_venue_weight':.75,'anchor_agreement_cents':.75,
        'minimum_kalshi_disagreement_cents':.5,'maximum_kalshi_disagreement_cents':3}


@pytest.mark.parametrize('points,passes', [([.52,.50,.501],True),([.48,.50,.501],True),
    ([.505,.50,.51],False),([.55,.50,.501],False),([.501,.50,.502],False)])
def test_direction_and_agreement_geometry(points,passes):
    leg={'market_key':'m','side':'yes','selected_point':sum(points)/3,'venue_components':{
        v:{'selected_point':p,'score':1} for v,p in zip(('kalshi','polymarket','pinnacle'),points)}}
    r=screen_leg(leg,POLICY)
    assert r['price_screen_passes']==passes
    assert not r['consensus_model_activated']
    for v in leg['venue_components'].values():v['selected_point']=1-v['selected_point']
    leg['side']='no';opposite=screen_leg(leg,POLICY)
    assert opposite['price_screen_passes']==passes
    assert opposite['kalshi_minus_anchor_cents']==pytest.approx(-r['kalshi_minus_anchor_cents'])


def test_combo_sensitivity_respects_inactive_legs_and_product():
    from consensus_price_screen import combo_lean_sensitivity
    legs=[{'baseline_selected_point':.5,'anchor_selected_point':.6,'price_screen_passes':True},
          {'baseline_selected_point':.4,'anchor_selected_point':.9,'price_screen_passes':False}]
    result=combo_lean_sensitivity(legs,.25)
    assert result['baseline_combo_point']==pytest.approx(.2)
    assert result['alternative_combo_point']==pytest.approx(.21)
    assert result['fair_change_cents']==pytest.approx(1)
    assert not result['quotes_or_fills_simulated']

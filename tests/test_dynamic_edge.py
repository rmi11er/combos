import pytest
from combos.dynamic_edge import charge


def scenario(gap=0,depth=5000,padding=.5):
    return {'legs':[{'pricing_guard':{'maximum_interval_gap_cents':gap,'padding_cents':padding},
        'venue_components':{'kalshi':{'two_sided_depth_payout_dollars':depth},
                             'polymarket':{'two_sided_depth_payout_dollars':depth},
                             'pinnacle':{'two_sided_depth_payout_dollars':depth}}}]}


def test_base_and_components_are_explicit():
    r=charge(scenario());assert r['edge_per_combo']==.003;assert r['disagreement_component']==0
    r=charge(scenario(gap=5,depth=100));assert r['edge_per_combo']>.003
    assert r['edge_per_combo']<=.01 and r['model']=='dynamic_edge_shadow_v1'


def test_dynamic_charge_does_not_depend_on_last_price_change():
    a=charge(scenario(gap=0,depth=5000));b=charge(scenario(gap=0,depth=5000,padding=.5));assert a==b


def test_invalid_evidence_rejected():
    s=scenario();s['legs'][0]['venue_components']['kalshi']['two_sided_depth_payout_dollars']=-1
    with pytest.raises(ValueError):charge(s)

import pytest
from combos.pricing_service import PricingService
from combos.weighted_fair import WeightPolicy
from combos.joint_pricing import price_joint
from combos.pricing import Interval
from test_exchange_fallback import setup
from test_runtime import rfq

def test_tail_filter_remains_rejection_not_added_quote_edge():
    config,state=setup(['kalshi'])
    config['correlation_tail']={'enabled':True,'reject_reserve_cents':.001}
    result=PricingService(state,config,WeightPolicy(delayed_pinnacle=True)).price(rfq()['mve_selected_legs'],100)
    assert not result['quote_allowed']
    assert result['block_reason']=='correlation_tail_reserve'
    assert result['extra_edge_per_share']==0
    config['correlation_tail']['enabled']=False
    control=PricingService(state,config,WeightPolicy(delayed_pinnacle=True)).price(rfq()['mve_selected_legs'],100)
    assert control['quote_allowed']
    assert control['joint']==result['joint']
    assert control['extra_edge_per_share']==0

def test_zero_pairwise_correlation_does_not_mean_joint_independence():
    result=price_joint([Interval(.5,.5,.5)]*3,0)
    assert result['joint']['point']==.125
    assert result['stressed_upper']==pytest.approx(.25)

def test_two_source_caps_force_eighty_twenty_despite_depth_change():
    config,state=setup(['kalshi','pinnacle'])
    pricer=PricingService(state,config,WeightPolicy(delayed_pinnacle=True))
    first=pricer.price(rfq()['mve_selected_legs'],100)
    for row in state.rows.values():
        if row['venue']=='kalshi':
            row['yes_bid_size']*=1000;row['yes_ask_size']*=1000
    second=pricer.price(rfq()['mve_selected_legs'],100)
    for result in (first,second):
        for leg in result['legs']:
            assert leg['venues']['kalshi']['weight']==pytest.approx(.8)
            assert leg['venues']['pinnacle']['weight']==pytest.approx(.2)

"""Replacement models/signals must change quotes through the same risk path."""
from dataclasses import dataclass
import pytest
from test_runtime import config,rfq,seed,add,drain,decisions
from combos.event_store import EventStore
from combos.creator_service import CreatorService
from combos.shadow_engine import ShadowEngine
from combos.pricing_service import PricingService, SignalAdjustment, WeightedLegFair
from combos.weighted_fair import WeightPolicy


@dataclass
class Signal:
    adjustment: SignalAdjustment
    def evaluate(self,legs,pricing,at):return self.adjustment
    def manifest(self):return {'model':'test_signal','adjustment':self.adjustment.__dict__}


def run(tmp_path,adjustment):
    store=EventStore(tmp_path/'bus.sqlite');c=config();w=WeightPolicy()
    pricer=PricingService(store,c,w,signals=[Signal(adjustment)])
    engine=ShadowEngine(store,c,w,replay=True,pricing_service=pricer);creators=CreatorService(store)
    seed(store);add(store,'rfq',rfq(),'r',100);drain(creators,engine)
    result=decisions(store)[0];store.close();return result


def test_signal_blocks_without_reservation(tmp_path):
    r=run(tmp_path,SignalAdjustment(quote_allowed=False,reason='news'))
    assert r['reason']=='signal:news' and r['status']=='skipped'
    assert r['pricing']['signals'][0]['adjustment']['reason']=='news'


def test_signal_widens_quote_and_reduces_risk(tmp_path):
    r=run(tmp_path,SignalAdjustment(risk_multiplier=.5,extra_edge_per_share=.03))
    assert r['status']=='shadow_quote'
    assert r['pricing']['risk_multiplier']==.5
    assert r['required_net_edge_per_share']==pytest.approx(.033)
    assert r['economics']['expected_edge']>=r['quantity']*.033-1e-9


@pytest.mark.parametrize('kwargs',[{'risk_multiplier':2},{'risk_multiplier':float('nan')},{'extra_edge_per_share':-.01},{'quote_allowed':1}])
def test_invalid_signal_rejected(kwargs):
    with pytest.raises(ValueError):SignalAdjustment(**kwargs)


def test_model_replacement_and_local_only_lookup(tmp_path,monkeypatch):
    from combos.pricing_service import PairwiseMomentJoint
    class CustomFair(WeightedLegFair):
        def price(self,observations,at,phase):
            result=super().price(observations,at,phase)
            result['fair']={'lower':.3,'point':.35,'upper':.4};return result
        def manifest(self):return {'model':'custom_fair_v1'}
    class CustomJoint:
        def price(self,intervals):return {'joint':{'lower':.09,'point':.1225,'upper':.16},'stressed_upper':.2}
        def manifest(self):return {'model':'custom_joint_v1'}
    store=EventStore(tmp_path/'bus.sqlite');c=config();w=WeightPolicy()
    p=PricingService(store,c,w,leg_model=CustomFair(w),joint_model=CustomJoint())
    engine=ShadowEngine(store,c,w,replay=True,pricing_service=p);seed(store)
    drain(CreatorService(store),engine)
    import requests
    def no_http(*a,**k):raise AssertionError('network on RFQ path')
    monkeypatch.setattr(requests.sessions.Session,'request',no_http)
    result=engine.fair(rfq()['mve_selected_legs'],100)
    assert result['joint']['point']==.1225 and result['stressed_upper']==.2
    assert result['components']['leg_model']['model']=='custom_fair_v1'
    store.close()

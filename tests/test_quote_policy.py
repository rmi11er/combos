from dataclasses import replace
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from combos.quote_policy import (AcceptanceEstimate, FairSignal, MakerFeeTerms,
                                QuotePolicy, QuoteRequest, Reserve, ShadowQuoteAudit)


def request(**overrides):
    args = dict(decision_id='test-rfq', decision_at=100., quantity=10.,
                fair=FairSignal(.2,99.,'test:fair'),
                reserves=tuple(Reserve(k,0.,99.,'test:zero') for k in ('uncertainty','dependence','adverse_selection','inventory')),
                fees=MakerFeeTerms(0.,90.,'test:fee','.0001',200.),
                price_ranges=({'start':0,'end':1,'step':.01},),
                minimum_profit_per_contract=.005,
                policy_reference='test:policy',policy_available_at=90.)
    args.update(overrides)
    return QuoteRequest(**args)


def test_exact_cash_rounding_changes_tiny_order_floor():
    req = request(quantity=.01, fair=FairSignal(.5,99,'test:fair'),
                  minimum_profit_per_contract=.003,
                  price_ranges=({'start':0,'end':1,'step':.0001},))
    result = QuotePolicy().evaluate(req)
    # Buying NO at .4999 pays .005 after account cash alignment, leaving no
    # profit. .4900 is the first NO bid with enough cash profit for this size.
    assert result['floor']['yes_ask'] == .51
    assert result['floor']['no_bid'] == .49
    assert result['floor']['margin_after_reserves_and_fee'] == pytest.approx(.0001)
    assert result['selected'] is None


def test_quote_uses_native_no_grid_and_complement():
    req = request(fair=FairSignal(.45,99,'test:fair'),
                  price_ranges=({'start':.1,'end':.5,'step':.1},))
    floor = QuotePolicy().evaluate(req)['floor']
    assert floor['yes_ask'] == .6
    assert floor['quote'] == {'yes_bid':'0.0000','no_bid':'0.4000'}


def test_components_keep_reserves_fees_and_commercial_markup_separate():
    reserves = tuple(Reserve(k,p,99,'test:reserve') for k,p in
        zip(('uncertainty','dependence','adverse_selection','inventory'),(.01,.02,.03,.04)))
    result = QuotePolicy().evaluate(request(reserves=reserves), (0,.02))
    floor, marked = result['candidates']
    assert floor['yes_ask'] == .31 and marked['yes_ask'] == .33
    assert sum(floor['reserve_dollars'].values()) == pytest.approx(1.)
    assert floor['required_minimum_profit'] == .05
    assert floor['maker_fee'] == 0
    assert floor['floor_surplus_after_minimum_profit'] == pytest.approx(.05)
    assert marked['commercial_markup_above_floor_per_contract'] == .02
    assert result['selected'] is None and result['selection_status'] == 'acceptance_model_unavailable'


class Model:
    """Synthetic test fixture only, never a fitted or production acceptance model."""
    def __init__(self, **overrides):self.overrides = overrides
    def manifest(self):return {'model_version':'test:model', 'calibration_reference':'test:calibration'}
    def predict(self, req, candidate):
        price = candidate['yes_ask']
        return AcceptanceEstimate(candidate_id=candidate['candidate_id'],
            acceptance_probability={.21:.5,.22:.9,.23:.1}.get(price,.1),
            conditional_yes_probability=.2,available_at=99,training_data_available_at=90,
            calibrated=True,model_version='test:model',calibration_reference='test:calibration',
            conditional_outcome_calibration_reference='test:conditional_calibration',
            scope_reference='test:exact-rfq-scope',**self.overrides)


def test_calibrated_joint_acceptance_and_conditional_outcome_selects_profit():
    result = QuotePolicy().evaluate(request(), (0,.01,.02), Model())
    assert result['selected']['yes_ask'] == .22
    assert result['selected']['expected_incremental_profit'] == pytest.approx(.18)
    assert result['selection_status'] == 'calibrated_expected_profit_selection'


@pytest.mark.parametrize('field,bad', [('fair',FairSignal(.2,101,'test:fair')),
    ('policy_available_at',101), ('fees',MakerFeeTerms(0,101,'test:fee','.0001'))])
def test_future_request_information_rejected(field,bad):
    with pytest.raises(ValueError,match='future_information'):
        QuotePolicy().evaluate(request(**{field:bad}))


@pytest.mark.parametrize('change', [{'calibrated':False}, {'calibrated':1}, {'calibrated':'true'}, {'available_at':101},
    {'training_data_available_at':101}, {'conditional_yes_probability':None},
    {'training_data_available_at':99,'available_at':95},
    {'conditional_outcome_calibration_reference':''}, {'candidate_id':'other-rfq'},
    {'label_unit':'public_trade_price_crossing'}])
def test_invalid_or_future_acceptance_never_optimizes(change):
    class BadModel(Model):
        def predict(self, req, candidate):return replace(super().predict(req,candidate), **change)
    result = QuotePolicy().evaluate(request(), acceptance_model=BadModel())
    assert result['selected'] is None
    assert result['selection_status'] == 'acceptance_inputs_unusable'
    assert result['candidates'][0]['acceptance_rejection_reason']


def test_no_quote_dominates_negative_conditional_profit():
    class AdverseModel(Model):
        def predict(self, req, candidate):return replace(super().predict(req,candidate), conditional_yes_probability=.9)
    result = QuotePolicy().evaluate(request(), acceptance_model=AdverseModel())
    assert result['selected'] is None
    assert result['selection_status'] == 'no_positive_expected_incremental_profit'


def test_expired_fee_and_missing_or_negative_reserves_rejected():
    with pytest.raises(ValueError,match='expired_fee'):
        QuotePolicy().evaluate(request(fees=MakerFeeTerms(0,90,'test:fee','.0001',100)))
    with pytest.raises(ValueError,match='missing_reserve'):
        QuotePolicy().evaluate(request(reserves=()))
    rs = list(request().reserves);rs[0]=replace(rs[0],per_contract=-.1)
    with pytest.raises(ValueError,match='negative_reserve'):
        QuotePolicy().evaluate(request(reserves=tuple(rs)))


def test_shadow_sidecar_logs_without_changing_selected_quote_or_reservation(tmp_path):
    from test_runtime import config,seed,add,rfq,drain,decisions
    from combos.event_store import EventStore
    from combos.creator_service import CreatorService
    from combos.shadow_engine import ShadowEngine
    outputs=[]
    for name,audit in [('original',None),('audit',ShadowQuoteAudit(0,'.0001',0,'test:policy'))]:
        store=EventStore(tmp_path/(name+'.sqlite'))
        engine=ShadowEngine(store,config(),replay=True,quote_policy_audit=audit)
        seed(store);add(store,'kalshi',{'type':'rfq_created','msg':rfq()},'rfq',100)
        drain(CreatorService(store),engine)
        outputs.append(decisions(store)[0]);store.close()
    original,audited=outputs
    assert original['status'] == audited['status'] == 'shadow_quote'
    for key in ('yes_ask','no_bid','quantity','quote','risk','economics'):
        assert original[key] == audited[key]
    assert 'quote_policy_audit' not in original
    assert audited['quote_policy_audit']['selected'] is None
    assert audited['config_version'] != original['config_version']


def test_shadow_audit_failure_does_not_change_quote(tmp_path):
    from test_runtime import config,seed,add,rfq,drain,decisions
    from combos.event_store import EventStore
    from combos.creator_service import CreatorService
    from combos.shadow_engine import ShadowEngine
    class BrokenAudit:
        def manifest(self):return {'component':'test:broken'}
        def evaluate(self,**kwargs):raise RuntimeError('test_sidecar_failure')
    store=EventStore(tmp_path/'broken.sqlite');engine=ShadowEngine(store,config(),replay=True,quote_policy_audit=BrokenAudit())
    seed(store);add(store,'kalshi',{'type':'rfq_created','msg':rfq()},'rfq',100)
    drain(CreatorService(store),engine)
    result=decisions(store)[0]
    assert result['status']=='shadow_quote'
    assert result['quote_policy_audit']['reason']=='test_sidecar_failure'
    store.close()

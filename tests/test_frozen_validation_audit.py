from copy import deepcopy
import pytest
from audit_frozen_august_validation import check_policy


def inputs():
    c = {'entry_basis':'point','entry_filter':'minimum_edge','minimum_net_edge_per_share':.003,
         'minimum_net_edge_unit':'leg_contract'}
    original = {'quantity':10,'yes_price':.26,'maker_fee':.01,'fair_point':.25,'stressed_upper':.4,
                'quote_allowed':True,'source':{'nlegs':4}}
    decision = {**deepcopy(original),'entry_basis':'point','entry_filter':'minimum_edge',
                'minimum_net_edge_unit':'leg_contract','selected_net_edge':10*(.26-.25)-.01,
                'required_net_edge':10*.003*4}
    return original, decision, {'configuration':c,'marginal_reserve_fraction':0}


def test_audit_distinguishes_per_leg_hurdle_and_sell_all():
    original, decision, policy = inputs()
    assert not check_policy(original,decision,policy)
    policy['configuration']['entry_filter'] = decision['entry_filter'] = 'all_priced'
    decision['required_net_edge'] = None
    assert check_policy(original,decision,policy)
    original['quote_allowed'] = decision['quote_allowed'] = False
    assert not check_policy(original,decision,policy)


@pytest.mark.parametrize('field,value',[('maker_fee',0),('required_net_edge',.03),('stressed_upper',.3)])
def test_audit_detects_corrupted_economics_and_policy(field,value):
    original, decision, policy = inputs()
    decision[field] = value
    with pytest.raises(AssertionError):
        check_policy(original,decision,policy)

from combos.creator_service import creator_policy_gate


def test_creator_policy_gate_prices_only_counterfactually_in_shadow():
    blocked = {'status': 'blocked'}
    assert creator_policy_gate(blocked, 'shadow') == {
        'eligible': False, 'counterfactual': True, 'price': True,
    }
    assert creator_policy_gate(blocked, 'live') == {
        'eligible': False, 'counterfactual': False, 'price': False,
    }
    assert creator_policy_gate({'status': 'clear'}, 'live')['price'] is True

import sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).parents[1]/'scripts'))
from corrected_shadow_review import reconstruct

def test_point_quote_omits_reserves_and_recomputes_target_size():
    original=dict(pricing={'joint':{'point':.30},'stressed_upper':.45},
        combo_terms={'maker_fee_rate':0,'price_ranges':[{'start':'0','end':'1','step':'.001'}]},
        request={'target_cost_dollars':'10'},ticket_liability_cap_dollars=250,
        yes_ask=.454,quantity=23)
    q=reconstruct(original,.003)
    assert q['yes_ask']==pytest.approx(.303)
    assert q['quantity']==34
    assert q['economics']['expected_edge']/q['quantity']==pytest.approx(.003)
    assert original['yes_ask']==.454
    assert q['pricing']['stressed_upper']==.45

def test_recomputed_size_stays_under_liability_cap():
    original=dict(pricing={'joint':{'point':.2}},
        combo_terms={'maker_fee_rate':0,'price_ranges':[{'start':'0','end':'1','step':'.001'}]},
        request={'contracts_fp':'10000'},ticket_liability_cap_dollars=250,yes_ask=.4,quantity=416.66)
    q=reconstruct(original,.003)
    assert q['quantity']*(1-q['yes_ask'])<=250
    assert (q['quantity']+.01)*(1-q['yes_ask'])>250

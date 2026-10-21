from copy import deepcopy
import pytest
from audit_marginal_reserve_sweep import check_row


def test_audit_rejects_changed_economics_reserve_and_selection():
    original={'evaluation_id':'a','fair_point':.2,'stressed_upper':.5,'quantity':100,
              'yes_price':.25,'maker_fee':.1,'quote_allowed':True,'source':{'nlegs':2}}
    row={**original,'stressed_upper':.225,'source':{'nlegs':2,'quote_reserve_candidate':{
        'original_joint_upper':.5,'fraction':.25,'independent_marginal_upper':.3}},
        'selected_net_edge':100*(.25-.225)-.1,'required_net_edge':.3,'accepted':True}
    check_row(original,row,(.2,.3),.25,{'minimum_net_edge_per_share':.003},False)
    for key,value in [('quantity',101),('stressed_upper',.21),('accepted',False)]:
        changed=deepcopy(row);changed[key]=value
        with pytest.raises(AssertionError):
            check_row(original,changed,(.2,.3),.25,{'minimum_net_edge_per_share':.003},False)
    with pytest.raises(AssertionError,match='risk_gate'):
        check_row(original,row,(.2,.3),.25,{'minimum_net_edge_per_share':.003},True)

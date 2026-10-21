import pytest
from combos.execution_startup_gate import assess_startup


def summary(cash='10000'):
    return {'atomic_snapshot': True,
        'cash_assessment': {'reported_available_dollars':cash,
            'maximum_initial_strategy_cash_dollars':cash,
            'positive_cash_available':True,'received_at':100},
        'collections': {n:{'pagination_complete':True,'rows':0}
                        for n in ('positions','resting_orders','self_quotes')}}


def test_negative_cash_never_becomes_budget(tmp_path):
    s=summary('-1048.3917');s['cash_assessment'].update(maximum_initial_strategy_cash_dollars='0',positive_cash_available=False)
    r=assess_startup(s,'10000',100,shared_activity_cleared=True,required_mapping_count=1,verified_mapping_count=1)
    assert not r['ready_for_ledger_initialization']
    assert 'nonpositive_available_cash' in r['reasons']
    assert r['maximum_initial_strategy_cash_dollars']=='0.0000' and not r['ledger_mutated']


def test_other_preflight_failures_are_explicit():
    s=summary();s['collections']['resting_orders']['rows']=1
    r=assess_startup(s,'10000',100,required_mapping_count=2,verified_mapping_count=1)
    assert not r['ready_for_ledger_initialization']
    assert {'existing_resting_orders','shared_account_activity_unresolved','production_mappings_incomplete'} <= set(r['reasons'])


def test_all_gates_pass_without_mutation():
    r=assess_startup(summary('12500'),'10000',100,shared_activity_cleared=True,required_mapping_count=4,verified_mapping_count=4)
    assert r['ready_for_ledger_initialization']
    assert r['maximum_initial_strategy_cash_dollars']=='10.0000' or r['maximum_initial_strategy_cash_dollars']=='10000.0000'
    assert r['orders_submitted']==0 and not r['ledger_mutated']


def test_stale_balance_blocks_startup():
    r=assess_startup(summary(), '10000', 200, shared_activity_cleared=True)
    assert not r['ready_for_ledger_initialization'] and 'cash_read_stale' in r['reasons']

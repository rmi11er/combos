from copy import deepcopy
from types import SimpleNamespace
from combos.readiness import readiness


def inputs():
    mapping={'market_key':'a','kalshi_ticker':'KXNFLGAME-X-A','sport':'NFL',
        'fixture_key':'a','market_type':'moneyline','start_at':10000,
        'pinnacle':{'selector_reference':'selector'},
        'fees':{v:{'reference':'fee','valid_until':10000} for v in ('kalshi','polymarket')}}
    second=deepcopy(mapping);second.update(market_key='b',fixture_key='b',kalshi_ticker='KXNFLGAME-Y-B')
    config={'mode':'shadow','sport':'NFL','mappings':[mapping,second],
        'capital_dollars':10000,'per_contract_dollars':100,'per_combo_dollars':100,
        'per_fixture_dollars':250,'combo_terms':{'x':{'fee_reference':'fee','price_ranges':[1],'valid_until':10000}}}
    weights=SimpleNamespace(delayed_pinnacle=True,pregame_cutoff_seconds=60)
    polling={'tournament_ids':[31],'known_used':0,'billing_cycle_start':0,'billing_cycle_end':10000}
    return config,weights,polling


def test_missing_payoff_and_units_cannot_pass_static_readiness(monkeypatch):
    monkeypatch.setenv('ODDSPAPI_API_KEY','test')
    args=inputs()
    result=readiness(*args,100)
    assert not result['shadow_configuration_ready']
    assert result['configuration_eligible_mappings']==0
    assert result['all_mapping_exclusions']=={'pinnacle_payoff_mapping_unreviewed':2,'pinnacle_limit_units_unreviewed':2}
    for m in args[0]['mappings']:
        m['pinnacle'].update(payoff_reference='basis',limit_currency='USD',limit_unit='stake',limit_reference='limits')
    assert readiness(*args,100)['shadow_configuration_ready']
    assert not readiness(*args,100)['live_ready']


def test_first_exclusion_retained_but_all_failures_visible(monkeypatch):
    monkeypatch.setenv('ODDSPAPI_API_KEY','test')
    args=inputs()
    for m in args[0]['mappings']:
        m['pricing_block_reason']='pending_review'
        m['pinnacle']={}
    result=readiness(*args,100)
    assert result['mapping_exclusions']=={'pending_review':2}
    assert result['all_mapping_exclusions']['pinnacle_selector_unreviewed']==2
    assert len(result['mapping_checks'][0]['reasons'])==4

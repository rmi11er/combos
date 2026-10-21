from pathlib import Path
import sys
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from runtime import creator_policy,worker
from combos.weighted_fair import WeightPolicy
from combos.creator_service import CreatorService,DEFAULT_POLICY,creator_state
from combos.event_store import EventStore


def test_legacy_defaults_and_config_not_mutated():
    assert creator_policy({})==DEFAULT_POLICY
    config={'creator_policy':{'minimum_requests':2}}
    assert creator_policy(config)['minimum_requests']==2
    assert config=={'creator_policy':{'minimum_requests':2}}
    assert DEFAULT_POLICY['minimum_requests']==30


@pytest.mark.parametrize('policy',[None,[],{'typo':1},{'minimum_requests':True},
    {'minimum_requests':2.5},{'cooldown_seconds':float('nan')},
    {'window_seconds':float('inf')},{'duplicate_fraction':1.1},{'long_legs':0}])
def test_invalid_policies_fail(policy):
    with pytest.raises(ValueError):creator_policy({'creator_policy':policy})


def test_configured_policy_causal_restart_and_mismatch(tmp_path):
    path=tmp_path/'events.sqlite'
    config={'creator_policy':{'minimum_requests':2,'bursts_before_cooldown':1}}
    store=EventStore(path)
    service=CreatorService(store,creator_policy(config))
    for i in range(3):
        store.append('rfq','fixture',{'id':str(i),'creator_id':'c',
            'mve_selected_legs':[{'market_ticker':'test','side':'yes'}]},str(i),100+i)
    while service.step():pass
    assert creator_state(store,'c',2,102)['status']=='clear'
    assert creator_state(store,'c',3,102)['status']=='cooldown'
    cursor=store.cursor(service.name)
    store.close()
    store=EventStore(path)
    service=CreatorService(store,creator_policy(config))
    assert service.step()==0 and store.cursor(service.name)==cursor
    with pytest.raises(ValueError,match='configuration differs'):
        CreatorService(store,creator_policy({}))
    store.close()


def test_worker_uses_manifest_policy(tmp_path):
    path=tmp_path/'worker.sqlite'
    config={'creator_policy':{'minimum_requests':2,'bursts_before_cooldown':1}}
    weights=WeightPolicy()
    store=EventStore(path)
    store.put('runtime','manifest',{'config':config,'weights':weights.__dict__,'code_sha256':{}})
    for i in range(3):
        store.append('rfq','fixture',{'id':str(i),'creator_id':'c',
            'mve_selected_legs':[{'market_ticker':'test','side':'yes'}]},str(i),100+i)
    store.close()
    worker(path,'creators',config,weights,10,drain=True)
    store=EventStore(path)
    assert creator_state(store,'c',3,102)['status']=='cooldown'
    store.close()

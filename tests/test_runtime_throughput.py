"""Consumer optimizations preserve causal state and transactional recovery."""
import importlib.util
from pathlib import Path
import sys
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
sys.path.insert(0,str(ROOT/'tests'))
from test_runtime import config,rfq,seed,add,drain,decisions
from combos.event_store import EventStore
from combos.creator_service import CreatorService
from combos.shadow_engine import ShadowEngine
spec=importlib.util.spec_from_file_location('throughput_benchmark',ROOT/'scripts/runtime_throughput_benchmark.py')
benchmark=importlib.util.module_from_spec(spec);spec.loader.exec_module(benchmark)


def test_selective_payload_read_preserves_envelopes_and_full_archive(tmp_path):
    store=EventStore(tmp_path/'events.sqlite')
    add(store,'external_raw',{'big':'payload'},'raw',101)
    add(store,'rfq',rfq(),'rfq',102)
    full=store.read();filtered=store.read(payload_kinds={'rfq'})
    assert [{k:v for k,v in e.items() if k!='payload'} for e in full]==[{k:v for k,v in e.items() if k!='payload'} for e in filtered]
    assert filtered[0]['payload']=={} and filtered[1]['payload']==full[1]['payload']
    assert store.read()==full
    store.close()


def test_legacy_equivalence_for_expiration_markouts_creator_policy_and_clock(tmp_path):
    fingerprints=[]
    for legacy in (True,False):
        store=EventStore(tmp_path/f'{legacy}.sqlite');c=config()
        c['quote_lifetime_seconds']=2;c['markout_horizons_seconds']=[1,2]
        creator=(benchmark.LegacyCreator if legacy else CreatorService)(store)
        shadow=(benchmark.LegacyShadow if legacy else ShadowEngine)(store,c,replay=True)
        seed(store)
        add(store,'rfq',rfq(),'first',100)
        # Irrelevant payload still triggers the exact expiration event/time.
        add(store,'external_raw',{'large':'not used'},'raw',103)
        add(store,'heartbeat',{},'heart',103)
        add(store,'rfq',rfq('second'),'second',103)
        add(store,'creator_override',{'creator_id':'c1','status':'blocked','reason':'manual_evidence','evidence':{'source':'test'}},'override',104)
        add(store,'rfq',rfq('third'),'third',104)
        add(store,'heartbeat',{},'tail',110)
        drain(creator,shadow)
        assert decisions(store)[-1]['reason']=='creator_blocked'
        transitions=[e for e in store.read(0,100) if e['kind']=='risk_transition']
        assert any(e['payload']['new_status']=='expired' and e['payload']['source_seq']==8 for e in transitions)
        fingerprints.append(benchmark.fingerprint(store));store.close()
    assert fingerprints[0]==fingerprints[1]


def test_batch_rollback_and_restart_rebuilds_due_caches(tmp_path,monkeypatch):
    store=EventStore(tmp_path/'events.sqlite');creator=CreatorService(store);shadow=ShadowEngine(store,config(),replay=True)
    seed(store);add(store,'rfq',rfq(),'rfq',100);creator.step()
    checkpoint=store.checkpoint
    def fail(name,seq):
        checkpoint(name,seq)
        if name=='shadow':raise RuntimeError('interrupted commit')
    monkeypatch.setattr(store,'checkpoint',fail)
    with pytest.raises(RuntimeError,match='interrupted'):shadow.step()
    assert store.cursor('shadow')==0
    assert store.db.execute('SELECT COUNT(*) FROM reservations').fetchone()[0]==0
    assert store.db.execute('SELECT COUNT(*) FROM decisions').fetchone()[0]==0
    assert store.get('shadow','clock') is None
    monkeypatch.setattr(store,'checkpoint',checkpoint)
    drain(creator,shadow)
    assert len(decisions(store))==1 and decisions(store)[0]['status']=='shadow_quote'
    store.close()


def test_creator_barrier_does_not_checkpoint_unprocessed_rfq(tmp_path):
    store=EventStore(tmp_path/'events.sqlite');creator=CreatorService(store);shadow=ShadowEngine(store,config(),replay=True)
    seed(store);add(store,'rfq',rfq(),'rfq',100)
    assert shadow.step()==6 and store.cursor('shadow')==6
    assert not decisions(store)
    creator.step();shadow.step()
    assert len(decisions(store))==1
    store.close()

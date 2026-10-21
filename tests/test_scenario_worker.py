import json
import pytest
from combos.event_store import EventStore
from combos.scenario_worker import ScenarioWorker

class Consumer:
    def __init__(self):self.seen=[]
    def consume(self,e,evaluation_at=None,price_rfqs=True):
        self.seen.append(e['seq'])
        return {'source_seq':e['seq'],'rfq_id':'r','status':'scenario_priced','at':evaluation_at} if e['kind']=='rfq' and price_rfqs else None


def test_restart_no_duplicates_and_decision_clock(tmp_path):
    s=EventStore(tmp_path/'input');s.append('rfq','test',{'id':'r'},'r',100)
    w=ScenarioWorker(s,str(tmp_path/'output'),Consumer(),{'version':1});assert w.step(clock=lambda:101)==1;w.close()
    consumer=Consumer();w=ScenarioWorker(s,str(tmp_path/'output'),consumer,{'version':1})
    assert consumer.seen==[1] and w.step(clock=lambda:101)==0
    row=json.loads(w.db.execute('select result from candidate_decisions').fetchone()[0]);assert row['pricing']['at']==101 and not row['live_authorized']
    w.close();s.close()


def test_old_rfq_recorded_as_lag_exclusion(tmp_path):
    s=EventStore(tmp_path/'input');s.append('rfq','test',{'id':'r'},'r',100)
    w=ScenarioWorker(s,str(tmp_path/'output'),Consumer(),{})
    w.step(clock=lambda:103);r=json.loads(w.db.execute('select result from candidate_decisions').fetchone()[0]);assert r['pricing']['reason']=='processing_lag_or_future_receipt'
    w.close();s.close()


def test_rollback_requires_reconstruction(tmp_path):
    s=EventStore(tmp_path/'input');s.append('rfq','test',{'id':'r'},'r',100)
    class Broken(Consumer):
        def consume(self,*a,**kw):raise RuntimeError('failure')
    w=ScenarioWorker(s,str(tmp_path/'output'),Broken(),{})
    with pytest.raises(RuntimeError):w.step(clock=lambda:101)
    assert w.db.execute('select seq from checkpoint').fetchone()[0]==0
    with pytest.raises(RuntimeError):w.step(clock=lambda:101)
    w.close();w=ScenarioWorker(s,str(tmp_path/'output'),Consumer(),{});assert w.step(clock=lambda:101)==1;w.close();s.close()


def test_changed_source_prefix_rejected(tmp_path):
    s=EventStore(tmp_path/'input');s.append('rfq','test',{'id':'r'},'r',100)
    w=ScenarioWorker(s,str(tmp_path/'output'),Consumer(),{});w.step(clock=lambda:101);w.close()
    s.db.execute("update events set digest='changed' where seq=1")
    with pytest.raises(ValueError,match='prefix changed'):ScenarioWorker(s,str(tmp_path/'output'),Consumer(),{})
    s.close()


def test_completion_lag_not_mistaken_for_timely_candidate(tmp_path):
    s=EventStore(tmp_path/'input');s.append('rfq','test',{'id':'r'},'r',100)
    times=iter([101,103]);w=ScenarioWorker(s,str(tmp_path/'output'),Consumer(),{})
    w.step(clock=lambda:next(times));r=json.loads(w.db.execute('select result from candidate_decisions').fetchone()[0]);assert r['pricing']['status']=='scenario_priced' and not r['candidate_timely']
    w.close();s.close()


def test_decision_write_failure_rolls_back_checkpoint(tmp_path):
    import sqlite3
    s=EventStore(tmp_path/'input');s.append('rfq','test',{'id':'r'},'r',100)
    w=ScenarioWorker(s,str(tmp_path/'output'),Consumer(),{})
    w.db.execute("CREATE TRIGGER reject_decision BEFORE INSERT ON candidate_decisions BEGIN SELECT RAISE(ABORT,'test write failure'); END")
    with pytest.raises(sqlite3.IntegrityError):w.step(clock=lambda:101)
    assert w.poisoned and w.db.execute('SELECT seq FROM checkpoint').fetchone()[0]==0
    assert w.db.execute('SELECT COUNT(*) FROM candidate_decisions').fetchone()[0]==0
    w.db.execute('DROP TRIGGER reject_decision');w.db.commit();w.close()
    w=ScenarioWorker(s,str(tmp_path/'output'),Consumer(),{});assert w.step(clock=lambda:101)==1;w.close();s.close()


def test_commit_receipt_failure_preserves_decision_and_requires_restart(tmp_path):
    import sqlite3
    s=EventStore(tmp_path/'input');s.append('rfq','test',{'id':'r'},'r',100)
    w=ScenarioWorker(s,str(tmp_path/'output'),Consumer(),{})
    w.db.execute("CREATE TRIGGER reject_receipt BEFORE INSERT ON commit_receipts BEGIN SELECT RAISE(ABORT,'test receipt failure'); END")
    with pytest.raises(sqlite3.IntegrityError):w.step(clock=lambda:101)
    assert w.poisoned
    assert w.db.execute('SELECT seq FROM checkpoint').fetchone()[0]==1
    assert w.db.execute('SELECT COUNT(*) FROM candidate_decisions').fetchone()[0]==1
    assert w.db.execute('SELECT COUNT(*) FROM commit_receipts').fetchone()[0]==0
    w.close();w=ScenarioWorker(s,str(tmp_path/'output'),Consumer(),{})
    assert w.step(clock=lambda:101)==0
    assert w.db.execute('SELECT COUNT(*) FROM candidate_decisions').fetchone()[0]==1
    w.close();s.close()

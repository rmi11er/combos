import json,sqlite3
import pytest
from combos.event_store import EventStore
from combos.markout_worker import MarkoutWorker


class Pricing:
    def __init__(self):self.point=.25
    def consume(self,e,price_rfqs=False):
        if e['kind']=='price':self.point=e['payload']['point']
    def revalue(self,msg,at,seq):
        return {'status':'scenario_priced','scenarios':[{'assumed_usd_per_native_unit':1,'independent_combo_point':self.point}]}


def setup(tmp_path):
    s=EventStore(tmp_path/'source');s.append('rfq','test',{'id':'r','creator_id':'c'},'rfq',100)
    d=sqlite3.connect(tmp_path/'decisions');d.execute('CREATE TABLE candidate_decisions(source_seq INTEGER PRIMARY KEY,rfq_id TEXT,result TEXT)');d.commit()
    return s,d


def publish(d):
    p={'pricing':{'source_seq':1,'rfq_id':'r','status':'scenario_priced','at':100,'nlegs':2,
        'scenarios':[{'assumed_usd_per_native_unit':1,'independent_combo_point':.25}], 'research_policy':{}}}
    d.execute('INSERT INTO candidate_decisions VALUES(1,?,?)',('r',json.dumps(p)));d.commit()


def test_wait_for_decision_restart_and_no_future_leak(tmp_path):
    s,d=setup(tmp_path);w=MarkoutWorker(s,d,tmp_path/'marks',Pricing(),{},(10,))
    assert w.step()==0 and w.seq==0
    publish(d);assert w.step()==1
    assert w.db.execute('SELECT COUNT(*) FROM pending').fetchone()[0]==1;w.close()
    w=MarkoutWorker(s,d,tmp_path/'marks',Pricing(),{},(10,))
    s.append('price','test',{'point':.9},'later',111);assert w.step()==1
    label=json.loads(w.db.execute('SELECT value FROM labels').fetchone()[0])
    assert label['adverse_move_cents']==0 and label['available_source_seq']==1
    assert w.db.execute('SELECT COUNT(*) FROM pending').fetchone()[0]==0
    assert w.step()==0;w.close();d.close();s.close()


def test_failed_label_transaction_restores_pending_after_restart(tmp_path):
    s,d=setup(tmp_path);publish(d);w=MarkoutWorker(s,d,tmp_path/'marks',Pricing(),{},(10,));w.step()
    w.db.execute("CREATE TRIGGER fail_labels BEFORE INSERT ON labels BEGIN SELECT RAISE(ABORT,'fault'); END");w.db.commit()
    s.append('price','test',{'point':.9},'later',111)
    with pytest.raises(sqlite3.IntegrityError):w.step()
    assert w.db.execute('SELECT seq FROM checkpoint').fetchone()[0]==1
    assert w.db.execute('SELECT COUNT(*) FROM pending').fetchone()[0]==1
    with pytest.raises(RuntimeError):w.step()
    w.db.execute('DROP TRIGGER fail_labels');w.db.commit();w.close()
    w=MarkoutWorker(s,d,tmp_path/'marks',Pricing(),{},(10,));w.step()
    assert w.db.execute('SELECT COUNT(*) FROM labels').fetchone()[0]==1
    w.close();d.close();s.close()


def test_changed_decision_rejected_on_restart(tmp_path):
    s,d=setup(tmp_path);publish(d);w=MarkoutWorker(s,d,tmp_path/'marks',Pricing(),{},(10,));w.step();w.close()
    raw=json.loads(d.execute('SELECT result FROM candidate_decisions').fetchone()[0]);raw['pricing']['at']=101
    d.execute('UPDATE candidate_decisions SET result=?',(json.dumps(raw),));d.commit()
    with pytest.raises(ValueError,match='evidence changed'):MarkoutWorker(s,d,tmp_path/'marks',Pricing(),{},(10,))
    d.close();s.close()

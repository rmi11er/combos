import json
import pytest
from combos.execution_journal import ExecutionJournal
from combos.execution_ownership_store import MakerOwnership
from combos.execution_fills import FillEvidence
from test_execution_ownership import evidence,fill


def setup(tmp_path,monkeypatch,order_changes=None):
    import combos.execution_journal as module
    j=ExecutionJournal(tmp_path/'journal');e,q,o=evidence()
    o.update(order_changes or {})
    j.prepare('op','hold','POST','/trade-api/v2/communications/quotes',{'rfq_id':'r','yes_bid':'0','no_bid':'.7','rest_remainder':False,'post_only':True},at=100)
    monkeypatch.setattr(module.time,'time',lambda:100.5);j.claim('op');j.finish_dispatch('op',response={'id':'q'})
    m=MakerOwnership(j);m.record('op',e,q,o,104,105,0,'private:synthetic');return j,m,e,q,o


def envelope(rows):return {'method':'GET','path':'/trade-api/v2/portfolio/fills','http_status':200,'request_started_at':103,'received_at':104,'payload':{'fills':rows}}


def test_durable_binding_deduplicated_fills_and_snapshot_race(tmp_path,monkeypatch):
    j,m,e,q,o=setup(tmp_path,monkeypatch);f=FillEvidence(j);f.ingest(envelope([fill()]),'read1');f.ingest(envelope([fill()]),'read2')
    assert m.reconcile_fills(0,'maker-order',2)['fill_records']==1
    assert m.reconcile_fills(0,'maker-order',3)['status']=='fill_evidence_incomplete'
    assert m.reconcile_fills(0,'maker-order',1)['status']=='order_snapshot_behind_fills'
    j.close();j=ExecutionJournal(tmp_path/'journal');m=MakerOwnership(j)
    r=m.reconcile_fills(0,'maker-order',2);assert r['status']=='counts_match' and not r['capital_release_authorized'];j.close()


def test_cumulative_overfill_detected(tmp_path,monkeypatch):
    j,m,*_=setup(tmp_path,monkeypatch);f=FillEvidence(j);rows=[]
    for i in range(6):
        r=fill();r['fill_id']=str(i);rows.append(r)
    f.ingest(envelope(rows),'read')
    with pytest.raises(ValueError,match='cumulative'):m.reconcile_fills(0,'maker-order',10)
    j.close()


def test_unmatched_intent_does_not_write_binding(tmp_path):
    j=ExecutionJournal(tmp_path/'journal');m=MakerOwnership(j);e,q,o=evidence()
    with pytest.raises(KeyError):m.record('missing',e,q,o,104,105,0,'source')
    assert j.db.execute('SELECT COUNT(*) FROM maker_order_ownership').fetchone()[0]==0;j.close()


def test_no_fills_yet_is_valid_incomplete_evidence(tmp_path,monkeypatch):
    j,m,*_=setup(tmp_path,monkeypatch)
    r=m.reconcile_fills(0,'maker-order',2)
    assert r['quantity']=='0' and r['status']=='fill_evidence_incomplete'
    j.close()

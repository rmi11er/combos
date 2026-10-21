from concurrent.futures import ThreadPoolExecutor
import pytest
from combos.execution_journal import ExecutionJournal


def prepare(j):
    return j.prepare('quote:r1','risk:r1','POST','/trade-api/v2/communications/quotes',
                     {'rfq_id':'r1','yes_bid':'0','no_bid':'.7','rest_remainder':False})


def test_timeout_and_restart_never_resubmit_or_discard_inventory(tmp_path):
    path=tmp_path/'journal.sqlite';j=ExecutionJournal(path);prepare(j)
    class Transport:
        calls=0
        def send_once(self,*args):
            self.calls+=1
            raise TimeoutError('sensitive transport message must not be logged')
    t=Transport()
    assert j.dispatch('quote:r1',t)['state']=='unknown'
    j.close();j=ExecutionJournal(path)
    prepare(j)
    assert j.dispatch('quote:r1',t)['state']=='unknown' and t.calls==1
    assert len(j.reconciliation_inventory())==1
    assert 'sensitive' not in str([tuple(r) for r in j.db.execute('SELECT * FROM execution_intent_events')])
    j.close()


def test_crash_after_claim_and_before_response_is_not_retried(tmp_path):
    path=tmp_path/'journal.sqlite';j=ExecutionJournal(path);prepare(j)
    assert j.claim('quote:r1');j.close()
    j=ExecutionJournal(path)
    assert not j.claim('quote:r1')
    assert j.reconciliation_inventory()[0]['state']=='inflight'
    j.close()


def test_two_connections_only_one_can_claim(tmp_path):
    path=tmp_path/'journal.sqlite';j=ExecutionJournal(path);prepare(j);j.close()
    def claim():
        j=ExecutionJournal(path)
        try:return j.claim('quote:r1')
        finally:j.close()
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(lambda _:claim(),range(2)))==[False,True]


def test_success_is_still_reconciliation_work_and_conflicts_rejected(tmp_path):
    j=ExecutionJournal(tmp_path/'journal.sqlite');prepare(j)
    class Transport:
        def send_once(self,*args):return {'id':'q1'}
    assert j.dispatch('quote:r1',Transport())['response']=={'id':'q1'}
    assert j.reconciliation_inventory()[0]['state']=='acknowledged'
    with pytest.raises(ValueError,match='conflicting'):
        j.prepare('quote:r1','different-risk','POST','/trade-api/v2/communications/quotes',{})
    j.close()

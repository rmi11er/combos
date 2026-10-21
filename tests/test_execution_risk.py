import pytest
from concurrent.futures import ThreadPoolExecutor
from combos.execution_journal import ExecutionJournal
from combos.execution_risk import ExecutionRiskHolds


CONFIG={'capital_dollars':100,'maximum_committed_dollars':100,'per_contract_dollars':80,
        'per_combo_dollars':80,'per_fixture_dollars':80}
BUCKETS={'contract':['canonical-team-outcome'],'combo':['c'],'fixture':['game']}


def make(path):
    j=ExecutionJournal(path)
    return j,ExecutionRiskHolds(j,CONFIG)


def reserve(r,key='one',cost=60,body=None):
    return r.reserve_create(key,'risk:'+key,body or {'rfq_id':key,'yes_bid':'0','no_bid':'.7'},cost,BUCKETS)


def test_unknown_dispatch_keeps_cash_and_buckets_after_restart(tmp_path):
    path=tmp_path/'journal.sqlite';j,r=make(path);reserve(r)
    class Transport:
        def send_once(self,*args):raise TimeoutError()
    assert j.dispatch('one',Transport())['state']=='unknown'
    assert r.available_units()==400000
    j.close();j,r=make(path)
    assert r.available_units()==400000
    with pytest.raises(ValueError,match='exchange_reconciliation'):r.abandon_unsent('risk:one')
    with pytest.raises(ValueError,match='contract_risk_limit'):reserve(r,'two',30)
    with pytest.raises(ValueError,match='cash_limit'):reserve(r,'three',41)
    j.close()


def test_hold_and_intent_roll_back_together(tmp_path):
    j,r=make(tmp_path/'journal.sqlite')
    with pytest.raises(ValueError,match='credential'):
        reserve(r,body={'rfq_id':'one','api_key':'not-a-real-key'})
    assert r.available_units()==1000000
    assert j.db.execute('SELECT COUNT(*) FROM execution_holds').fetchone()[0]==0
    assert j.db.execute('SELECT COUNT(*) FROM execution_intents').fetchone()[0]==0
    j.close()


def test_idempotence_and_duplicate_rfq_block(tmp_path):
    j,r=make(tmp_path/'journal.sqlite');reserve(r);reserve(r)
    assert r.available_units()==400000
    with pytest.raises(ValueError,match='already has'):
        reserve(r,'other',body={'rfq_id':'one'})
    with pytest.raises(ValueError,match='conflicting'):
        reserve(r,'one',59)
    assert r.available_units()==400000
    j.close()


def test_abandon_and_dispatch_race_both_serializations(tmp_path):
    j,r=make(tmp_path/'journal.sqlite');reserve(r)
    r.abandon_unsent('risk:one');r.abandon_unsent('risk:one')
    assert not j.claim('one') and r.available_units()==1000000
    assert j.reconciliation_inventory()==[]
    reserve(r,'two');assert j.claim('two')
    with pytest.raises(ValueError,match='exchange_reconciliation'):r.abandon_unsent('risk:two')
    assert r.available_units()==400000
    j.close()


def test_successful_ack_does_not_release_and_lower_regime_cap_applies(tmp_path):
    j,r=make(tmp_path/'journal.sqlite');reserve(r)
    class Transport:
        def send_once(self,*args):return {'id':'exchange-quote'}
    j.dispatch('one',Transport())
    with pytest.raises(ValueError,match='exchange_reconciliation'):r.abandon_unsent('risk:one')
    with pytest.raises(ValueError,match='contract_risk_limit'):
        r.reserve_create('two','risk:two',{'rfq_id':'two'},1,BUCKETS,risk_multiplier=.5)
    assert r.available_units()==400000
    j.close()


def test_concurrent_reservations_cannot_overcommit_cash(tmp_path):
    path=tmp_path/'journal.sqlite';j,r=make(path);j.close()
    def attempt(key):
        j,r=make(path)
        try:
            try:reserve(r,key);return True
            except ValueError as exc:
                assert 'limit' in str(exc)
                return False
        finally:j.close()
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(attempt,['one','two']))==[False,True]
    j,r=make(path)
    assert r.available_units()==400000
    assert j.db.execute('SELECT COUNT(*) FROM execution_intents').fetchone()[0]==1
    j.close()

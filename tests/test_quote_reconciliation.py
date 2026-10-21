from dataclasses import replace
import pytest
from combos.quote_reconciliation import ExpectedQuote, match_quote, QuoteReconciler
from combos.execution_journal import ExecutionJournal


def expected():
    return ExpectedQuote('r1','COMBO','maker',0,'0','.7','10.00',100,quote_id='q1',fixed_contracts='10.00')


def quote():
    return {'id':'q1','rfq_id':'r1','market_ticker':'COMBO','creator_user_id':'maker','creator_subaccount':0,
            'yes_bid_dollars':'0.0000','no_bid_dollars':'0.7000','yes_contracts_fp':'10.00','no_contracts_fp':'10.00',
            'contracts_fp':'10.00','rest_remainder':False,'post_only':True,'status':'accepted','accepted_side':'no',
            'created_ts':'1970-01-01T00:01:41Z','updated_ts':'1970-01-01T00:01:42Z'}


def test_matching_is_not_confirmation_or_cash_release():
    result=match_quote(expected(),quote(),102,103)
    assert result['matched'] and not result['confirmation_authorized'] and not result['capital_release_authorized']


@pytest.mark.parametrize('field,value',[('rfq_id','other'),('creator_user_id','other'),('creator_subaccount',1),
    ('no_bid_dollars','.71'),('accepted_side','yes'),('no_contracts_fp','10.01'),('no_contracts_fp','0'),
    ('yes_contracts_fp','NaN'),('post_only',False),('contracts_fp','9.00'),('id','q2')])
def test_mismatch_rejected(field,value):
    q=quote();q[field]=value
    with pytest.raises(ValueError):match_quote(expected(),q,102,103)


def test_target_cost_requires_returned_size_and_stale_is_rejected():
    e=replace(expected(),fixed_contracts=None)
    q=quote();del q['no_contracts_fp']
    with pytest.raises(KeyError):match_quote(e,q,102,103)
    with pytest.raises(ValueError,match='stale'):match_quote(e,quote(),102,105)


def test_durable_snapshot_assessment_does_not_change_intent(tmp_path,monkeypatch):
    import combos.execution_journal as module
    j=ExecutionJournal(tmp_path/'journal.sqlite')
    body={'rfq_id':'r1','yes_bid':'0','no_bid':'.7','post_only':True,'rest_remainder':False}
    j.prepare('create:r1','risk:r1','POST','/trade-api/v2/communications/quotes',body,at=100)
    reconciler=QuoteReconciler(j)
    with pytest.raises(ValueError,match='not dispatched'):
        reconciler.record('create:r1',expected(),quote(),102,103,'synthetic:quote')
    monkeypatch.setattr(module.time,'time',lambda:100.5)
    assert j.claim('create:r1')
    j.finish_dispatch('create:r1',response={'id':'q1'})
    assert reconciler.record('create:r1',expected(),quote(),102,103,'synthetic:quote')['matched']
    bad=quote();bad['id']='q2'
    assert not reconciler.record('create:r1',expected(),bad,102,103,'synthetic:wrong')['matched']
    assert j.get('create:r1')['state']=='acknowledged'
    assert len(j.reconciliation_inventory())==1
    assert j.db.execute("SELECT COUNT(*) FROM execution_intent_events WHERE state='quote_snapshot'").fetchone()[0]==2
    j.close()

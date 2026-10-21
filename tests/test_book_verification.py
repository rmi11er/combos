from copy import deepcopy
import pytest
from combos.book_verification import verify_snapshot,candidate_time


def args():
    book={'bid':[['.4','10']],'ask':[['.6','20']]}
    return dict(token='t',snapshot={'asset_id':'t','timestamp':'1000','bids':[{'price':'.4','size':'10'}],
        'asks':[{'price':'.6','size':'20'}]},before=book,after=deepcopy(book),
        generation_before='session',generation_after='session',revision_before=3,revision_after=3,
        request_started_at=100,received_at=100.5,response_headers={'Date':'Thu, 01 Jan 1970 00:01:40 GMT'},source_reference='raw')


def test_old_native_time_with_recent_verified_ladder():
    a=args();e=verify_snapshot(**a)
    assert e['native_snapshot_at']==1 and e['verified_at']==100
    result=candidate_time(e,token='t',generation='session',revision=3,current_book=a['before'],now=101)
    assert result['candidate_observed_at']==100 and not result['live_pricing_authorized']
    assert a['snapshot']['timestamp']=='1000'


@pytest.mark.parametrize('change',[{'generation_after':'reconnect'},{'revision_after':4},
    {'received_at':110},{'response_headers':{'Date':'Thu, 01 Jan 1970 00:01:40 GMT','Age':'10'}}])
def test_invalid_verification_rejected(change):
    a=args();a.update(change)
    with pytest.raises(ValueError):verify_snapshot(**a)


def test_depth_mismatch_even_with_identical_prices():
    a=args();a['after']['bid'][0][1]='11'
    with pytest.raises(ValueError,match='ladders differ'):verify_snapshot(**a)


@pytest.mark.parametrize('change',[{'generation':'new'},{'revision':4},{'now':120},{'now':100}])
def test_evidence_expires_on_state_change_or_time(change):
    a=args();e=verify_snapshot(**a)
    kwargs=dict(token='t',generation='session',revision=3,current_book=a['before'],now=101)
    kwargs.update(change)
    with pytest.raises(ValueError):candidate_time(e,**kwargs)

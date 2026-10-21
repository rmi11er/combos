import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from top_book_state_research import TopBookState
from top_book_verification_research import verify_top_snapshot


def setup():
    book = {'bid': [('.4', '10')], 'ask': [('.6', '20')]}
    e = verify_top_snapshot(token='t', snapshot={'asset_id':'t','timestamp':'1000',
        'bids':[{'price':'.4','size':'10'}],'asks':[{'price':'.6','size':'20'}]},
        before=book,after=book,generation_before='g',generation_after='g',revision_before=3,revision_after=3,
        request_started_at=100,received_at=100.5,response_headers={'Date':'Thu, 01 Jan 1970 00:01:40 GMT'},source_reference='raw')
    state=TopBookState({'t':'k'},{('raw','t'):{'raw_seq':2,'evidence':e}})
    native=dict(market_key='k',venue='polymarket',active=False,invalid_reason='snapshot_depth_quarantine',
        connection_generation='g',book_revision=3,observed_at=1,available_at=99,
        yes_bid=.4,yes_ask=.6,yes_bid_size=10,yes_ask_size=20)
    state.consume(dict(seq=1,kind='observation',source='polymarket',received_at=99,payload=native))
    return state,native


def publish(state):
    state.consume(dict(seq=3,kind='book_verification_status',source='polymarket',received_at=101,
        payload={'status':'rejected','source_reference':'raw','token':'t'}))


def test_publication_not_http_time_controls_visibility():
    state,_=setup()
    assert state.pair('k',101)['candidate'] is None
    publish(state)
    assert state.pair('k',100.75)['candidate'] is None
    assert state.pair('k',101)['candidate']['active']
    assert state.pair('k',116)['candidate'] is None


def test_revision_and_rebuild_invalidate():
    state,native=setup();publish(state)
    state.consume(dict(seq=4,kind='observation',source='polymarket',received_at=102,payload=dict(native,book_revision=4)))
    assert state.pair('k',102)['candidate'] is None
    state,_=setup();publish(state)
    state.consume(dict(seq=4,kind='book_rebuild',source='polymarket',received_at=102,payload={'tokens':['t']}))
    assert state.pair('k',102)['candidate'] is None


def test_quarantine_does_not_override_real_size_mismatch():
    state,native=setup();publish(state)
    state.consume(dict(seq=4,kind='observation',source='polymarket',received_at=102,payload=dict(native,yes_bid_size=11)))
    assert state.pair('k',102)['candidate'] is None

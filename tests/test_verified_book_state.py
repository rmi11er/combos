from copy import deepcopy
import pytest
from combos.verified_book_state import VerifiedBookState


def events():
    row=dict(market_key='m',venue='polymarket',active=True,source_reference='ws',
        observed_at=1,available_at=100,yes_bid=.4,yes_ask=.6,yes_bid_size=10,yes_ask_size=20,
        connection_generation='s',book_revision=1)
    observation=dict(seq=1,kind='observation',source='polymarket',received_at=100,payload=row)
    evidence=dict(basis='matching_rest_ws_full_depth_v1',generation='s',revision=1,
        verified_at=101,available_at=102,source_reference='rest')
    verification=dict(seq=2,kind='book_verification',source='polymarket',received_at=103,
        payload={'market_key':'m','baseline_observation':deepcopy(row),'evidence':evidence})
    return observation,verification


def test_causal_candidate_and_expiry_preserve_native():
    s=VerifiedBookState();a,b=events();s.consume(a);s.consume(b)
    assert s.pair('m',102)['candidate'] is None
    pair=s.pair('m',103)
    assert pair['baseline'] is None and pair['candidate']['observed_at']==101
    assert s.books['m']['observed_at']==1
    assert s.pair('m',117)['candidate'] is None


@pytest.mark.parametrize('reset',[False,True])
def test_update_or_reset_removes_verification(reset):
    s=VerifiedBookState();a,b=events();s.consume(a);s.consume(b)
    if reset:s.consume(dict(seq=3,kind='venue_reset',source='polymarket',received_at=104,payload={}))
    else:
        a['seq']=3;a['payload']['book_revision']=2;s.consume(a)
    assert s.pair('m',104)['candidate'] is None


def test_mismatching_baseline_and_duplicate_sequence_rejected():
    s=VerifiedBookState();a,b=events();s.consume(a)
    b['payload']['baseline_observation']['yes_bid_size']=999
    with pytest.raises(ValueError,match='baseline'):s.consume(b)
    with pytest.raises(ValueError,match='sequence'):s.consume(a)

import pytest
from combos.feed_liveness import FeedLiveness


def test_local_heartbeat_is_not_upstream_evidence():
    tracker=FeedLiveness(0)
    result=tracker.evidence(20)
    assert result['last_inbound_frame_age_seconds'] is None
    assert not result['book_observation_time_renewed']
    assert not result['market_book_synchronization_verified']


def test_pong_is_distinct_from_market_data():
    tracker=FeedLiveness(0)
    tracker.received(1)
    tracker.ping_sent(10)
    tracker.received(10.25,pong=True)
    result=tracker.evidence(11)
    assert result['last_application_ping_rtt_seconds']==.25
    assert result['last_data_frame_age_seconds']==10
    assert result['last_matched_application_pong_age_seconds']==.75
    assert result['unanswered_application_ping_age_seconds'] is None


def test_repeated_ping_does_not_hide_missing_response():
    tracker=FeedLiveness(0)
    tracker.ping_sent(10);tracker.ping_sent(20)
    assert tracker.evidence(25)['unanswered_application_ping_age_seconds']==15


def test_unsolicited_pong_and_invalid_time():
    tracker=FeedLiveness(0)
    tracker.received(1,pong=True)
    assert tracker.evidence(2)['last_matched_application_pong_age_seconds'] is None
    with pytest.raises(ValueError):tracker.evidence(.5)

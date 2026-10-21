from copy import deepcopy
import pytest
from combos.snapshot_age import delivery_observation_time
from combos.pinnacle_feed import normalize, fixture_index
from test_pinnacle_feed import sample


def inputs():
    return ({'request_started_at': 129.5, 'retrieved_at': 130.,
             'response_headers': {'Date': 'Thu, 01 Jan 1970 00:02:10 GMT'}},
            {'mode': 'response_delivery_proxy_v1', 'reference': 'synthetic:assumption',
             'assume_live_upstream_snapshot': True, 'maximum_request_seconds': 5,
             'maximum_http_age_seconds': 5, 'maximum_http_date_lag_seconds': 5,
             'clock_tolerance_seconds': 1})


def test_unchanged_price_separate_from_delivery_age_without_claiming_health():
    snapshot, policy = inputs()
    mapping, fixture = sample()
    old, _ = normalize(mapping, fixture_index(fixture), 130, 'raw', snapshot=snapshot)
    new, _ = normalize(mapping, fixture_index(fixture), 130, 'raw', snapshot=snapshot, freshness_policy=policy)
    assert old['observed_at'] == 70
    assert new['active'] and new['observed_at'] == 99.5 and new['available_at'] == 130
    assert new['native_changed_at'] == [70, 70]
    assert new['freshness_context']['upstream_freshness_validated'] is False
    assert new['freshness_context']['upstream_live_snapshot_assumed'] is True
    with pytest.raises(ValueError, match='receipt_mismatch'):
        delivery_observation_time(snapshot, 160, 30, policy)  # cached envelope cannot be retimestamped


@pytest.mark.parametrize('case', ['slow', 'old_date', 'future_date', 'cache', 'nan_age', 'missing_date', 'implicit'])
def test_delivery_guards(case):
    snapshot, policy = inputs()
    if case == 'slow': snapshot['request_started_at'] = 100
    if case == 'old_date': snapshot['response_headers']['Date'] = 'Thu, 01 Jan 1970 00:01:00 GMT'
    if case == 'future_date': snapshot['response_headers']['Date'] = 'Thu, 01 Jan 1970 00:03:00 GMT'
    if case == 'cache': snapshot['response_headers']['Age'] = '20'
    if case == 'nan_age': snapshot['response_headers']['Age'] = 'nan'
    if case == 'missing_date': del snapshot['response_headers']['Date']
    if case == 'implicit': policy['assume_live_upstream_snapshot'] = False
    with pytest.raises((ValueError, KeyError)):
        delivery_observation_time(snapshot, 130, 30, policy)
    m, f = sample()
    row, _ = normalize(m, fixture_index(f), 130, 'raw', snapshot=snapshot, freshness_policy=policy)
    assert not row['active']

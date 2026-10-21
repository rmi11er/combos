"""Explicit delivery-age proxy; successful HTTP delivery is not upstream proof."""
from email.utils import parsedate_to_datetime
import math


def delivery_observation_time(snapshot, received_at, nominal_delay, policy):
    if policy.get('mode') != 'response_delivery_proxy_v1' or not policy.get('reference'):
        raise ValueError('unreviewed_snapshot_age_policy')
    if policy.get('assume_live_upstream_snapshot') is not True:
        raise ValueError('snapshot_upstream_assumption_not_explicit')
    names = ('maximum_request_seconds', 'maximum_http_age_seconds',
             'maximum_http_date_lag_seconds', 'clock_tolerance_seconds')
    limits = {name: float(policy[name]) for name in names}
    if any(not math.isfinite(v) or v < 0 for v in limits.values()):
        raise ValueError('invalid_snapshot_age_limits')
    started, retrieved = float(snapshot['request_started_at']), float(snapshot['retrieved_at'])
    if not all(math.isfinite(v) for v in (started, retrieved, received_at, nominal_delay)) or nominal_delay < 30:
        raise ValueError('invalid_snapshot_chronology')
    if abs(retrieved-received_at) > .000001 or started > retrieved:
        raise ValueError('snapshot_receipt_mismatch')
    if retrieved-started > limits['maximum_request_seconds']:
        raise ValueError('snapshot_request_too_slow')
    headers = {k.lower(): v for k, v in snapshot['response_headers'].items()}
    date = parsedate_to_datetime(headers['date'])
    if date.tzinfo is None:
        raise ValueError('http_date_timezone_missing')
    dated = date.timestamp()
    age = float(headers.get('age', 0))
    if not math.isfinite(age) or age < 0:
        raise ValueError('invalid_http_cache_age')
    if age > limits['maximum_http_age_seconds']:
        raise ValueError('http_cached_snapshot_too_old')
    if dated-retrieved > limits['clock_tolerance_seconds']:
        raise ValueError('http_date_in_future')
    if retrieved-dated > limits['maximum_http_date_lag_seconds']:
        raise ValueError('http_date_too_old')
    observed = min(started, dated)-age-nominal_delay
    return observed, {'weight_age_basis': policy['mode'], 'policy_reference': policy['reference'],
        'upstream_freshness_validated': False, 'upstream_live_snapshot_assumed': True,
        'request_started_at': started, 'response_received_at': retrieved,
        'http_date_at': dated, 'http_age_seconds': age, 'nominal_delay_seconds': nominal_delay,
        'effective_observed_at': observed}

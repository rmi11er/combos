"""Full-depth snapshot evidence for a separate shadow freshness candidate."""
from decimal import Decimal, InvalidOperation
from email.utils import parsedate_to_datetime
import hashlib
import json
import math


def canonical(book):
    if set(book) != {'bid','ask'}:
        raise ValueError('two ladders required')
    result={}
    for side, rows in book.items():
        levels={}
        for price, size in rows:
            try:p,q=Decimal(str(price)),Decimal(str(size))
            except InvalidOperation:raise ValueError('invalid ladder value') from None
            if not p.is_finite() or not q.is_finite() or not 0<=p<=1 or q<=0:
                raise ValueError('invalid ladder value')
            if p in levels:raise ValueError('duplicate price level')
            levels[p]=q
        if not levels:raise ValueError('positive two-sided depth required')
        result[side]=[(str(p.normalize()),str(q.normalize())) for p,q in sorted(levels.items())]
    if Decimal(result['bid'][-1][0])>Decimal(result['ask'][0][0]):
        raise ValueError('crossed book')
    return result


def digest(book):
    return hashlib.sha256(json.dumps(canonical(book),sort_keys=True).encode()).hexdigest()


def verify_snapshot(*, token, snapshot, before, after, generation_before,
                    generation_after, revision_before, revision_after,
                    request_started_at, received_at, response_headers,
                    source_reference, maximum_request_seconds=2):
    if not token or not source_reference or not generation_before or generation_before!=generation_after:
        raise ValueError('missing provenance or connection changed')
    if type(revision_before) is not int or revision_before<0 or revision_before!=revision_after:
        raise ValueError('book changed during snapshot request')
    if not all(math.isfinite(t) for t in (request_started_at,received_at,maximum_request_seconds)) or not 0<maximum_request_seconds<=5 or not 0<=received_at-request_started_at<=maximum_request_seconds:
        raise ValueError('invalid or slow snapshot request')
    if snapshot.get('asset_id')!=token:
        raise ValueError('snapshot token mismatch')
    headers={k.lower():v for k,v in response_headers.items()}
    date=parsedate_to_datetime(headers['date'])
    if date.tzinfo is None:raise ValueError('HTTP Date timezone required')
    http_at=date.timestamp();age=float(headers.get('age',0))
    if not math.isfinite(age) or age<0 or age>2 or not -2<=received_at-http_at<=5:
        raise ValueError('HTTP freshness evidence invalid')
    native_at=float(snapshot['timestamp'])/1000
    if not math.isfinite(native_at) or native_at>received_at+.25:
        raise ValueError('invalid native snapshot time')
    rest={side:[(r['price'],r['size']) for r in snapshot[field]] for side,field in (('bid','bids'),('ask','asks'))}
    fingerprint=digest(rest)
    if fingerprint!=digest(before) or fingerprint!=digest(after):
        raise ValueError('REST and WebSocket ladders differ')
    return {'token':token,'generation':generation_after,'revision':revision_after,
        'ladder_sha256':fingerprint,'verified_at':min(request_started_at,http_at)-age,
        'available_at':received_at,'native_snapshot_at':native_at,
        'source_reference':source_reference,'basis':'matching_rest_ws_full_depth_v1',
        'upstream_independently_verified':False}


def candidate_time(evidence, *, token, generation, revision, current_book, now,
                   maximum_verification_age=15):
    if evidence['basis']!='matching_rest_ws_full_depth_v1' or evidence['token']!=token or evidence['generation']!=generation:
        raise ValueError('verification identity mismatch')
    if evidence['revision']!=revision or evidence['ladder_sha256']!=digest(current_book):
        raise ValueError('book changed since verification')
    if not math.isfinite(now) or not math.isfinite(maximum_verification_age) or maximum_verification_age<=0 or not evidence['verified_at']<=evidence['available_at']<=now or now-evidence['verified_at']>maximum_verification_age:
        raise ValueError('verification stale or not yet available')
    return {'candidate_observed_at':evidence['verified_at'],
        'native_snapshot_at':evidence['native_snapshot_at'],'verification_reference':evidence['source_reference'],
        'basis':evidence['basis'],'live_pricing_authorized':False}

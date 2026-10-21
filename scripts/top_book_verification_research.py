"""Explicit top-only shadow evidence; never certifies a reconstructed full ladder."""
from copy import deepcopy
from combos.book_verification import canonical, verify_snapshot, candidate_time

BASIS = 'matching_rest_ws_top_prices_sizes_research_v1'


def top(book):
    # Validate the entire supplied representation before projecting it.
    levels = canonical(book)
    return {'bid': [levels['bid'][-1]], 'ask': [levels['ask'][0]]}


def verify_top_snapshot(**kwargs):
    args = deepcopy(kwargs)
    snapshot = args['snapshot']
    rest = top({side: [(row['price'], row['size']) for row in snapshot[field]]
                for side, field in (('bid', 'bids'), ('ask', 'asks'))})
    for side, field in (('bid', 'bids'), ('ask', 'asks')):
        snapshot[field] = [{'price': p, 'size': q} for p, q in rest[side]]
    args['before'] = top(args['before'])
    args['after'] = top(args['after'])
    evidence = verify_snapshot(**args)
    evidence['basis'] = BASIS
    evidence['top_sha256'] = evidence.pop('ladder_sha256')
    evidence['full_depth_verified'] = False
    evidence['live_pricing_authorized'] = False
    return evidence


def top_candidate_time(evidence, **kwargs):
    if evidence.get('basis') != BASIS or evidence.get('full_depth_verified') is not False:
        raise ValueError('top-only evidence required')
    translated = deepcopy(evidence)
    translated['basis'] = 'matching_rest_ws_full_depth_v1'
    translated['ladder_sha256'] = translated.pop('top_sha256')
    args = dict(kwargs, current_book=top(kwargs['current_book']))
    result = candidate_time(translated, **args)
    result['basis'] = BASIS
    result['full_depth_verified'] = False
    return result

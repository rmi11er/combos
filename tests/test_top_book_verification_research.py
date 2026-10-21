from copy import deepcopy
import importlib.util
from pathlib import Path
import pytest

spec = importlib.util.spec_from_file_location('top_research', Path(__file__).resolve().parents[1] / 'scripts/top_book_verification_research.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def arguments():
    book = {'bid': [['.3', '8'], ['.4', '10']], 'ask': [['.6', '20'], ['.7', '5']]}
    return dict(token='t', snapshot={'asset_id': 't', 'timestamp': '1000',
        'bids': [{'price': '.3', 'size': '99'}, {'price': '.4', 'size': '10'}],
        'asks': [{'price': '.6', 'size': '20'}, {'price': '.8', 'size': '11'}]},
        before=book, after=deepcopy(book), generation_before='g', generation_after='g',
        revision_before=3, revision_after=3, request_started_at=100, received_at=100.5,
        response_headers={'Date': 'Thu, 01 Jan 1970 00:01:40 GMT'}, source_reference='raw')


def test_deep_mismatch_has_only_top_authority_and_leaves_inputs_unchanged():
    args = arguments()
    before = deepcopy(args)
    evidence = module.verify_top_snapshot(**args)
    assert args == before
    assert evidence['basis'] == module.BASIS
    assert not evidence['full_depth_verified'] and not evidence['live_pricing_authorized']
    assert 'ladder_sha256' not in evidence
    result = module.top_candidate_time(evidence, token='t', generation='g', revision=3,
                                      current_book=args['after'], now=101)
    assert result['basis'] == module.BASIS and not result['live_pricing_authorized']


@pytest.mark.parametrize('field,value', [('price', '.41'), ('size', '11')])
def test_top_price_or_size_mismatch_rejected(field, value):
    args = arguments()
    args['snapshot']['bids'][1][field] = value
    with pytest.raises(ValueError, match='ladders differ'):
        module.verify_top_snapshot(**args)


@pytest.mark.parametrize('change', [{'generation_after': 'new'}, {'revision_after': 4},
    {'received_at': 110}, {'response_headers': {'Date': 'Thu, 01 Jan 1970 00:01:40 GMT', 'Age': '10'}}])
def test_original_chronology_guards_retained(change):
    args = arguments()
    args.update(change)
    with pytest.raises(ValueError):
        module.verify_top_snapshot(**args)


@pytest.mark.parametrize('change', [{'revision': 4}, {'generation': 'new'}, {'now': 120}, {'now': 100}])
def test_expiration_and_any_revision_change_invalidate_certificate(change):
    args = arguments()
    evidence = module.verify_top_snapshot(**args)
    query = dict(token='t', generation='g', revision=3, current_book=args['after'], now=101)
    query.update(change)
    with pytest.raises(ValueError):
        module.top_candidate_time(evidence, **query)


def test_malformed_deep_ladder_is_not_silently_ignored():
    args = arguments()
    args['before']['bid'].append(['.3', '8'])
    with pytest.raises(ValueError, match='duplicate'):
        module.verify_top_snapshot(**args)

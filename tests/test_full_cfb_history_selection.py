import importlib.util
from pathlib import Path
import sys

import pytest

SCRIPTS = Path(__file__).parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location('full_cfb_history', SCRIPTS / 'cfb_full_history_acquire.py')
acquire = importlib.util.module_from_spec(spec)
spec.loader.exec_module(acquire)


def fixture(fid='f1'):
    return {'fixtureId': fid, 'participant1ShortName': 'Lions', 'participant2ShortName': 'Bears',
            'startTime': '2026-09-05T12:00:00Z'}


def test_single_mapped_line_qualifies_and_timezone_is_equivalent():
    mapping = {'one-line': {'status': 'matched', 'teams': ['lions', 'bears'],
                            'start_time': '2026-09-05T07:00:00-05:00'}}
    result = acquire.build_selection([fixture()], mapping)
    assert result['candidate_fixtures'] == 1
    assert result['selected'][0]['kalshi_tickers'] == ['one-line']


def test_unmapped_fixture_is_explicit_and_duplicates_rejected():
    result = acquire.build_selection([fixture()], {})
    assert result['selected'] == []
    assert result['excluded_fixtures'][0]['reason'] == 'no_exact_existing_exchange_fixture_mapping'
    with pytest.raises(ValueError, match='duplicate'):
        acquire.build_selection([fixture(), fixture()], {})


def test_reviewed_alias_does_not_relax_start_time_matching():
    native = {**fixture(), 'participant1Name': 'Miami Hurricanes', 'participant1ShortName': 'Miami'}
    mapping = {'m': {'status': 'matched', 'teams': ['miamifl', 'bears'],
                     'start_time': '2026-09-05T12:00:00Z'}}
    joined = acquire.build_selection([native], mapping)
    assert len(joined['selected']) == 1
    assert joined['selected'][0]['provider_team_identities'][0]['native_full_name'] == 'Miami Hurricanes'
    mapping['m']['start_time'] = '2026-09-05T12:01:00Z'
    mismatch = acquire.build_selection([native], mapping)
    assert mismatch['selected'] == []
    assert mismatch['unjoined_exchange_mappings'][0]['reason'] == 'fixture_start_time_disagreement'

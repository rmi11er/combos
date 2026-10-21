from copy import deepcopy
from datetime import datetime, timedelta
import gzip
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'scripts'))
from nfl_playoffs_history_probe import ProviderArchive, match_fixtures, stamp
from nfl_playoffs_public_acquire import calendar_days
from nfl_playoffs_exchange_review import native_event, review
from nfl_playoffs_cohort import classify


def schedule():
    return json.loads((ROOT / 'config/nfl_playoffs_history_2026.json').read_text())


def provider_rows():
    return [{'sportId': 14, 'tournamentId': 31, 'statusId': 2, 'fixtureId': str(i),
             'participant1Name': f['home'], 'participant2Name': f['away'], 'startTime': f['scheduled_start']}
            for i, f in enumerate(schedule()['fixtures'])]


def test_exact_NFL_participants_and_date_required_but_clock_difference_is_logged():
    rows = provider_rows()
    rows[4]['startTime'] = (datetime.fromisoformat(rows[4]['startTime']) + timedelta(minutes=15)).isoformat()
    result = match_fixtures(schedule(), rows)
    assert len(result) == 10
    assert result[4]['start_clock_discrepancy_requires_review'] is True
    assert result[4]['provider_minus_official_start_seconds'] == 900
    assert result[4]['conservative_original_schedule_cutoff'] == stamp(schedule()['fixtures'][4]['scheduled_start'])
    with pytest.raises(ValueError, match='not_unique'):
        match_fixtures(schedule(), rows + [rows[0]])
    rows[0]['participant2Name'] = 'Los Angeles Chargers'
    with pytest.raises(ValueError, match='not_unique'):
        match_fixtures(schedule(), rows)


def test_calendar_and_native_aliases_keep_NFL_scope_separate():
    dates = calendar_days(schedule())
    assert len(dates) == 14 and dates[0] == '2026-01-05' and dates[-1] == '2026-01-18'
    assert native_event(schedule()['fixtures'][0]) == 'KXNFLGAME-26JAN10LACAR'
    assert native_event(schedule()['fixtures'][2]) == 'KXNFLGAME-26JAN11BUFJAC'
    invalid = schedule()
    invalid['sport'] = 'MLB'
    with pytest.raises(ValueError, match='NFL_schedule'):
        calendar_days(invalid)


def test_classifier_retains_broad_scope_without_admitting_wrong_fixture_or_prop():
    market = {'mve_selected_legs': [{'market_ticker': 'KXNFLGAME-26JAN10LACAR-LA', 'side': 'no'},
                                  {'market_ticker': 'KXNFLSPREAD-26JAN10GBCHI-CHI3', 'side': 'yes'}]}
    c = classify(market, schedule())
    assert c['pure_nfl'] and c['target_fixtures_only'] and c['fullgame_core'] and c['distinct_fixtures']
    market['mve_selected_legs'][1]['market_ticker'] = 'KXNFLANYTD-26JAN10LACAR-PLAYER'
    c = classify(market, schedule())
    assert c['pure_nfl'] and c['target_fixtures_only']
    assert not c['fullgame_core'] and not c['distinct_fixtures']
    market['mve_selected_legs'][1]['market_ticker'] = 'KXNFLGAME-26JAN18SFSEA-SF'
    c = classify(market, schedule())
    assert not c['target_fixtures_only']  # Wrong original date is not nearest matched.


class FakeResponse:
    status_code = 403
    headers = {'Content-Type': 'application/json'}
    content = b'{"error":"denied"}'
    def json(self):
        return {'apiKey': 'test-secret', 'error': 'denied test-secret', 'details': 'apiKey=test-secret'}


def test_provider_denial_cached_redacted_and_budget_counts_attempts(tmp_path):
    client = ProviderArchive(tmp_path, 'test-secret', max_requests=1)
    calls = []
    class Session:
        def get(self, *args, **kwargs):
            calls.append((args, kwargs))
            return FakeResponse()
    client.session = Session()
    result = client.get('test', 'historical-odds', {'fixtureId': 'fixture', 'bookmakers': 'pinnacle'})
    assert result['http_status'] == 403
    assert 'test-secret' not in json.dumps(result)
    assert calls[0][1]['allow_redirects'] is False
    assert client.get('test', 'historical-odds', {'fixtureId': 'fixture', 'bookmakers': 'pinnacle'}) == result
    assert len(calls) == 1
    with pytest.raises(ValueError, match='budget_exhausted'):
        client.get('another', 'fixtures', {})
    for path in tmp_path.glob('*.json.gz'):
        assert 'test-secret' not in gzip.decompress(path.read_bytes()).decode()


def test_provider_cache_hash_corruption_stops_before_network(tmp_path):
    client = ProviderArchive(tmp_path, 'test-secret')
    class Session:
        def get(self, *args, **kwargs):
            return FakeResponse()
    client.session = Session()
    client.get('test', 'historical-odds', {'fixtureId': 'fixture', 'bookmakers': 'pinnacle'})
    path = next(tmp_path.glob('*.json.gz'))
    path.write_bytes(b'corrupt')
    with pytest.raises(ValueError, match='hash_mismatch'):
        client.get('test', 'historical-odds', {'fixtureId': 'fixture', 'bookmakers': 'pinnacle'})

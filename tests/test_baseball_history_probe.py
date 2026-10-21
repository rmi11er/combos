import importlib.util
import json
from pathlib import Path
from urllib.parse import quote

import pytest

spec = importlib.util.spec_from_file_location('baseball_probe', Path(__file__).parents[1] / 'scripts/oddspapi_baseball_history.py')
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


def history():
    return {'fixtureId': 'fixture1', 'bookmakers': {'pinnacle+30': {'markets': {'1': {
        'outcomes': {'2': {'players': {'0': [
            {'createdAt': '2026-07-01T12:00:00Z', 'active': True},
            {'createdAt': '2026-07-01T12:01:00Z', 'active': False}]}}}}}}}}


def test_history_counts_inactive_and_chronology():
    result = probe.history_summary(history(), 'fixture1')
    assert result['row_count'] == 2
    assert result['activity_counts'] == {'active': 1, 'inactive': 1}
    assert result['earliest_created_at'] == '2026-07-01T12:00:00+00:00'
    with pytest.raises(ValueError):
        probe.history_summary(history(), 'wrong-fixture')


def test_secret_scrub_handles_encoded_and_non_json_body():
    key = 'private/? key'
    result = probe.scrub({'api_key': key, 'non_json_body': f'url?apiKey={quote(key, safe="")}&a=2',
                          'nested': [key, 'https://x/?access_token=othersecret']}, key)
    assert key not in json.dumps(result)
    assert quote(key, safe='') not in json.dumps(result)
    assert 'othersecret' not in json.dumps(result)
    assert result['api_key'] == '[REDACTED]'


def test_discovery_does_not_filter_current_has_odds():
    row = {'fixtureId': 'fixture1', 'sportId': 13, 'statusId': 2, 'tournamentSlug': 'mlb', 'hasOdds': False}
    assert probe.choose_fixture([row]) == row
    with pytest.raises(ValueError):
        probe.choose_fixture([{**row, 'sportId': 14}])


class Response:
    headers = {}
    def __init__(self, status, payload):
        self.status_code, self.payload = status, payload
    def json(self):
        return self.payload


class Session:
    def __init__(self, responses):
        self.responses, self.calls = list(responses), []
    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        assert kwargs['allow_redirects'] is False
        return self.responses.pop(0)


def test_history_not_preblocked_by_football_subscription_and_resume(tmp_path, monkeypatch):
    monkeypatch.setattr(probe.time, 'sleep', lambda _: None)
    account = {'subscriptions': [{'subscription_id': 's', 'sport_ids': [14], 'request_count': 17}]}
    session = Session([Response(200, account), Response(403, {'error': 'apiKey=secret'}),
                       Response(200, history()), Response(200, account)])
    client = probe.Probe(tmp_path, 'secret', {'fixture_id': 'fixture1', 'start': '2026-07-01'}, session)
    report = probe.run(client)
    assert report['historical_access'] == 'confirmed_nonempty_history'
    assert report['requests_attempted'] == 4
    assert [x['http_status'] for x in report['history_attempts']] == [403, 200]
    assert report['request_counter_delta'] == {'s': 0}
    assert all('/odds' not in url for url, _ in session.calls)
    assert probe.run(client)['requests_attempted'] == 4
    assert len(session.calls) == 4


def test_request_ceiling_reserves_account_after(tmp_path, monkeypatch):
    monkeypatch.setattr(probe.time, 'sleep', lambda _: None)
    client = probe.Probe(tmp_path, 'secret', {'fixture_id': 'fixture1', 'start': '2026-07-01'},
                         Session([Response(403, {}) for _ in range(6)]))
    for n in range(5):
        client.get(str(n), 'historical-odds')
    with pytest.raises(ValueError, match='ceiling'):
        client.get('excess', 'historical-odds')
    client.get('after', 'account', reserve_after=False)
    assert len(client.state['requests']) == 6
    with pytest.raises(ValueError, match='ceiling'):
        client.get('seventh', 'account', reserve_after=False)

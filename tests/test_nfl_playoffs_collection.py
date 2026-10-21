from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'scripts'))
from nfl_playoffs_exchange_history import ArchiveClient, inspect_response, plan_jobs
from nfl_playoffs_cohort_watch import attempts_used, validate_cohort, verify_frozen


def inputs():
    schedule = json.loads((ROOT / 'config/nfl_playoffs_history_2026.json').read_text())
    fixtures = []
    for i, fixture in enumerate(schedule['fixtures']):
        fixtures.append({'fixture': fixture, 'polymarket_startTime': fixture['scheduled_start'],
                         'polymarket_moneyline_feesEnabled': False,
                         'moneyline_identity_candidates': [{'kalshi_ticker': f'TEST-{i}-{j}',
                             'polymarket_token': str(i * 2 + j), 'normal_game_identity_matched': True}
                             for j in range(2)]})
    return {'sport': 'NFL', 'fixture_identity_count': 10, 'moneyline_identity_candidates': 20, 'fixtures': fixtures}, schedule


def test_full_moneyline_plan_has_contiguous_bounded_windows_and_prior_seed():
    review, schedule = inputs()
    identities, jobs = plan_jobs(review, schedule)
    assert len(identities) == 20 and len(jobs) == 152
    for identity in identities:
        assert identity['capture_start_at'] == identity['target_start_at'] - 86400
        expected_end = datetime.fromisoformat(identity['fixture']['scheduled_start']).timestamp() - 60
        assert identity['capture_end_at'] == expected_end
        for venue, name in [('kalshi', 'kalshi_ticker'), ('polymarket', 'polymarket_token')]:
            parts = sorted((j for j in jobs if j['venue'] == venue and j['identity'] == identity[name]), key=lambda j: j['part'])
            assert parts[0]['start_at'] == identity['capture_start_at']
            assert parts[-1]['end_at'] == expected_end
            assert all(j['end_at'] - j['start_at'] <= 3 * 86400 for j in parts)
            assert all(a['end_at'] == b['start_at'] for a, b in zip(parts, parts[1:]))
            if venue == 'kalshi':
                assert all(j['params']['include_latest_before_start'] == 'true' for j in parts)


def test_empty_query_coverage_does_not_invent_a_price_and_future_rows_rejected():
    _, jobs = plan_jobs(*inputs())
    job = next(j for j in jobs if j['venue'] == 'polymarket')
    env = {'status': 200, 'url': job['url'], 'params': job['params'], 'payload': {'history': []}}
    value = inspect_response(job, env)
    assert value['query_coverage_complete'] is True and value['contains_price_states'] is False
    env['payload']['history'] = [{'t': job['end_at'] + 1, 'p': .5}]
    with pytest.raises(ValueError, match='later_than_requested'):
        inspect_response(job, env)


def test_public_history_budget_persists_across_resumes_without_network(tmp_path):
    (tmp_path / 'attempts.jsonl').write_text('{}\n{}\n')
    client = ArchiveClient(tmp_path, 2)
    _, jobs = plan_jobs(*inputs())
    value = client.get(jobs[0])
    assert value['reason'] == 'persistent_public_request_budget_exhausted'
    assert client.count == 2 and attempts_used(tmp_path) == 2


def test_watcher_requires_complete_NFL_cohort_and_all_metadata(tmp_path):
    (tmp_path / 'summary.json').write_text(json.dumps({'sport': 'NFL', 'date': '2026-01-05', 'complete_census': True}))
    (tmp_path / 'metadata_coverage.json').write_text(json.dumps({'missing': []}))
    assert validate_cohort(tmp_path, '2026-01-05')['sport'] == 'NFL'
    with pytest.raises(ValueError, match='requested_NFL'):
        validate_cohort(tmp_path, '2026-01-06')
    (tmp_path / 'metadata_coverage.json').write_text(json.dumps({'missing': ['native-ticker']}))
    with pytest.raises(ValueError, match='missing_native'):
        validate_cohort(tmp_path, '2026-01-05')


def test_watcher_freeze_rejects_changed_collection_code(tmp_path):
    source = tmp_path / 'source.py'
    source.write_text('changed')
    with pytest.raises(ValueError, match='frozen_NFL'):
        verify_frozen({'frozen_sha256': {str(source): 'old-hash'}})


def test_offline_state_audit_uses_native_dollar_schema_and_checks_capture_hash(tmp_path):
    from nfl_playoffs_exchange_history import digest, save
    from nfl_playoffs_history_audit import audit
    ticker = 'KXNFLGAME-26JAN11LACNE-LAC'
    jobs = [
        {'venue': 'kalshi', 'identity': ticker, 'file': f'kalshi_parts/{ticker}.part0.json.gz',
         'url': f'https://external-api.kalshi.com/trade-api/v2/historical/markets/{ticker}/candlesticks',
         'params': {'start_ts': 100, 'end_ts': 200, 'period_interval': 1}, 'start_at': 100, 'end_at': 200},
        {'venue': 'polymarket', 'identity': '123', 'file': 'polymarket_parts/123.part0.json.gz',
         'url': 'https://clob.polymarket.com/prices-history',
         'params': {'startTs': 100, 'endTs': 200}, 'start_at': 100, 'end_at': 200}]
    payloads = [{'ticker': ticker, 'candlesticks': [{'end_period_ts': 120,
                 'yes_bid': {'close': '0.3600'}, 'yes_ask': {'close': '0.3700'}}]},
                {'history': [{'t': 125, 'p': .365}]}]
    for job, payload in zip(jobs, payloads):
        save(tmp_path / job['file'], {'status': 200, 'url': job['url'], 'params': job['params'], 'payload': payload})
    save(tmp_path / 'plan.json', {'sport': 'NFL', 'jobs': jobs,
         'identities': [{'kalshi_ticker': ticker, 'polymarket_token': '123',
                         'target_start_at': 100, 'capture_end_at': 200}]})
    save(tmp_path / 'coverage.json', {'plan_sha256': digest(tmp_path / 'plan.json'),
        'results': [{'file': job['file'], 'sha256': digest(tmp_path / job['file'])} for job in jobs],
        'full_requested_query_coverage': True, 'public_attempts': 2})
    result = audit(tmp_path)
    assert result['venues']['kalshi']['valid_unique_book_states'] == 1
    assert result['venues']['polymarket']['valid_unique_price_points'] == 1
    assert result['fee_model_applied'] is False
    (tmp_path / jobs[0]['file']).write_bytes(b'corrupted')
    with pytest.raises(ValueError, match='capture_hash_mismatch'):
        audit(tmp_path)

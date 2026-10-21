import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import cfb_full_exchange_acquire as collector


def test_full_collection_keeps_single_line_fixture_and_k_only():
    selection = {'selected': [{'fixture': {'startTime': '2026-09-05T15:00:00Z'},
                               'kalshi_tickers': ['KXTEST-GAME-YES']}]}
    jobs, tickers, tokens = collector.build_jobs(selection,
        {'KXTEST-GAME-YES': {'status': 'matched', 'token': '123'}},
        collector.START, collector.END, {'KXOTHER-GAME-NO': collector.END})
    assert set(tickers) == {'KXTEST-GAME-YES', 'KXOTHER-GAME-NO'}
    assert tokens == {'123'}
    parts = [job for job in jobs if job.key.startswith('KXTEST')]
    assert parts[0].params['start_ts'] == collector.START
    assert parts[-1].params['end_ts'] == collector.timestamp('2026-09-05T15:00:00Z')
    assert all(left.params['end_ts'] == right.params['start_ts'] for left, right in zip(parts, parts[1:]))
    assert all(job.params['end_ts'] - job.params['start_ts'] <= 3 * 86400 for job in parts)


def test_cached_failure_and_wrong_window_are_not_reused(tmp_path):
    job = collector.Job('polymarket', '123', 'https://example.invalid', {'startTs': 10, 'endTs': 20})
    path = tmp_path / job.filename
    record = {'status': 403, 'params': job.params, 'payload': {'history': []}}
    collector.atomic_json(path, record, compressed=True)
    assert collector.read_cache(path, job) is None
    record.update(status=200, params={'startTs': 10, 'endTs': 19})
    collector.atomic_json(path, record, compressed=True)
    assert collector.read_cache(path, job) is None
    record['params'] = job.params
    collector.atomic_json(path, record, compressed=True)
    assert collector.read_cache(path, job) == record


def test_successful_prior_cache_reused_without_network(tmp_path, monkeypatch):
    prior, out = tmp_path / 'prior', tmp_path / 'out'
    job = collector.Job('polymarket', '123', 'https://example.invalid', {'startTs': 10, 'endTs': 20})
    record = {'status': 200, 'params': job.params, 'retrieved_at': 42, 'payload': {'history': []}}
    collector.atomic_json(prior / job.venue / job.filename, record, compressed=True)
    def forbidden(*args, **kwargs):
        pytest.fail('Network should not be called for a valid reusable cache')
    monkeypatch.setattr(collector.requests, 'get', forbidden)
    result = collector.fetch(job, out, [prior], 1)
    assert result['cached']
    assert collector.read_cache(out / job.venue / job.filename, job) == record


def test_additional_ticker_metadata_and_duplicate_kickoff(tmp_path):
    path = tmp_path / 'tickers.json'
    path.write_text(json.dumps({'tickers': [{'ticker': 'KXTEST-A', 'start_time': '2026-09-05T15:00:00Z'}, 'KXTEST-B']}))
    extra = collector.additional_tickers(path, collector.END)
    assert extra['KXTEST-B'] is None
    selection = {'selected': [{'fixture': {'startTime': '2026-09-05T15:00:00Z'}, 'kalshi_tickers': ['KXTEST-A']}]}
    with pytest.raises(ValueError, match='conflicting kickoff'):
        collector.build_jobs(selection, {}, collector.START, collector.END, {'KXTEST-A': collector.END})


def test_capture_stops_at_report_end_for_future_games():
    jobs, _, _ = collector.build_jobs({'selected': []}, {}, collector.START, collector.END,
        {'KXFUTURE': collector.END + 14 * 86400, 'KXPAST': collector.START - 86400})
    assert not any(job.key.startswith('KXPAST') for job in jobs)
    assert max(job.params['end_ts'] for job in jobs) == collector.END
    assert len(jobs) == 3


def test_decision_windows_merge_and_cap_future_capture():
    jobs, tickers = collector.build_window_jobs([
        {'ticker': 'KXA', 'start_ts': 100, 'end_ts': 200},
        {'ticker': 'KXA', 'start_ts': 300, 'end_ts': 450},
        {'ticker': 'KXA', 'start_ts': 1000, 'end_ts': 1300},
        {'ticker': 'KXB', 'start_ts': 1400, 'end_ts': 1500},
    ], 150, 1200)
    assert set(tickers) == {'KXA'}
    assert [(job.params['start_ts'], job.params['end_ts']) for job in jobs] == [(150, 450), (1000, 1200)]
    assert jobs[0].key == 'KXA.gap150-450'
    assert all(job.params['include_latest_before_start'] == 'true' for job in jobs)


def test_long_decision_gap_splits_into_bounded_complete_requests():
    jobs, _ = collector.build_window_jobs([
        {'ticker': 'KXA', 'start_ts': collector.START, 'end_ts': collector.END}
    ], collector.START, collector.END)
    assert len(jobs) == 3
    assert jobs[0].params['start_ts'] == collector.START
    assert jobs[-1].params['end_ts'] == collector.END
    assert all(job.params['end_ts'] - job.params['start_ts'] <= 3 * 86400 for job in jobs)
    assert all(a.params['end_ts'] == b.params['start_ts'] for a, b in zip(jobs, jobs[1:]))
    with pytest.raises(ValueError):
        collector.build_window_jobs([{'ticker': 'KXA', 'start_ts': 200, 'end_ts': 100}], 0, 1000)

"""Complete-day provenance and date-specific assumptions precede outcome tests."""
import gzip
import hashlib
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import mlb_daily_cohort as daily
import mlb_exchange_acquire as exchange
import mlb_historical_fees as fees
import mlb_model_replay as replay
from mlb_public_day_acquire import BudgetExhausted, read, save


def scenario(start=0, end=2_000_000_000):
    return {'schema_version': 1, 'start_at': start, 'end_at': end,
            'reference': 'synthetic explicit dated scenario', 'historical_effective_date_verified': False,
            'kalshi_combo_maker_rate': .035, 'kalshi_leg_taker_rate': .07,
            'polymarket_rate_policy': 'native_market_schedule_unverified'}


def fixture_day(tmp_path):
    day = tmp_path / '2026-07-01'
    lo = daily.stamp('2026-07-01T05:00:00Z')
    hi = daily.stamp('2026-07-02T05:00:00Z')
    folder = day / 'partition'
    folder.mkdir(parents=True)
    rows = [{'trade_id': 'combo', 'ticker': 'KXMVETEST-A', 'count_fp': '10',
             'yes_price_dollars': '.3', 'taker_side': 'yes', 'created_time': '2026-07-01T06:00:00Z'},
            {'trade_id': 'ordinary', 'ticker': 'KXMLBGAME-X', 'created_time': '2026-07-01T06:00:00Z'},
            {'trade_id': 'boundary', 'ticker': 'KXMVETEST-B', 'created_time': '2026-07-02T05:00:00Z'}]
    env = {'http_status': 200, 'request': {'endpoint': '/historical/trades',
           'params': {'min_ts': int(lo) - 1, 'max_ts': int(hi) + 1, 'limit': 1000}},
           'payload': {'trades': rows, 'cursor': ''}}
    page = folder / 'page_00000.json.gz'
    save(page, env)
    manifest = {'start_at': lo, 'end_at': hi, 'endpoint': '/historical/trades', 'complete': True,
                'pages': [{'path': page.name, 'sha256': daily.sha(page), 'rows': len(rows)}],
                'raw_rows': len(rows)}
    path = folder / 'manifest.json'
    save(path, manifest)
    return day, path, manifest, page, env, lo, hi


def test_complete_public_day_keeps_only_unique_in_window_combos(tmp_path):
    day, path, manifest, page, env, lo, hi = fixture_day(tmp_path)
    out = tmp_path / 'cohort'; out.mkdir()
    db, got_lo, got_hi, sources, counts = daily.index_tape(day, '2026-07-01', out)
    assert (got_lo, got_hi) == (lo, hi)
    assert db.execute('SELECT id FROM trades').fetchall() == [('combo',)]
    assert counts['public_prints'] == 2 and counts['unique_combo_prints'] == 1
    assert sources[0]['method'] == 'census' and sources[0]['sample_weight_in_replay'] == 1
    db.close()


@pytest.mark.parametrize('problem', ['incomplete', 'gap', 'page_hash', 'cursor', 'query'])
def test_truncated_or_changed_capture_cannot_become_census(tmp_path, problem):
    day, path, manifest, page, env, lo, hi = fixture_day(tmp_path)
    if problem == 'incomplete':
        manifest['complete'] = False
    elif problem == 'gap':
        manifest['end_at'] -= 1
    elif problem == 'page_hash':
        manifest['pages'][0]['sha256'] = 'bad'
    elif problem == 'cursor':
        env['payload']['cursor'] = 'more-not-collected'
        save(page, env); manifest['pages'][0]['sha256'] = daily.sha(page)
    elif problem == 'query':
        env['request']['params']['min_ts'] += 10
        save(page, env); manifest['pages'][0]['sha256'] = daily.sha(page)
    save(path, manifest)
    out = tmp_path / 'cohort'; out.mkdir()
    with pytest.raises(ValueError):
        daily.index_tape(day, '2026-07-01', out)
    assert not (out / 'summary.json').exists()


def test_metadata_budget_resume_uses_cached_responses_and_historical_route(tmp_path):
    class Client:
        def __init__(self, budget): self.count = 0; self.budget = budget
        def get(self, endpoint, params):
            if self.count >= self.budget: raise BudgetExhausted()
            self.count += 1
            return {'http_status': 200, 'request': {'endpoint': endpoint, 'params': params},
                    'payload': {'markets': [] if endpoint == '/markets' else [{'ticker': 'A'}]}}
    first = Client(1)
    result, missing, stopped = daily.recover_metadata(['A'], tmp_path / 'cache', first)
    assert result == {} and missing == ['A'] and stopped and first.count == 1
    second = Client(1)
    result, missing, stopped = daily.recover_metadata(['A'], tmp_path / 'cache', second)
    assert result == {'A': {'ticker': 'A'}} and not missing and not stopped and second.count == 1
    cached = Client(0)
    result, missing, stopped = daily.recover_metadata(['A'], tmp_path / 'cache', cached)
    assert not missing and not stopped and cached.count == 0


def test_historical_first_still_falls_back_to_current_for_unreturned_tickers(tmp_path):
    class Client:
        def __init__(self): self.count = 0; self.calls = []
        def get(self, endpoint, params):
            self.count += 1; self.calls.append((endpoint, params['tickers']))
            return {'http_status': 200, 'request': {'endpoint': endpoint, 'params': params},
                    'payload': {'markets': [{'ticker': 'A' if endpoint == '/historical/markets' else 'B'}]}}
    client = Client()
    result, missing, stopped = daily.recover_metadata(['A', 'B'], tmp_path / 'cache', client,
                                                      historical_first=True)
    assert client.calls == [('/historical/markets', 'A,B'), ('/markets', 'B')]
    assert set(result) == {'A', 'B'} and not missing and not stopped


def test_parallel_shared_client_never_overspends_and_resumes_cached_batches(tmp_path, monkeypatch):
    import threading
    import time
    import mlb_public_day_acquire as public
    active = 0; peak = 0; actual = 0; mutex = threading.Lock()
    class Session:
        def get(self, url, params, **kwargs):
            nonlocal active, peak, actual
            assert url.endswith('/historical/markets')
            with mutex:
                actual += 1; active += 1; peak = max(peak, active)
            time.sleep(.015)
            with mutex: active -= 1
            payload = {'markets': [{'ticker': ticker} for ticker in params['tickers'].split(',')]}
            class Response:
                status_code = 200
                content = json.dumps(payload).encode()
                def json(self): return payload
            return Response()
        def close(self): pass
    monkeypatch.setattr(public.requests, 'Session', Session)
    monkeypatch.setattr(public, 'pace', lambda: None)
    tickers = [f'T{index:04d}' for index in range(500)]
    client = public.Client(tmp_path, 3)
    result, missing, stopped = daily.recover_metadata(tickers, tmp_path / 'cache', client,
                                                      workers=4, historical_first=True)
    assert actual == client.count == 3 and 1 < peak <= 4
    assert len(result) == 300 and len(missing) == 200 and stopped
    resumed = public.Client(tmp_path, 2)
    result, missing, stopped = daily.recover_metadata(tickers, tmp_path / 'cache', resumed,
                                                      workers=4, historical_first=True)
    assert actual == 5 and resumed.count == 2
    assert len(result) == 500 and not missing and not stopped


def test_historical_fee_schedule_uses_half_open_dated_native_override(tmp_path):
    data = scenario(100, 1000)
    data['kalshi_rate_overrides'] = [{'kind': 'leg_taker', 'series': 'KXMLBGAME',
                                    'start_at': 500, 'end_at': 1000, 'rate': .035,
                                    'reference': 'synthetic native effective record', 'verified': True}]
    path = tmp_path / 'fees.json'; save(path, data)
    loaded = fees.load_fee_scenario(path)
    assert fees.kalshi_rate(loaded, 'KXMLBGAME-X', 499.99, 'leg_taker')[0] == .07
    rate, provenance = fees.kalshi_rate(loaded, 'KXMLBGAME-X', 500, 'leg_taker')
    assert rate == .035 and provenance['verified']
    assert fees.kalshi_rate(loaded, 'KXMLBSPREAD-X', 500, 'leg_taker')[0] == .07
    with pytest.raises(ValueError, match='does_not_cover'):
        fees.kalshi_rate(loaded, 'KXMLBGAME-X', 1000, 'leg_taker')
    data['kalshi_rate_overrides'].append(dict(data['kalshi_rate_overrides'][0]))
    save(path, data)
    with pytest.raises(ValueError, match='overlapping'):
        fees.load_fee_scenario(path)


def test_unverified_native_fee_snapshot_cannot_claim_verified_historical_net_pnl(tmp_path):
    data = scenario(); data['historical_effective_date_verified'] = True
    path = tmp_path / 'fees.json'; save(path, data)
    with pytest.raises(ValueError, match='cannot_be_verified'):
        fees.load_fee_scenario(path)


def test_combo_shard_fee_series_does_not_collapse_into_parent_series():
    data = scenario(100, 1000)
    data['kalshi_rate_overrides'] = [
        {'kind': 'combo_maker', 'series': 'KXMVECROSSCATEGORY', 'start_at': 100,
         'end_at': 1000, 'rate': .01, 'reference': 'parent', 'verified': True},
        {'kind': 'combo_maker', 'series': 'KXMVECROSSCATEGORY-SHARD1', 'start_at': 100,
         'end_at': 1000, 'rate': .02, 'reference': 'shard1', 'verified': True}]
    assert fees.kalshi_rate(data, 'KXMVECROSSCATEGORY-EVENT-OUTCOME', 500, 'combo_maker')[0] == .01
    rate, basis = fees.kalshi_rate(data, 'KXMVECROSSCATEGORY-SHARD1-EVENT-OUTCOME', 500, 'combo_maker')
    assert rate == .02 and basis['series'] == 'KXMVECROSSCATEGORY-SHARD1'
    assert fees.kalshi_rate(data, 'KXMVECROSSCATEGORY-SHARD2-EVENT-OUTCOME', 500, 'combo_maker')[0] == .035


def test_candidate_schema_preserves_unknown_outcome_and_explicit_fee_scenario(tmp_path):
    day, path, manifest, page, env, lo, hi = fixture_day(tmp_path)
    out = tmp_path / 'cohort'; out.mkdir()
    db, lo, hi, sources, counts = daily.index_tape(day, '2026-07-01', out)
    legs = ['KXMLBGAME-26JUL011305NYYBAL-NYY', 'KXMLBGAME-26JUL011840SDCIN-SD']
    markets = {'KXMVETEST-A': {'ticker': 'KXMVETEST-A', 'status': 'closed',
               'mve_selected_legs': [{'market_ticker': ticker, 'side': 'yes'} for ticker in legs]}}
    summary = daily.write_cohort(db, markets, {ticker: {} for ticker in legs}, out, lo, hi,
                                sources, counts, scenario(lo, hi), '2026-07-01')
    assert summary['complete_census'] and summary['fullgame_pregame_proxy_prints'] == 1
    with gzip.open(out / 'candidate_trades.jsonl.gz', 'rt') as handle:
        candidate = json.loads(handle.readline())
    assert candidate['settlement_value'] is None and candidate['seller_pnl_dollars'] is None
    assert candidate['maker_fee_dollars'] > 0 and 'UNVERIFIED RESEARCH SCENARIO' in candidate['fee_basis']
    db.close()


def test_exchange_discovery_bounds_follow_fixture_dates_instead_of_september():
    lo, hi = exchange.gamma_date_bounds(['KXMLBGAME-26JUL011305NYYBAL-NYY'])
    assert lo.startswith('2026-06-17') and hi.startswith('2026-07-15')


def test_exchange_blends_are_fixed_at_leg_level_and_require_both_sources(tmp_path):
    ticker = 'KXMLBGAME-26JUL011305NYYBAL-NYY'
    save(tmp_path / 'polymarket_mapping_reviewed.json', {ticker: {'status': 'matched', 'token': '123', 'fee_rate': .03}})
    (tmp_path / 'kalshi_parts').mkdir(); (tmp_path / 'polymarket').mkdir()
    save(tmp_path / 'kalshi_parts' / (ticker + '.part0.json.gz'),
         {'status': 200, 'params': {'start_ts': 100, 'end_ts': 300, 'period_interval': 1},
          'payload': {'ticker': ticker, 'candlesticks': [{'end_period_ts': 120,
                      'yes_bid': {'close_dollars': .39}, 'yes_ask': {'close_dollars': .41}}]}})
    save(tmp_path / 'polymarket/123.json.gz', {'status': 200,
         'params': {'startTs': 100, 'endTs': 300}, 'payload': {'history': [{'t': 120, 'p': .6}]}})
    provider = replay.SourceFairs(tmp_path, fee_scenario=scenario(100, 400))
    available, context, errors = provider.fair(ticker, 180)
    assert available['exchange_blend_equal'][0].point == pytest.approx(.5)
    assert available['exchange_blend_pm75'][0].point == pytest.approx(.55)
    assert context['kalshi']['fee_basis']['taker_rate'] == .07
    assert 'pinnacle' not in available
    assert context['exchange_blend_pm75']['required_sources'] == ['kalshi', 'polymarket']
    unavailable, _, errors = provider.fair(ticker, 179)
    assert 'exchange_blend_pm75' not in unavailable
    assert errors['exchange_blend_pm75'] == 'two_exchange_intersection_missing'

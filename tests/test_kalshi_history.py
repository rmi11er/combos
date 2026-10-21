import gzip
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from combos.kalshi_history import KalshiHistory, _quote_close
from combos.pricing import fee_expanded_book


TICKER = 'KXNCAAFGAME-26SEP05ABCXYZ-ABC'


def candle(at, bid=.48, ask=.52):
    return {'end_period_ts': at, 'yes_bid': {'close_dollars': bid}, 'yes_ask': {'close_dollars': ask}}


def capture(path, start, end, rows, status=200, seed=False, legacy=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    env = {'params': {'start_ts': start, 'end_ts': end, 'period_interval': 1,
                      'include_latest_before_start': seed}, 'payload': {'candlesticks': rows}}
    if not legacy:
        env['status'] = status
    with gzip.open(path, 'wt') as f:
        json.dump(env, f)


def part(root, n=0):
    return root/'kalshi_parts'/f'{TICKER}.part{n}.json.gz'


def test_independent_pricing_is_causal_and_does_not_need_other_venues(tmp_path):
    capture(part(tmp_path), 0, 300, [candle(60), candle(120, .6, .62)])
    h = KalshiHistory(tmp_path, fallback_dirs=[])
    with pytest.raises(ValueError, match='no_prior'):
        h.at(TICKER, 119)
    quote = h.at(TICKER, 179)
    assert quote['source_at'] == 60 and quote['raw_age_seconds'] == 119
    assert quote['interval']['point'] == .5
    assert quote['interval']['upper'] == fee_expanded_book(.48, .52, .07).upper
    assert quote['available_at'] == 120
    assert 'depth_imputation' in quote['depth_basis']
    assert h.at(TICKER, 180)['source_at'] == 120
    with pytest.raises(ValueError, match='uncovered'):
        h.at(TICKER, 361)


def test_legacy_daily_fallback_does_not_cover_other_days(tmp_path):
    fallback = tmp_path/'old'
    capture(fallback/(TICKER+'.json.gz'), 86400, 172800, [candle(86400)], legacy=True)
    h = KalshiHistory(tmp_path, fallback_dirs=[fallback])
    assert h.at(TICKER, 90000)['source_provenance']['http_status_basis'] == 'legacy_success_capture_schema'
    with pytest.raises(ValueError, match='uncovered'):
        h.at(TICKER, 80000)


def test_missing_chunk_is_not_silently_bridged(tmp_path):
    capture(part(tmp_path), 0, 100, [candle(80)])
    capture(part(tmp_path, 1), 100, 200, [], status=500)
    capture(part(tmp_path, 2), 200, 300, [candle(250)])
    h = KalshiHistory(tmp_path, fallback_dirs=[])
    with pytest.raises(ValueError, match='uncovered'):
        h.at(TICKER, 210)
    with pytest.raises(ValueError, match='no_prior'):
        h.at(TICKER, 280)
    assert h.at(TICKER, 310)['source_at'] == 250


def test_explicit_latest_before_start_seed_is_supported(tmp_path):
    capture(part(tmp_path), 100, 300, [candle(50)], seed=True)
    h = KalshiHistory(tmp_path, fallback_dirs=[])
    assert h.at(TICKER, 180)['source_at'] == 50
    with pytest.raises(ValueError, match='uncovered'):
        h.at(TICKER, 150)


def test_pre_window_state_without_seed_permission_is_not_used(tmp_path):
    capture(part(tmp_path), 100, 300, [candle(50)], seed=False)
    h = KalshiHistory(tmp_path, fallback_dirs=[])
    with pytest.raises(ValueError, match='no_prior'):
        h.at(TICKER, 180)


@pytest.mark.parametrize('bad,error', [(candle(120, .7, .6), 'crossed'),
                                      ({'end_period_ts': 120}, 'missing_latest')])
def test_invalid_latest_quote_does_not_fall_back(tmp_path, bad, error):
    capture(part(tmp_path), 0, 300, [candle(60), bad])
    with pytest.raises(ValueError, match=error):
        KalshiHistory(tmp_path, fallback_dirs=[]).at(TICKER, 200)


def test_boundary_sentinel_does_not_erase_quote_but_conflicts_fail(tmp_path):
    capture(part(tmp_path), 0, 100, [candle(100)])
    capture(part(tmp_path, 1), 100, 200, [{'end_period_ts': 100}])
    h = KalshiHistory(tmp_path, fallback_dirs=[])
    assert h.at(TICKER, 180)['interval']['point'] == .5
    capture(part(tmp_path, 1), 100, 200, [candle(100, .7, .8)])
    h.refresh()
    with pytest.raises(ValueError, match='conflicting'):
        h.at(TICKER, 180)


def test_refresh_includes_new_capture_files(tmp_path):
    capture(part(tmp_path), 0, 100, [candle(50)])
    h = KalshiHistory(tmp_path, fallback_dirs=[])
    assert h.at(TICKER, 140)['source_at'] == 50
    capture(part(tmp_path, 1), 100, 200, [candle(150)])
    h.refresh()
    assert h.at(TICKER, 220)['source_at'] == 150


def test_focused_gap_capture_is_discovered(tmp_path):
    path = tmp_path/'kalshi_parts'/f'{TICKER}.gap100-200.json.gz'
    capture(path, 100, 200, [candle(90)], seed=True)
    quote = KalshiHistory(tmp_path, fallback_dirs=[]).at(TICKER, 180)
    assert quote['source_at'] == 90
    assert quote['coverage_interval'] == [100., 200.]


def test_unverified_request_coverage_is_not_accepted(tmp_path):
    p = part(tmp_path); p.parent.mkdir(parents=True)
    with gzip.open(p, 'wt') as f:
        json.dump({'status': 200, 'payload': {'candlesticks': [candle(60)]}}, f)
    with pytest.raises(ValueError, match='no_covered'):
        KalshiHistory(tmp_path, fallback_dirs=[]).at(TICKER, 180)


def schema_capture(path, rows, schema=None, historical=False):
    capture(path, 0, 300, rows)
    with gzip.open(path, 'rt') as handle: env = json.load(handle)
    if historical:
        env['url'] = 'https://external-api.kalshi.com/trade-api/v2/historical/markets/' + TICKER + '/candlesticks'
    if schema:
        env['candle_price_schema'] = schema
        env['candle_schema_reference'] = 'synthetic:explicitly documented legacy integer-cent response'
    with gzip.open(path, 'wt') as handle: json.dump(env, handle)


def test_native_historical_fixed_point_close_is_dollars_with_endpoint_provenance(tmp_path):
    # Unmodified quote objects from NFL native capture
    # KXNFLGAME-26JAN11LACNE-LAC.part2.json.gz, first row at 1768024800.
    # Timestamp is moved into this test's synthetic coverage interval only.
    row = {'end_period_ts': 60,
           'yes_bid': {'close': '0.3600', 'high': '0.3600', 'low': '0.3600', 'open': '0.3600'},
           'yes_ask': {'close': '0.3700', 'high': '0.3700', 'low': '0.3700', 'open': '0.3700'},
           'volume': '1098.00', 'open_interest': '361203.00'}
    schema_capture(part(tmp_path), [row], historical=True)
    quote = KalshiHistory(tmp_path, fallback_dirs=[]).at(TICKER, 120)
    assert (quote['yes_bid'], quote['yes_ask'], quote['interval']['point']) == pytest.approx((.36, .37, .365))
    assert quote['source_provenance']['candle_price_schema'] == 'historical_decimal_dollars'
    assert quote['source_provenance']['quote_price_encodings'] == {'historical_decimal_dollars': 2}
    assert quote['source_provenance']['candle_schema_reference'].endswith('/get-historical-market-candlesticks')


@pytest.mark.parametrize('raw,expected', [('0.0000', 0.), ('0.0100', .01), ('0.3600', .36), ('1.0000', 1.)])
def test_historical_decimal_dollar_boundaries_are_not_rescaled(raw, expected):
    assert _quote_close({'close': raw}, 'historical_decimal_dollars')[0] == expected


@pytest.mark.parametrize('raw,expected', [(0, 0.), (1, .01), (36, .36), (100, 1.)])
def test_legacy_integer_cents_require_explicit_schema(raw, expected):
    assert _quote_close({'close': raw}, 'legacy_integer_cents')[0] == expected
    with pytest.raises(ValueError, match='ambiguous'):
        _quote_close({'close': raw}, 'explicit_close_dollars_only')


@pytest.mark.parametrize('raw', ['1', '36', 1, 0.36, True, None, 'NaN', '1.1000', '.36'])
def test_historical_units_are_never_guessed_from_magnitude_or_ambiguous_string(raw):
    with pytest.raises(ValueError):
        _quote_close({'close': raw}, 'historical_decimal_dollars')


def test_explicit_dollar_field_is_authoritative_but_conflicting_known_alias_fails():
    assert _quote_close({'close_dollars': '1'}, 'explicit_close_dollars_only')[0] == 1.
    assert _quote_close({'close_dollars': '.36', 'close': 36}, 'legacy_integer_cents')[0] == .36
    with pytest.raises(ValueError, match='conflicting'):
        _quote_close({'close_dollars': '.36', 'close': '0.3700'}, 'historical_decimal_dollars')
    with pytest.raises(ValueError):
        _quote_close({'close_dollars': None, 'close': '0.3600'}, 'historical_decimal_dollars')


def test_ambiguous_latest_historical_quote_does_not_fall_back_to_old_valid_quote(tmp_path):
    rows = [{'end_period_ts': 60, 'yes_bid': {'close': '0.3600'}, 'yes_ask': {'close': '0.3700'}},
            {'end_period_ts': 120, 'yes_bid': {'close': '1'}, 'yes_ask': {'close': '1'}}]
    schema_capture(part(tmp_path), rows, historical=True)
    history = KalshiHistory(tmp_path, fallback_dirs=[])
    with pytest.raises(ValueError, match='missing_latest'):
        history.at(TICKER, 180)
    assert history.load(TICKER)['sources'][0]['quote_parse_errors'] == {'invalid_historical_decimal_dollar_close': 1}


def test_legacy_integer_capture_needs_referenced_schema_to_interpret_one_cent(tmp_path):
    rows = [{'end_period_ts': 60, 'yes_bid': {'close': 1}, 'yes_ask': {'close': 2}}]
    schema_capture(part(tmp_path), rows, schema='legacy_integer_cents')
    quote = KalshiHistory(tmp_path, fallback_dirs=[]).at(TICKER, 120)
    assert quote['yes_bid'] == .01 and quote['yes_ask'] == .02

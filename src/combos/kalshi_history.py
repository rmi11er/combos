"""Independent, historical-only Kalshi candle pricing with interval coverage.

Successful request coverage is separate from last-price age. No Polymarket or
Pinnacle mapping, order-book size or live-feed health is inferred. Instantiate
after collection, or call refresh(), to include newly acquired files.
"""
from array import array
from bisect import bisect_right
from collections import OrderedDict, defaultdict
from dataclasses import asdict
import gzip
import hashlib
import json
import math
from pathlib import Path
import re
from urllib.parse import urlsplit

from .pricing import fee_expanded_book


def _finite(value, name):
    if isinstance(value, bool):
        raise ValueError('invalid '+name)
    try:
        value = float(value)
    except (TypeError, ValueError):
        raise ValueError('invalid '+name) from None
    if not math.isfinite(value):
        raise ValueError('invalid '+name)
    return value


def _capture_price_schema(env, ticker):
    """Resolve bare close units from an explicit native schema, never magnitude."""
    explicit = env.get('candle_price_schema')
    reference = env.get('candle_schema_reference')
    if explicit is not None:
        if explicit not in ('historical_decimal_dollars', 'legacy_integer_cents') or not reference:
            raise ValueError('unsupported_or_unreferenced_candle_price_schema')
        return explicit, reference
    url = urlsplit(env.get('url', ''))
    if (url.hostname in ('external-api.kalshi.com', 'api.elections.kalshi.com', 'api.kalshi.com') and
            url.path == '/trade-api/v2/historical/markets/' + ticker + '/candlesticks'):
        return 'historical_decimal_dollars', 'https://docs.kalshi.com/api-reference/historical/get-historical-market-candlesticks'
    return 'explicit_close_dollars_only', 'Unit-bearing close_dollars field; bare close units unverified'


def _bare_close(value, schema):
    if schema == 'historical_decimal_dollars':
        # The historical endpoint specifies fixed-point dollar strings. A bare
        # "1", integer 1 or float 1.0 is not that schema and is not guessed.
        if not isinstance(value, str) or not re.fullmatch(r'(?:0|1)\.\d+', value):
            raise ValueError('invalid_historical_decimal_dollar_close')
        result = _finite(value, 'historical dollar close')
    elif schema == 'legacy_integer_cents':
        if type(value) is not int or not 0 <= value <= 100:
            raise ValueError('invalid_legacy_integer_cent_close')
        result = value / 100.
    else:
        raise ValueError('ambiguous_candle_close_units')
    if not 0 <= result <= 1:
        raise ValueError('candle_close_outside_probability_range')
    return result


def _quote_close(ohlc, schema):
    if not isinstance(ohlc, dict):
        raise ValueError('missing_quote_object')
    if 'close_dollars' in ohlc:
        result = _finite(ohlc['close_dollars'], 'close_dollars')
        if not 0 <= result <= 1:
            raise ValueError('candle_close_outside_probability_range')
        if 'close' in ohlc and schema != 'explicit_close_dollars_only':
            if _bare_close(ohlc['close'], schema) != result:
                raise ValueError('conflicting_candle_unit_aliases')
        return result, 'explicit_close_dollars'
    return _bare_close(ohlc.get('close'), schema), schema


class KalshiHistory:
    def __init__(self, data_run, fallback_dirs=None, publication_delay=60., taker_rate=.07, cache_size=512):
        self.data_run = Path(data_run)
        root = Path(__file__).resolve().parents[2]
        self.fallback_dirs = [Path(p) for p in (fallback_dirs if fallback_dirs is not None else
                             (root/'data/raw/candles', root/'data/raw/candles_retry'))]
        self.publication_delay = _finite(publication_delay, 'publication delay')
        self.taker_rate = _finite(taker_rate, 'taker rate')
        if self.publication_delay < 0 or self.taker_rate < 0 or cache_size < 1:
            raise ValueError('invalid history configuration')
        self.cache_size = cache_size
        self.refresh()

    def refresh(self):
        self._cache = OrderedDict(); self._files = defaultdict(list)
        for path in sorted((self.data_run/'kalshi_parts').glob('*.json.gz')):
            ticker = path.name.split('.part')[0].split('.gap')[0]
            self._files[ticker].append(path)

    def load(self, ticker):
        """Load compact states and verified request ranges for one native ticker."""
        if not isinstance(ticker, str) or not ticker or '/' in ticker or '\\' in ticker:
            raise ValueError('invalid ticker')
        if ticker in self._cache:
            self._cache.move_to_end(ticker)
            return self._cache[ticker]
        paths = [*self._files.get(ticker, [])]
        paths.extend(p/(ticker+'.json.gz') for p in self.fallback_dirs if (p/(ticker+'.json.gz')).exists())
        captures = []; failures = []
        for path in paths:
            try:
                raw = path.read_bytes(); env = json.loads(gzip.decompress(raw))
            except (OSError, ValueError, EOFError):
                failures.append({'file': str(path), 'reason': 'unreadable_capture'}); continue
            payload = env.get('payload'); params = env.get('params')
            if env.get('status', 200) != 200 or not isinstance(payload, dict) or not isinstance(payload.get('candlesticks'), list):
                failures.append({'file': str(path), 'reason': 'unsuccessful_capture'}); continue
            if not isinstance(params, dict):
                failures.append({'file': str(path), 'reason': 'missing_request_coverage'}); continue
            try:
                lo, hi = _finite(params['start_ts'], 'capture start'), _finite(params['end_ts'], 'capture end')
                if lo >= hi or int(params['period_interval']) != 1:
                    raise ValueError('unsupported candle interval')
            except (KeyError, ValueError, TypeError):
                failures.append({'file': str(path), 'reason': 'invalid_request_coverage'}); continue
            if payload.get('ticker', ticker) != ticker:
                raise ValueError('capture_ticker_mismatch')
            schema, schema_reference = _capture_price_schema(env, ticker)
            seed = params.get('include_latest_before_start') in (True, 'true', 'True', 1)
            provenance = {'file': str(path), 'sha256': hashlib.sha256(raw).hexdigest(),
                          'request_start_at': lo, 'request_end_at': hi,
                          'include_latest_before_start': seed, 'retrieved_at': env.get('retrieved_at'),
                          'request_url': env.get('url'), 'candle_price_schema': schema,
                          'candle_schema_reference': schema_reference, 'quote_price_encodings': {}, 'quote_parse_errors': {},
                          'http_status_basis': 'explicit_200' if 'status' in env else 'legacy_success_capture_schema'}
            captures.append({'lo': lo, 'hi': hi, 'seed': seed, 'schema': schema, 'source': provenance, 'rows': payload['candlesticks']})
        if not captures:
            raise ValueError('no_covered_kalshi_history')
        # Each connected request interval is independent: never carry a price
        # across an uncollected gap, even if a later request returned no quotes.
        groups = []
        for capture in sorted(captures, key=lambda c: (c['lo'], c['hi'])):
            if not groups or capture['lo'] > groups[-1]['hi']:
                groups.append({'lo': capture['lo'], 'hi': capture['hi'], 'captures': []})
            group = groups[-1]; group['hi'] = max(group['hi'], capture['hi']); group['captures'].append(capture)
        segments = []; sources = []
        for group in groups:
            points = {}
            for capture in group['captures']:
                source = len(sources); sources.append(capture['source'])
                for row in capture['rows']:
                    at = _finite(row['end_period_ts'], 'candle end')
                    if at > capture['hi'] or (at < capture['lo'] and not capture['seed']):
                        continue
                    try:
                        bid, bid_encoding = _quote_close(row.get('yes_bid'), capture['schema'])
                        ask, ask_encoding = _quote_close(row.get('yes_ask'), capture['schema'])
                        for encoding in (bid_encoding, ask_encoding):
                            counts = capture['source']['quote_price_encodings']
                            counts[encoding] = counts.get(encoding, 0) + 1
                    except (KeyError, ValueError, TypeError) as exc:
                        errors = capture['source']['quote_parse_errors']; reason = str(exc)
                        errors[reason] = errors.get(reason, 0) + 1
                        bid = ask = math.nan
                    prior = points.get(at)
                    if prior is not None:
                        previous_valid = math.isfinite(prior[0]) and math.isfinite(prior[1])
                        valid = math.isfinite(bid) and math.isfinite(ask)
                        if valid and previous_valid and (bid, ask) != prior[:2]:
                            raise ValueError('conflicting_candle_close')
                        # Boundary sentinels can omit quotes, but cannot overwrite
                        # an actual quote at that exact same timestamp.
                        if previous_valid:
                            continue
                    points[at] = (bid, ask, source)
            times = sorted(points)
            segments.append({'lo': group['lo'], 'hi': group['hi'], 'times': array('d', times),
                             'bids': array('d', (points[t][0] for t in times)),
                             'asks': array('d', (points[t][1] for t in times)),
                             'source_ids': array('I', (points[t][2] for t in times))})
        loaded = {'segments': segments, 'sources': sources, 'ignored_captures': failures}
        self._cache[ticker] = loaded
        if len(self._cache) > self.cache_size:
            self._cache.popitem(last=False)
        return loaded

    def at(self, ticker, at):
        decision = _finite(at, 'decision time'); cutoff = decision-self.publication_delay
        history = self.load(ticker)
        segment = next((s for s in history['segments'] if s['lo'] <= cutoff <= s['hi']), None)
        if segment is None:
            raise ValueError('uncovered_kalshi_timestamp')
        index = bisect_right(segment['times'], cutoff)-1
        if index < 0:
            raise ValueError('no_prior_kalshi_state')
        bid, ask = segment['bids'][index], segment['asks'][index]
        if not math.isfinite(bid) or not math.isfinite(ask):
            raise ValueError('missing_latest_kalshi_book')
        if not 0 <= bid <= ask <= 1:
            raise ValueError('crossed_or_invalid_kalshi_book')
        source_at = segment['times'][index]
        interval = fee_expanded_book(bid, ask, self.taker_rate)
        return {'interval': asdict(interval), 'source_at': source_at, 'raw_age_seconds': decision-source_at,
                'available_at': source_at+self.publication_delay, 'decision_at': decision,
                'yes_bid': bid, 'yes_ask': ask, 'historical_only': True,
                'publication_delay_seconds': self.publication_delay,
                'source_provenance': history['sources'][segment['source_ids'][index]],
                'coverage_interval': [segment['lo'], segment['hi']],
                'fee_basis': {'taker_rate': self.taker_rate, 'historical_assumption': True},
                'depth_basis': 'not_required_for_single_venue_interval; no_depth_imputation',
                'freshness_basis': 'candle_state_carry_forward_within_captured_interval; upstream_heartbeat_unverified'}

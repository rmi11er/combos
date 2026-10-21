"""Read-only v4 acquisition. Raw history stays raw until mapping is reviewed."""
import gzip, hashlib, json, os, time, math
from pathlib import Path
import requests

class OddsPapi:
    BASE = 'https://api.oddspapi.io/v4'
    ENDPOINTS = {'account', 'sports', 'tournaments', 'markets', 'bookmakers', 'fixtures', 'fixture', 'historical-odds', 'odds', 'odds-by-tournaments'}

    def __init__(self, cache, api_key=None, session=None, request_budget=None):
        self.cache = Path(cache); self.cache.mkdir(parents=True, exist_ok=True)
        self.key = api_key or os.environ.get('ODDSPAPI_API_KEY')
        self.session = session or requests.Session(); self.last_request = float('-inf')
        self.request_budget = request_budget

    def get(self, endpoint, params=None, refresh=False, max_cache_age_seconds=None):
        if endpoint not in self.ENDPOINTS: raise ValueError('read endpoint not allowed')
        if max_cache_age_seconds is not None and (not math.isfinite(max_cache_age_seconds) or max_cache_age_seconds < 0):
            raise ValueError('invalid cache age')
        params = dict(params or {})
        if any('key' in k.lower() or 'token' in k.lower() for k in params):
            raise ValueError('credentials must come from ODDSPAPI_API_KEY')
        request = {'endpoint': endpoint, 'params': params}
        digest = hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest()
        folder = self.cache/digest; folder.mkdir(exist_ok=True)
        versions = sorted(folder.glob('*.json.gz'))
        if versions and not refresh:
            with gzip.open(versions[-1], 'rt') as f: cached = json.load(f)
            age = time.time()-cached['retrieved_at']
            if max_cache_age_seconds is None or 0 <= age <= max_cache_age_seconds:
                return cached  # Preserve original receipt time, including on cache hits.
        if not self.key: raise ValueError('ODDSPAPI_API_KEY is not configured')
        for attempt in range(5):
            # One process, conservative endpoint pacing. CLI is sequential.
            time.sleep(max(0., 5.05-(time.monotonic()-self.last_request)))
            self.last_request = time.monotonic()
            if self.request_budget is not None:
                self.request_budget.claim(endpoint)  # Count attempts/retries, not just successful responses.
            request_started_at = time.time()
            try:
                response = self.session.get(self.BASE+'/'+endpoint, params={**params, 'apiKey': self.key}, timeout=45)
            except requests.RequestException:
                if attempt == 4: raise RuntimeError('OddsPapi transport failed; credential-bearing URL suppressed') from None
                continue
            if response.status_code == 429 or response.status_code >= 500:
                time.sleep(min(16, 2**attempt)); continue
            if response.status_code != 200:
                raise RuntimeError(f'OddsPapi HTTP {response.status_code}; response body and URL suppressed')
            try: payload = redact_credentials(response.json())
            except ValueError: raise RuntimeError('OddsPapi returned invalid JSON') from None
            envelope = {'request': request, 'request_started_at': request_started_at,
                        'retrieved_at': time.time(), 'etag': response.headers.get('ETag'),
                        'response_headers': {k:response.headers.get(k) for k in
                            ('Date','Age','Cache-Control','ETag','Last-Modified','CF-Cache-Status','X-Cache')
                            if response.headers.get(k) is not None}, 'payload': payload}
            path = folder/f'{time.time_ns()}.json.gz'
            with gzip.open(path.with_suffix('.tmp'), 'wt') as f:
                json.dump(envelope, f, separators=(',', ':'), allow_nan=False)
            path.with_suffix('.tmp').replace(path)
            return envelope
        raise RuntimeError('OddsPapi retries exhausted')


def redact_credentials(value):
    """The account endpoint echoes the API key. Never archive or return it."""
    if isinstance(value, dict):
        return {k: '[REDACTED]' if k.lower().replace('_','').replace('-','') in
                ('apikey','accesstoken','refreshtoken','authorization','password','secret')
                else redact_credentials(v) for k,v in value.items()}
    if isinstance(value, list):return [redact_credentials(v) for v in value]
    return value

def iter_history(payload):
    """Preserve both active and inactive rows; ordering and pairing come later."""
    fixture = payload['fixtureId']
    for venue, book in payload.get('bookmakers', {}).items():
        for market, m in book.get('markets', {}).items():
            for outcome, o in m.get('outcomes', {}).items():
                for player, snapshots in o.get('players', {}).items():
                    if not isinstance(snapshots, list): raise ValueError('historical snapshots must be a list')
                    for snapshot in snapshots:
                        yield {'fixture_id': fixture, 'venue': venue, 'market_id': market,
                               'outcome_id': outcome, 'player_id': player, 'snapshot': snapshot}

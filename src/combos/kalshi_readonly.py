"""Authenticated, bounded account reads. Pagination is not an atomic snapshot."""
import base64
import json
import os
import re
from pathlib import Path
import time

import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

BASE = 'https://external-api.kalshi.com'
PREFIX = '/trade-api/v2/'
ALLOWED = frozenset(PREFIX + suffix for suffix in (
    'portfolio/balance', 'portfolio/subaccounts/balances', 'portfolio/positions',
    'portfolio/orders', 'portfolio/fills', 'portfolio/settlements', 'communications/quotes',
    'communications/id', 'account/limits'))


def order_read_path(order_id):
    if not isinstance(order_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', order_id):
        raise ValueError('invalid order id')
    return PREFIX + 'portfolio/orders/' + order_id


def allowed_read_path(path):
    return isinstance(path, str) and (path in ALLOWED or
        re.fullmatch(re.escape(PREFIX) + r'portfolio/orders/[A-Za-z0-9_-]{1,128}', path) is not None)


class ReadSigner:
    def __init__(self, key_id, pem):
        self.key_id = key_id
        self.key = serialization.load_pem_private_key(pem, password=None)
        if not isinstance(self.key, rsa.RSAPrivateKey):
            raise ValueError('RSA key required')

    @classmethod
    def from_environment(cls):
        return cls(os.environ['KALSHI_API_KEY_ID'],
                   Path(os.environ['KALSHI_PRIVATE_KEY_PATH']).expanduser().read_bytes())

    def headers(self, path):
        if not allowed_read_path(path):
            raise ValueError('unapproved read path')
        timestamp = str(time.time_ns() // 1_000_000)
        signature = self.key.sign((timestamp + 'GET' + path).encode(),
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()),
                        salt_length=padding.PSS.DIGEST_LENGTH), hashes.SHA256())
        return {'KALSHI-ACCESS-KEY': self.key_id,
                'KALSHI-ACCESS-TIMESTAMP': timestamp,
                'KALSHI-ACCESS-SIGNATURE': base64.b64encode(signature).decode()}


def private_json(path, value):
    """Create a new private artifact, never overwrite a previous observation."""
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.flush()
        os.fsync(stream.fileno())


class ReadOnlyClient:
    def __init__(self, signer, *, session=None, clock=time.time):
        self.signer = signer
        self.clock = clock
        self.session = session if session is not None else requests.Session()
        if session is None:
            self.session.trust_env = False
            self.session.mount('https://', requests.adapters.HTTPAdapter(max_retries=0))

    def get(self, path, params=None):
        if not allowed_read_path(path):
            raise ValueError('unapproved read path')
        params = dict(params or {})
        if any(not isinstance(k, str) or type(v) not in (str, int, bool)
               for k, v in params.items()):
            raise ValueError('scalar query parameters required')
        envelope = {'method': 'GET', 'path': path, 'params': params,
                    'request_started_at': self.clock()}
        try:
            response = self.session.get(BASE + path, params=params,
                headers=self.signer.headers(path), timeout=(5, 15), allow_redirects=False)
            envelope['http_status'] = response.status_code
            try:
                envelope['payload'] = response.json()
            except ValueError:
                envelope['error'] = 'invalid_json'
        except requests.RequestException as exc:
            # Exception text may contain signed request details.
            envelope['error'] = type(exc).__name__
        envelope['received_at'] = self.clock()
        return envelope

    def paginate(self, path, fields, *, params=None, max_pages=5, archive=None):
        if type(max_pages) is not int or not 1 <= max_pages <= 100:
            raise ValueError('page budget must be 1..100')
        params = dict(params or {})
        if 'cursor' in params or not fields or len(set(fields)) != len(fields):
            raise ValueError('start from first page with distinct required fields')
        rows = {field: [] for field in fields}
        pages, seen = [], set()
        complete, reason = False, 'page_budget'
        for _ in range(max_pages):
            page = self.get(path, params)
            pages.append(page)
            if archive is not None:
                archive(page)
            payload = page.get('payload')
            if page.get('http_status') != 200 or not isinstance(payload, dict):
                reason = 'request_failed'
                break
            if any(not isinstance(payload.get(field), list) or
                   any(not isinstance(row, dict) for row in payload[field]) for field in fields):
                reason = 'invalid_rows'
                break
            # Quotes documents an optional cursor; the live empty response omits it.
            # Only accept that observed terminal shape, not a missing cursor on
            # nonempty pages or on portfolio endpoints.
            absent_empty_quotes = (path == PREFIX + 'communications/quotes'
                and fields == ('quotes',) and payload.get('quotes') == []
                and 'cursor' not in payload)
            cursor = '' if absent_empty_quotes else payload.get('cursor')
            if not isinstance(cursor, str):
                reason = 'invalid_cursor'
                break
            for field in fields:
                rows[field].extend(payload[field])
            if not cursor:
                complete, reason = True, 'cursor_exhausted'
                break
            if cursor in seen:
                reason = 'cursor_loop'
                break
            seen.add(cursor)
            params['cursor'] = cursor
        return {'rows': rows, 'pages': pages, 'pagination_complete': complete,
                'stop_reason': reason, 'atomic_snapshot': False}

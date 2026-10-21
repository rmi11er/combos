import base64
import json
from types import SimpleNamespace

import pytest
import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from combos.kalshi_readonly import ReadOnlyClient, ReadSigner, PREFIX, private_json

PATH = PREFIX + 'portfolio/orders'


class Session:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        response = next(self.responses)
        if isinstance(response, Exception):
            raise response
        return SimpleNamespace(status_code=200, json=lambda: response)


def client(responses):
    session = Session(responses)
    return ReadOnlyClient(SimpleNamespace(headers=lambda path: {'secret': 'never archived'}),
                          session=session), session


def test_complete_read_preserves_queries_and_disables_redirects():
    c, session = client([{'orders': [{'id': 'a'}], 'cursor': 'next'},
                         {'orders': [{'id': 'b'}], 'cursor': ''}])
    result = c.paginate(PATH, ('orders',), params={'status': 'resting'})
    assert result['pagination_complete'] and not result['atomic_snapshot']
    assert len(result['rows']['orders']) == 2
    assert session.calls[1][1]['params'] == {'status': 'resting', 'cursor': 'next'}
    assert session.calls[0][1]['allow_redirects'] is False
    assert 'never archived' not in json.dumps(result)


@pytest.mark.parametrize('responses,budget,reason', [
    ([{'orders': [], 'cursor': 'n'}], 1, 'page_budget'),
    ([{'orders': [], 'cursor': 'n'}] * 2, 3, 'cursor_loop'),
    ([{'orders': []}], 3, 'invalid_cursor'),
    ([{'cursor': ''}], 3, 'invalid_rows'),
    ([requests.Timeout('secret')], 3, 'request_failed'),
])
def test_incomplete_never_authorizes_empty_account(responses, budget, reason):
    c, session = client(responses)
    result = c.paginate(PATH, ('orders',), max_pages=budget)
    assert not result['pagination_complete']
    assert result['stop_reason'] == reason
    assert len(session.calls) == len(responses)
    assert 'secret' not in json.dumps(result)


def test_signer_uses_exact_get_path_and_rejects_untrusted_paths():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    signer = ReadSigner('test', key.private_bytes(serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    headers = signer.headers(PATH)
    key.public_key().verify(base64.b64decode(headers['KALSHI-ACCESS-SIGNATURE']),
        (headers['KALSHI-ACCESS-TIMESTAMP'] + 'GET' + PATH).encode(),
        padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.DIGEST_LENGTH), hashes.SHA256())
    c, session = client([])
    for path in ('https://example.com', PATH + '?cursor=x', PREFIX + '../orders'):
        with pytest.raises(ValueError):
            c.get(path)
        with pytest.raises(ValueError):
            signer.headers(path)
    assert not session.calls


def test_artifact_private_and_cannot_overwrite(tmp_path):
    path = tmp_path / 'read.json'
    private_json(path, {'ok': True})
    assert path.stat().st_mode & 0o777 == 0o600
    with pytest.raises(FileExistsError):
        private_json(path, {})


def test_optional_cursor_only_for_empty_quotes():
    c, _ = client([{'quotes': []}])
    assert c.paginate(PREFIX + 'communications/quotes', ('quotes',))['pagination_complete']
    c, _ = client([{'quotes': [{'id': 'a'}]}])
    assert not c.paginate(PREFIX + 'communications/quotes', ('quotes',))['pagination_complete']

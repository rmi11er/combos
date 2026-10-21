from datetime import datetime
import hashlib
import json
from zoneinfo import ZoneInfo
import pytest
from heldout_fixture_filter import HeldoutFixtureFilter


def setup_filter(tmp_path):
    p = tmp_path/'excluded.json'
    p.write_text(json.dumps({'fixtures': ['mlb:26AUG011507STLTOR'], 'fixture_count': 1,
                            'observed_development_dates': ['2026-07-31']}))
    digest = hashlib.sha256(p.read_bytes()).hexdigest()
    return p, digest


def row(fixture, price=.2):
    return {'at': datetime(2026, 8, 1, 10, tzinfo=ZoneInfo('America/Chicago')).timestamp(),
            'buckets': {'fixture': [fixture]}, 'yes_price': price}


def test_excludes_before_economics_and_requires_full_consumption(tmp_path):
    p, digest = setup_filter(tmp_path)
    f = HeldoutFixtureFilter(p, digest, ['2026-08-01'])
    kept = row('mlb:26AUG031507STLTOR')
    stream = f.rows([row('mlb:26AUG011507STLTOR'), kept])
    assert next(stream) is kept
    with pytest.raises(ValueError, match='not fully consumed'):
        f.receipt()
    assert list(stream) == []
    assert f.receipt()['dates']['2026-08-01'] == {'input': 2, 'excluded': 1, 'retained': 1}
    with pytest.raises(ValueError, match='fresh fixture filter'):
        list(f.rows([]))


def test_hash_date_and_identity_fail_closed(tmp_path):
    p, digest = setup_filter(tmp_path)
    with pytest.raises(ValueError, match='hash mismatch'):
        HeldoutFixtureFilter(p, 'wrong', ['2026-08-01'])
    with pytest.raises(ValueError, match='overlap'):
        HeldoutFixtureFilter(p, digest, ['2026-07-31'])
    f = HeldoutFixtureFilter(p, digest, ['2026-08-02'])
    with pytest.raises(ValueError, match='outside frozen'):
        list(f.rows([row('mlb:26AUG011507STLTOR')]))
    f = HeldoutFixtureFilter(p, digest, ['2026-08-01'])
    with pytest.raises(ValueError, match='noncanonical'):
        list(f.rows([row('26AUG011507STLTOR')]))

import json
import sqlite3
import pytest
from build_development_fixture_exclusions import build, canonical_fixture


def test_broad_only_outcomes_are_excluded_too(tmp_path):
    native = tmp_path/'native.json'
    index = tmp_path/'index.sqlite'
    native.write_text(json.dumps({'observed_dates': ['2026-07-31'], 'fixtures': [
        {'fixture': '26AUG011507STLTOR'}, {'fixture': '26AUG011610MIANYM'}]}))
    db = sqlite3.connect(index)
    db.execute('CREATE TABLE prints (date TEXT)')
    db.execute("INSERT INTO prints VALUES ('2026-07-31')")
    db.execute('CREATE TABLE fixtures (fixture TEXT)')
    db.execute("INSERT INTO fixtures VALUES ('mlb:26AUG011507STLTOR')")
    db.commit(); db.close()
    result = build(native, index)
    assert result['fixture_count'] == 2
    assert result['additional_broad_universe_fixtures'] == ['mlb:26AUG011610MIANYM']
    assert not result['validation_outcomes_read']
    native.write_text(json.dumps({'observed_dates': ['2026-08-02'], 'fixtures': []}))
    with pytest.raises(ValueError, match='July development'):
        build(native, index)


def test_doubleheaders_preserve_game_identity():
    assert canonical_fixture('26JUL071415MILSTLG1') == 'mlb:26JUL071415MILSTLG1'
    assert canonical_fixture('mlb:26JUL071415MILSTLG2') != canonical_fixture('26JUL071415MILSTLG1')
    with pytest.raises(ValueError):
        canonical_fixture('nfl:26JAN05ABCDEF')

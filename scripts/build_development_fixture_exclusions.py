"""Freeze already-inspected fixture identities without reading validation outcomes."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sqlite3


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def canonical_fixture(value):
    native = value.removeprefix('mlb:')
    if not re.fullmatch(r'\d{2}[A-Z]{3}\d{6}[A-Z]+(?:G[12])?', native):
        raise ValueError('unrecognized MLB fixture identity: '+value)
    return 'mlb:'+native


def build(native_summary, development_index):
    before = {str(p): digest(p) for p in (native_summary, development_index)}
    report = json.loads(native_summary.read_text())
    dates = report['observed_dates']
    if not dates or any(not date.startswith('2026-07-') for date in dates):
        raise ValueError('expected July development universe only')
    native = {canonical_fixture(r['fixture']) for r in report['fixtures']}
    db = sqlite3.connect(development_index.resolve().as_uri()+'?mode=ro', uri=True)
    index_dates = {r[0] for r in db.execute('SELECT DISTINCT date FROM prints')}
    if not index_dates or not index_dates <= set(dates):
        raise ValueError('index dates outside inspected development scope')
    priced = {canonical_fixture(r[0]) for r in db.execute('SELECT DISTINCT fixture FROM fixtures')}
    db.close()
    assert before == {str(p): digest(p) for p in (native_summary, development_index)}
    fixtures = sorted(native | priced)
    return {'schema_version': 1, 'source_hashes': before,
            'observed_development_dates': dates, 'priced_development_dates': sorted(index_dates),
            'native_fixture_count': len(native), 'priced_fixture_count': len(priced),
            'additional_broad_universe_fixtures': sorted(native-priced),
            'fixtures': fixtures, 'fixture_count': len(fixtures),
            'validation_outcomes_read': False,
            'policy': 'Exclude every validation print touching any listed fixture, before selection and capital replay.',
            'scope': 'All inspected July native-universe and common-priced fixture identities; refresh if additional development outcomes are inspected.',
            'script_sha256': digest(Path(__file__))}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--native-summary', type=Path, required=True)
    p.add_argument('--development-index', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    result = build(a.native_summary, a.development_index)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    with a.out.open('x') as handle:
        json.dump(result, handle, indent=2)
        handle.write('\n')
    print(json.dumps({k: result[k] for k in ('fixture_count', 'native_fixture_count', 'priced_fixture_count', 'validation_outcomes_read')}))


if __name__ == '__main__':
    main()

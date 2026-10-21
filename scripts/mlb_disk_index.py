#!/usr/bin/env python3
"""Bounded-memory, certified common-source longitudinal input index.

Only public research artifacts are read. SQLite contains shared economics once
per print and exact remaining per-model fields; no float re-encoding through SQL.
"""
import hashlib
import json
import os
from pathlib import Path
import sqlite3

from mlb_longitudinal_sweep import discover
from mlb_validation_report import bounds

SHARED = ('at', 'quantity', 'yes_price', 'maker_fee', 'yes_settlement',
          'settled_at', 'buckets', 'source')


class JSONStream:
    def __init__(self, handle):
        self.handle = handle
        self.buffer = ''
        self.decoder = json.JSONDecoder()
        self.eof = False

    def fill(self):
        chunk = self.handle.read(65536)
        self.buffer += chunk
        self.eof = not chunk

    def whitespace(self):
        self.buffer = self.buffer.lstrip()
        while not self.buffer and not self.eof:
            self.fill()
            self.buffer = self.buffer.lstrip()

    def token(self, token):
        self.whitespace()
        if not self.buffer.startswith(token):
            raise ValueError('invalid_json_expected:' + token)
        self.buffer = self.buffer[len(token):]

    def peek(self):
        self.whitespace()
        return self.buffer[:1]

    def value(self):
        self.whitespace()
        while True:
            try:
                value, end = self.decoder.raw_decode(self.buffer)
                # A scalar may end exactly at a chunk boundary: read its delimiter.
                if end == len(self.buffer) and not self.eof:
                    self.fill()
                    continue
                self.buffer = self.buffer[end:]
                return value
            except json.JSONDecodeError:
                if self.eof:
                    raise
                self.fill()


def stream_document(path, row_callback):
    """Stream the opportunities array, returning all other top-level metadata."""
    meta = {}; seen = set()
    with Path(path).open() as handle:
        reader = JSONStream(handle); reader.token('{')
        while reader.peek() != '}':
            key = reader.value()
            if not isinstance(key, str) or key in seen:
                raise ValueError('duplicate_or_invalid_document_key')
            seen.add(key); reader.token(':')
            if key == 'opportunities':
                reader.token('[')
                while reader.peek() != ']':
                    row_callback(reader.value())
                    if reader.peek() == ']':
                        break
                    reader.token(',')
                    if reader.peek() == ']':
                        raise ValueError('invalid_json_trailing_comma')
                reader.token(']')
            else:
                meta[key] = reader.value()
            if reader.peek() == '}':
                break
            reader.token(',')
            if reader.peek() == '}':
                raise ValueError('invalid_json_trailing_comma')
        reader.token('}')
        if reader.peek():
            raise ValueError('invalid_json_trailing_content')
    if 'opportunities' not in seen:
        raise ValueError('opportunities_missing')
    return meta


def connect(path):
    db = sqlite3.connect(path)
    db.execute('PRAGMA cache_size=-16384')
    db.execute('PRAGMA temp_store=FILE')
    db.execute('PRAGMA foreign_keys=ON')
    return db


def dumps(value):
    return json.dumps(value, separators=(',', ':'), allow_nan=False)


def file_digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def validate_row(row, start, end):
    if not start <= row['at'] < end:
        return False
    if row['source']['sampling_method'] != 'census':
        raise ValueError('requested_day_contains_non_census_source')
    if type(row['source']['nlegs']) is not int or not 2 <= row['source']['nlegs'] <= 4:
        raise ValueError('study_requires_two_through_four_legs')
    if len(set(row['buckets']['fixture'])) != row['source']['nlegs']:
        raise ValueError('study_requires_distinct_fixtures')
    if row['at'] >= row['source']['start_at'] - 60:
        raise ValueError('study_requires_sixty_second_pregame_cutoff')
    if not set(row['source']['series']) <= {'KXMLBGAME', 'KXMLBSPREAD', 'KXMLBTOTAL'}:
        raise ValueError('study_requires_fullgame_non_player_MLB')
    return True


def build_index(batch_roots, plan, outdb):
    """Publish an atomic index; return the exact prepare() coverage structure."""
    files, empty_dates, states = discover(batch_roots, plan)
    target = Path(outdb); target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + '.building')
    if temporary.exists():
        raise ValueError('index_build_already_exists:' + str(temporary))
    db = connect(temporary)
    db.executescript('''
      CREATE TABLE prints (id INTEGER PRIMARY KEY, date TEXT, evaluation_id TEXT,
                           at REAL, shared TEXT);
      CREATE TABLE models (print_id INTEGER REFERENCES prints(id) ON DELETE CASCADE,
                           model TEXT, payload TEXT, PRIMARY KEY(print_id, model));
      CREATE TABLE fixtures (print_id INTEGER REFERENCES prints(id) ON DELETE CASCADE, fixture TEXT);
      CREATE INDEX fixture_key ON fixtures(fixture);
      CREATE INDEX print_order ON prints(at, evaluation_id);
      CREATE INDEX model_key ON models(model,print_id);
      CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT);
      CREATE TABLE stage (evaluation_id TEXT, model TEXT, payload TEXT,
                          PRIMARY KEY(evaluation_id, model));
    ''')
    models = plan['primary_models']; observed = []; missing = []; coverage = {}; purged = {}
    try:
        for date, fold in sorted(plan['dates'].items()):
            if fold == 'previously_inspected_reference':
                continue
            if date in empty_dates:
                observed.append(date); coverage[date] = {'complete_empty_eligible_scope': True}
                continue
            if date not in files:
                missing.append({'date': date, 'fold': fold, 'reason': 'awaiting_completed_day'})
                continue
            # paired_day uses Chicago calendar boundaries independently of plan timezone.
            start, end = bounds(date, 'America/Chicago')
            actual = set(); counts = {model: 0 for model in sorted(models)}; validation_errors = []
            def consume(row):
                actual.add(row['model'])
                if row['model'] not in models:
                    return
                try:
                    if not validate_row(row, start, end):
                        return
                except (ValueError, KeyError, TypeError) as exc:
                    validation_errors[:] = validation_errors or [exc]
                    return
                try:
                    db.execute('INSERT INTO stage VALUES (?,?,?)',
                               (row['evaluation_id'], row['model'], dumps(row)))
                except sqlite3.IntegrityError as exc:
                    validation_errors[:] = validation_errors or [ValueError('duplicate_model_evaluation')]
                    return
                counts[row['model']] += 1
            before = file_digest(files[date])
            meta = stream_document(files[date], consume)
            if before != file_digest(files[date]):
                raise ValueError('replay_changed_during_indexing')
            if meta.get('cohort_description') != 'Complete daily census':
                raise ValueError('longitudinal_requires_completed_daily_census')
            left, right = bounds(date, plan['timezone'])
            if meta['start_at'] > left or meta['end_at'] < right:
                raise ValueError('replay_does_not_cover_complete_requested_day')
            absent = sorted(set(models) - actual)
            common = db.execute('SELECT evaluation_id FROM stage GROUP BY evaluation_id HAVING COUNT(*)=? ORDER BY evaluation_id', (len(models),))
            n = 0
            if absent:
                missing.append({'date': date, 'fold': fold, 'reason': 'required_primary_models_unavailable', 'missing_primary_models': absent})
            else:
                if validation_errors:
                    raise validation_errors[0]
                if meta['start_at'] > start or meta['end_at'] < end:
                    raise ValueError('input_does_not_cover_complete_calendar_day')
                for (identifier,) in common:
                    paired = [json.loads(payload) for (payload,) in db.execute('SELECT payload FROM stage WHERE evaluation_id=? ORDER BY model', (identifier,))]
                    reference = paired[0]
                    for row in paired:
                        for key in SHARED:
                            if row[key] != reference[key]:
                                raise ValueError('inconsistent_paired_' + key)
                    shared = {key: reference[key] for key in SHARED}
                    pid = db.execute('INSERT INTO prints(date,evaluation_id,at,shared) VALUES (?,?,?,?)', (date, identifier, reference['at'], dumps(shared))).lastrowid
                    db.executemany('INSERT INTO fixtures VALUES (?,?)', ((pid, f) for f in set(reference['buckets']['fixture'])))
                    for row in paired:
                        payload = {k: v for k, v in row.items() if k not in SHARED}
                        db.execute('INSERT INTO models VALUES (?,?,?)', (pid, row['model'], dumps(payload)))
                    n += 1
                if not n:
                    missing.append({'date': date, 'fold': fold, 'reason': 'empty_primary_source_intersection'})
                else:
                    observed.append(date)
                    coverage[date] = {'priced_by_model': counts, 'common_prints_before_purge': n,
                                      'fee_scenario': meta.get('identity', {}).get('fee_scenario')}
            db.execute('DELETE FROM stage'); db.commit()
        if plan['evaluation'].get('purge_shared_fixtures_between_development_and_validation', True):
            db.execute('CREATE TABLE development_fixtures (fixture TEXT PRIMARY KEY)')
            for date in observed:
                if plan['dates'][date] == 'development':
                    db.execute('INSERT OR IGNORE INTO development_fixtures SELECT f.fixture FROM fixtures f JOIN prints p ON p.id=f.print_id WHERE p.date=?', (date,))
            for date in observed:
                if plan['dates'][date] == 'validation':
                    ids = 'SELECT DISTINCT p.id FROM prints p JOIN fixtures f ON f.print_id=p.id JOIN development_fixtures d ON d.fixture=f.fixture WHERE p.date=?'
                    purged[date] = db.execute('SELECT COUNT(*) FROM (' + ids + ')', (date,)).fetchone()[0]
                    db.execute('DELETE FROM prints WHERE id IN (' + ids + ')', (date,))
        if db.execute('SELECT evaluation_id FROM prints GROUP BY evaluation_id HAVING COUNT(*)>1 LIMIT 1').fetchone():
            raise ValueError('repeated_evaluation_across_dated_inputs')
        result = {'observed_dates': sorted(observed), 'empty_scope_dates': sorted(empty_dates),
                  'missing_dates': missing, 'coverage': coverage,
                  'validation_shared_fixture_purged_prints': purged,
                  'purge_status': 'provisional_missing_development_dates' if any(r['fold'] == 'development' for r in missing) else 'all_priced_development_dates_available'}
        # Revalidate completion certificates after reading, before publication.
        # New completed dates are permitted; the build remains its initial snapshot.
        certified, _, _ = discover(batch_roots, plan)
        if any(date not in certified or file_digest(path) != file_digest(certified[date])
               for date, path in files.items()):
            raise ValueError('completion_certificate_changed_during_indexing')
        db.executemany('INSERT INTO metadata VALUES (?,?)', [('coverage', dumps(result)), ('plan', dumps(plan)), ('batch_states', dumps(states)), ('sources', dumps({d: {'path': str(p), 'sha256': file_digest(p)} for d, p in files.items()}))])
        db.execute('DROP TABLE stage'); db.commit(); db.close()
        os.replace(temporary, target)
        return result
    except BaseException:
        db.close(); temporary.unlink(missing_ok=True)
        raise


def iter_model(dbpath, model):
    db = connect(dbpath)
    try:
        for shared, payload in db.execute('SELECT p.shared,m.payload FROM prints p JOIN models m ON m.print_id=p.id WHERE m.model=? ORDER BY p.at,p.evaluation_id', (model,)):
            yield {**json.loads(shared), **json.loads(payload)}
    finally:
        db.close()


def count_model_rows(dbpath, model=None):
    db = connect(dbpath)
    try:
        return db.execute('SELECT COUNT(*) FROM models' + (' WHERE model=?' if model is not None else ''), (model,) if model is not None else ()).fetchone()[0]
    finally:
        db.close()

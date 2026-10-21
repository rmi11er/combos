from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import mlb_disk_index as disk
import mlb_longitudinal_sweep as sweep
from test_mlb_longitudinal_sweep import plan, opportunity, day


def certify(root, inputs, empty=()):
    root.mkdir(exist_ok=True)
    state = {'status': 'running', 'days': {}, 'stages': {}}
    for date, data in inputs.items():
        path = root / date / 'replay/opportunities.json'
        sweep.save(path, data)
        state['days'][date] = {'status': 'complete'}
        state['stages'][date + '/replay'] = {'status': 'complete', 'output_sha256': {str(path.resolve()): sweep.digest(path)}}
    for date in empty:
        sweep.save(root / date / 'cohort/summary.json', {'date': date, 'complete_census': True})
        state['days'][date] = {'status': 'complete_empty_eligible_scope'}
    sweep.save(root / 'batch_status.json', state)
    return root


def test_exact_rows_coverage_purge_and_missing(tmp_path):
    p = plan(); p['dates']['2026-07-03'] = 'validation'; p['dates']['2026-07-05'] = 'validation'
    inputs = {}
    for date in ('2026-07-01', '2026-07-03'):
        rows = [opportunity(date, date, model) for model in p['primary_models']]
        for row in rows:
            row['custom_model_metadata'] = {'preserve': row['model']}
        inputs[date] = day(date, rows)
    expected, coverage = sweep.prepare(inputs, p)
    path = tmp_path / 'index.sqlite'
    actual = disk.build_index([certify(tmp_path / 'batch', inputs)], p, path)
    assert actual == coverage
    assert disk.count_model_rows(path) == len(expected)
    for model in p['primary_models']:
        assert list(disk.iter_model(path, model)) == [r for r in expected if r['model'] == model]
        assert disk.count_model_rows(path, model) == 1


def test_source_economics_and_atomic_failure(tmp_path):
    p = plan(); date = '2026-07-01'
    rows = [opportunity(date, 'same', m) for m in p['primary_models']]
    rows[-1]['quantity'] += 1
    root = certify(tmp_path / 'batch', {date: day(date, rows)})
    path = tmp_path / 'index.sqlite'
    with pytest.raises(ValueError, match='inconsistent_paired_quantity'):
        disk.build_index([root], p, path)
    assert not path.exists() and not path.with_name(path.name + '.building').exists()


def test_missing_model_empty_day_and_intersection(tmp_path):
    p = plan(); p['dates']['2026-07-05'] = 'validation'
    inputs = {'2026-07-01': day('2026-07-01', [opportunity('2026-07-01', 'only')]),
              '2026-07-03': day('2026-07-03', [opportunity('2026-07-03', m, m) for m in p['primary_models']])}
    root = certify(tmp_path / 'batch', inputs, ['2026-07-05'])
    expected, coverage = sweep.prepare(inputs, p, ['2026-07-05'])
    assert disk.build_index([root], p, tmp_path / 'index.sqlite') == coverage
    assert not expected


def test_duplicate_model_is_not_silently_collapsed(tmp_path):
    p = plan(); date = '2026-07-01'
    rows = [opportunity(date, 'same', m) for m in p['primary_models']]
    rows.append(deepcopy(rows[0]))
    with pytest.raises(ValueError, match='duplicate_model_evaluation'):
        disk.build_index([certify(tmp_path / 'batch', {date: day(date, rows)})], p, tmp_path / 'index.sqlite')


def test_retains_distinct_prints_identical_economics_and_orders(tmp_path):
    p = plan(); date = '2026-07-01'
    rows = [opportunity(date, identifier, m) for identifier in ['z', 'a'] for m in p['primary_models']]
    root = certify(tmp_path / 'batch', {date: day(date, rows)})
    path = tmp_path / 'index.sqlite'; disk.build_index([root], p, path)
    assert [r['evaluation_id'] for r in disk.iter_model(path, 'kalshi')] == ['a', 'z']
    db = disk.connect(path)
    assert db.execute('SELECT COUNT(*) FROM prints').fetchone()[0] == 2
    assert db.execute('SELECT COUNT(*) FROM models').fetchone()[0] == 4
    db.close()


def test_streaming_chunk_boundaries_and_bad_json(tmp_path):
    path = tmp_path / 'data.json'
    payload = {'start_at': 1234567, 'opportunities': [{'large': 'x' * 131072}, {'value': 1e-12}], 'tail': '\u2603'}
    path.write_text(json.dumps(payload)); rows = []
    assert disk.stream_document(path, rows.append) == {'start_at': 1234567, 'tail': '\u2603'}
    assert rows == payload['opportunities']
    path.write_text('{"opportunities": [],}')
    with pytest.raises(ValueError):
        disk.stream_document(path, rows.append)


def test_changed_certificate_rejected(tmp_path):
    p = plan(); date = '2026-07-01'; root = certify(tmp_path / 'batch', {date: day(date, [])})
    (root / date / 'replay/opportunities.json').write_text('{}')
    with pytest.raises(ValueError, match='hash_certificate'):
        disk.build_index([root], p, tmp_path / 'index.sqlite')


def test_unavailable_model_skips_invalid_scope_like_oracle(tmp_path):
    p = plan(); date = '2026-07-01'
    row = opportunity(date, 'a'); row['source']['nlegs'] = 8
    inputs = {date: day(date, [row, deepcopy(row)])}
    expected, coverage = sweep.prepare(inputs, p)
    actual = disk.build_index([certify(tmp_path / 'batch', inputs)], p, tmp_path / 'index.sqlite')
    assert actual == coverage and not expected


def test_cross_date_duplicate_identity_rejected(tmp_path):
    p = plan()
    inputs = {date: day(date, [opportunity(date, 'same', m) for m in p['primary_models']]) for date in p['dates']}
    with pytest.raises(ValueError, match='repeated_evaluation_across_dated_inputs'):
        disk.build_index([certify(tmp_path / 'batch', inputs)], p, tmp_path / 'index.sqlite')

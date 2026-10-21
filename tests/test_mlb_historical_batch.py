"""Batch orchestration preserves completeness, reproducibility and bounded retries."""
from datetime import datetime, timedelta
import gzip
import json
from pathlib import Path
import sys
import ast
import subprocess
import venv
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import mlb_historical_batch as batch


def test_child_stages_preserve_the_virtual_environment(tmp_path):
    environment = tmp_path / 'environment'
    venv.EnvBuilder(with_pip=False, symlinks=True).create(environment)
    executable = batch.interpreter_path(environment / 'bin/python')
    result = subprocess.run([str(executable), '-c', 'import sys; print(sys.prefix)'],
                            capture_output=True, text=True, check=True)
    assert Path(result.stdout.strip()) == environment


def bounds():
    start = datetime(2026, 7, 1, tzinfo=ZoneInfo('America/Chicago'))
    return start.timestamp(), (start + timedelta(days=1)).timestamp()


def partition(tmp_path, name, lo, hi, complete=True):
    path = tmp_path / '2026-07-01' / name / 'manifest.json'
    batch.save(path, {'start_at': lo, 'end_at': hi, 'complete': complete,
                      'pages': [{'path': 'page_00000.json.gz', 'sha256': 'checked_by_adapter'}]})
    return path


def test_day_readiness_never_promotes_missing_or_incomplete_partitions(tmp_path):
    lo, hi = bounds()
    assert not batch.day_readiness(tmp_path, '2026-07-01')['ready']
    partition(tmp_path, 'first', lo, lo + 3600)
    assert not batch.day_readiness(tmp_path, '2026-07-01')['ready']
    partition(tmp_path, 'last', lo + 3600, hi, complete=False)
    assert not batch.day_readiness(tmp_path, '2026-07-01')['ready']
    partition(tmp_path, 'last', lo + 3600, hi)
    result = batch.day_readiness(tmp_path, '2026-07-01')
    assert result['ready'] and len(result['manifest_sha256']) == 2


def test_day_readiness_rejects_overlapping_and_empty_complete_certificates(tmp_path):
    lo, hi = bounds()
    partition(tmp_path, 'first', lo, lo + 3600)
    partition(tmp_path, 'overlap', lo + 100, hi)
    with pytest.raises(ValueError, match='overlapping'):
        batch.day_readiness(tmp_path, '2026-07-01')
    (tmp_path / '2026-07-01/overlap/manifest.json').unlink()
    path = partition(tmp_path, 'last', lo + 3600, hi)
    data = batch.load(path); data['pages'] = []; batch.save(path, data)
    with pytest.raises(ValueError, match='no_pages'):
        batch.day_readiness(tmp_path, '2026-07-01')


def test_scope_empty_is_distinct_from_incomplete_and_respects_pregame_buffer(tmp_path):
    lo, _ = bounds()
    def row(at):
        return {'trade': {'taker_side': 'yes', 'created_time': datetime.fromtimestamp(at, ZoneInfo('UTC')).isoformat()},
                'classification': {'distinct_fixtures': True, 'nlegs': 2, 'earliest_scheduled_start': lo + 200}}
    file = tmp_path / 'candidate_trades.jsonl.gz'
    with gzip.open(file, 'wt') as handle:
        handle.write(json.dumps(row(lo + 140)) + '\n')
    assert not batch.has_eligible_scope(tmp_path)
    with gzip.open(file, 'at') as handle:
        handle.write(json.dumps(row(lo + 139)) + '\n')
    assert batch.has_eligible_scope(tmp_path)


def stage_setup(tmp_path):
    frozen = tmp_path / 'frozen.py'; frozen.write_text('# fixed\n')
    manifest = {'frozen_sha256': {str(frozen): batch.digest(frozen)}}
    args = SimpleNamespace(out=tmp_path, max_stage_attempts=2, stage_timeout_seconds=5, poll_seconds=1)
    state = {'stages': {}}
    return frozen, manifest, args, state, tmp_path / 'status.json'


def test_success_is_durable_and_resume_verifies_outputs_before_skipping(tmp_path, monkeypatch):
    _, manifest, args, state, status = stage_setup(tmp_path)
    artifact = tmp_path / 'artifact.json'
    calls = []
    def run(*unused):
        calls.append(True); artifact.write_text('{}'); return 0
    monkeypatch.setattr(batch, 'run_command', run)
    for _ in range(2):
        batch.run_stage('day/stage', ['synthetic'], [artifact], state, status, manifest, args)
    assert len(calls) == 1 and state['stages']['day/stage']['status'] == 'complete'
    artifact.write_text('{"changed":true}')
    with pytest.raises(ValueError, match='completed_stage_output_changed'):
        batch.run_stage('day/stage', ['synthetic'], [artifact], state, status, manifest, args)


def test_zero_exit_without_required_outputs_is_failure(tmp_path, monkeypatch):
    _, manifest, args, state, status = stage_setup(tmp_path)
    monkeypatch.setattr(batch, 'run_command', lambda *args: 0)
    with pytest.raises(ValueError, match='missing_success_artifact'):
        batch.run_stage('day/stage', ['synthetic'], [tmp_path / 'missing.json'], state, status, manifest, args)
    assert state['stages']['day/stage']['status'] == 'failed'


def test_transient_retries_are_bounded_and_persist_across_resume(tmp_path, monkeypatch):
    _, manifest, args, state, status = stage_setup(tmp_path)
    calls = []
    def run(command, log, *unused):
        calls.append(True); log.write_text('HTTP 429\n'); return 1
    monkeypatch.setattr(batch, 'run_command', run)
    monkeypatch.setattr(batch.time, 'sleep', lambda unused: None)
    for _ in range(2):
        with pytest.raises(RuntimeError, match='stage_attempts_exhausted'):
            batch.run_stage('day/stage', ['synthetic'], [], state, status, manifest, args)
    assert len(calls) == 2


def test_metadata_coverage_and_budget_failure_does_not_retry_automatically(tmp_path, monkeypatch):
    _, manifest, args, state, status = stage_setup(tmp_path)
    calls = []
    def run(command, log, *unused):
        calls.append(True)
        log.write_text('Earlier HTTP 429\nIncomplete combo metadata; resume with larger budget.\n')
        return 1
    monkeypatch.setattr(batch, 'run_command', run)
    with pytest.raises(RuntimeError, match='nontransient'):
        batch.run_stage('day/stage', ['synthetic'], [], state, status, manifest, args)
    assert len(calls) == 1


def test_code_mutation_prevents_stage_execution(tmp_path, monkeypatch):
    frozen, manifest, args, state, status = stage_setup(tmp_path)
    frozen.write_text('# changed\n')
    monkeypatch.setattr(batch, 'run_command', lambda *args: pytest.fail('must not execute changed code'))
    with pytest.raises(ValueError, match='frozen_code_or_policy_changed'):
        batch.run_stage('day/stage', ['synthetic'], [], state, status, manifest, args)


def test_exchange_success_requires_all_expected_jobs_and_statuses(tmp_path):
    path = tmp_path / 'exchange/acquisition.json'
    batch.save(path, {'plan': {'jobs': 2}, 'results': [{'status': 200}]})
    with pytest.raises(ValueError, match='job_count'):
        batch.validate_output('exchange', tmp_path, '2026-07-01')
    batch.save(path, {'plan': {'jobs': 2}, 'results': [{'status': 200}, {'status': 429}]})
    with pytest.raises(ValueError, match='failed_exchange_jobs'):
        batch.validate_output('exchange', tmp_path, '2026-07-01')


def test_zero_exit_transient_exchange_job_failures_retry_with_same_bounded_attempts(tmp_path, monkeypatch):
    _, manifest, args, state, status = stage_setup(tmp_path)
    calls = []
    monkeypatch.setattr(batch, 'run_command', lambda *unused: 0)
    monkeypatch.setattr(batch.time, 'sleep', lambda unused: None)
    def validate():
        calls.append(True)
        if len(calls) == 1:
            raise ValueError('failed_exchange_jobs:[429]')
    batch.run_stage('day/exchange', ['synthetic'], [], state, status, manifest, args, validate)
    assert len(calls) == 2 and state['stages']['day/exchange']['status'] == 'complete'


def test_commands_include_frozen_fee_scope_entry_sweep_and_no_order_or_pinnacle(tmp_path):
    commands = batch.stage_commands(Path(sys.executable), tmp_path, tmp_path / 'day', '2026-07-01',
                                    tmp_path / 'fees.json', tmp_path / 'plan.json', 6, 100, None)
    assert [r[0] for r in commands] == ['cohort', 'exchange', 'replay', 'report', 'entry_sweep', 'risk_capacity']
    assert '--write-reviewed-mapping' in commands[1][1]
    assert '--common-only' in commands[3][1]
    assert '--fee-scenario' in commands[0][1] and '--fee-scenario' in commands[2][1]
    assert all('pinnacle' not in ' '.join(r[1]).lower() and 'order' not in ' '.join(r[1]).lower() for r in commands)


def test_frozen_dependency_scope_ignores_unrelated_nfl_script_edits(tmp_path):
    (tmp_path / 'scripts').mkdir()
    for name in batch.PIPELINE_SCRIPTS:
        (tmp_path / 'scripts' / name).write_text('# fixed MLB dependency\n')
    (tmp_path / 'src/combos').mkdir(parents=True)
    for name in batch.PIPELINE_SOURCES:
        (tmp_path / 'src/combos' / name).write_text('# fixed MLB dependency\n')
    unused = tmp_path / 'src/combos/consensus_anchor.py'
    unused.write_text('# separately developed research variant\n')
    unrelated = tmp_path / 'scripts/nfl_research.py'
    unrelated.write_text('# initial unrelated research\n')
    paths = batch.frozen_code_paths(tmp_path)
    assert unrelated not in paths
    assert unused not in paths
    manifest = {'frozen_sha256': {str(p): batch.digest(p) for p in paths}}
    unrelated.write_text('# revised NFL research\n')
    unused.write_text('# revised unimported conditional model\n')
    batch.verify_frozen(manifest)
    (tmp_path / 'scripts/mlb_model_replay.py').write_text('# changed pricing\n')
    with pytest.raises(ValueError, match='frozen_code_or_policy_changed'):
        batch.verify_frozen(manifest)


def test_frozen_scope_contains_static_local_import_dependencies():
    paths = set(batch.frozen_code_paths(ROOT))
    for path in paths:
        for node in ast.walk(ast.parse(path.read_text())):
            modules = []
            if isinstance(node, ast.ImportFrom) and node.module:
                modules = [node.module]
                if node.level:
                    modules = ['combos.' + node.module]
            elif isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            for module in modules:
                candidate = (ROOT/'src'/Path(*module.split('.'))).with_suffix('.py')
                if not candidate.exists():
                    candidate = (ROOT/'scripts'/Path(*module.split('.'))).with_suffix('.py')
                if candidate.exists():
                    assert candidate in paths, f'{path} imports unfrozen local dependency {candidate}'

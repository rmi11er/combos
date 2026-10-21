"""Replay the frozen August policies only after complete dated certificates exist."""
import argparse
from copy import deepcopy
import gzip
import json
from pathlib import Path
import sqlite3
import time
from build_quote_features import features
from heldout_fixture_filter import HeldoutFixtureFilter
from mlb_deployment_cap_sweep import DeploymentConfig
from combos.deployment_risk import DeploymentCappedRiskLedger
from mlb_disk_index import build_index, file_digest, iter_model
from mlb_longitudinal_sweep import discover
from mlb_marginal_reserve_sweep import with_reserve
from mlb_streaming_longitudinal import evaluate_one
from run_mlb_streaming_snapshot import atomic, source_hashes


def load_spec(spec_path, freeze_path, parent_path):
    freeze = json.loads(freeze_path.read_text())
    if file_digest(spec_path) != freeze['specification_sha256']:
        raise ValueError('candidate specification changed after freeze')
    spec = json.loads(spec_path.read_text())
    if file_digest(parent_path) != spec['parent_plan_sha256']:
        raise ValueError('parent plan changed')
    if file_digest(Path(spec['exclusion_manifest']['path'])) != spec['exclusion_manifest']['sha256']:
        raise ValueError('exclusion manifest changed')
    plan = deepcopy(json.loads(parent_path.read_text()))
    plan['dates'] = spec['dates']
    plan['study_id'] = spec['study_id']
    # The parent purge has no development rows in this validation-only index.
    # HeldoutFixtureFilter applies the broader frozen exclusion manifest below.
    plan['evaluation']['purge_shared_fixtures_between_development_and_validation'] = False
    if len(plan['dates']) != 15 or set(plan['dates'].values()) != {'validation'}:
        raise ValueError('expected all 15 frozen August dates')
    if len(spec['policies']) != 14 or len({p['id'] for p in spec['policies']}) != 14:
        raise ValueError('invalid frozen policy census')
    for p in spec['policies']:
        DeploymentConfig(**p['configuration'])
    return spec, plan


def require_dates(files, empty, dates):
    missing = set(dates)-set(files)-set(empty)
    if missing:
        raise ValueError('awaiting_completed_validation_dates:'+','.join(sorted(missing)))


def build_features(index_path, files, out):
    """Use existing causal feature arithmetic; never derive features from outcomes."""
    before = file_digest(index_path)
    index = sqlite3.connect(index_path.resolve().as_uri()+'?mode=ro', uri=True)
    db = sqlite3.connect(out)
    db.execute('CREATE TABLE features(evaluation_id TEXT, model TEXT, point REAL, independent_upper REAL, summed_marginal_interval_cents REAL, nlegs INTEGER, PRIMARY KEY(evaluation_id,model))')
    sources = {}
    try:
        for date, replay in sorted(files.items()):
            expected = {(eid, model): (at, json.loads(payload)) for eid, at, model, payload in index.execute(
                'SELECT p.evaluation_id,p.at,m.model,m.payload FROM prints p JOIN models m ON m.print_id=p.id WHERE p.date=?', (date,))}
            eligible = {eid for eid, _ in expected}
            context = replay.parent/'pricing_context.jsonl.gz'
            digest = file_digest(context)
            seen = set()
            with gzip.open(context, 'rt') as handle:
                for line in handle:
                    row = json.loads(line); eid = row['evaluation_id']
                    if eid not in eligible:
                        continue
                    if eid in seen:
                        raise ValueError('duplicate pricing context')
                    seen.add(eid)
                    for model, value in features(row).items():
                        at, original = expected[eid, model]
                        if row['at'] != at or abs(value['point']-original['fair_point']) > 1e-9 or value['independent_upper'] > original['stressed_upper']+1e-9:
                            raise ValueError('context does not match indexed pricing')
                        db.execute('INSERT INTO features VALUES(?,?,?,?,?,?)',
                            (eid, model, value['point'], value['independent_upper'], value['summed_marginal_interval_cents'], value['nlegs']))
            if seen != eligible or file_digest(context) != digest:
                raise ValueError('missing or changed pricing context')
            sources[str(context)] = digest
            db.commit()
        count = db.execute('SELECT COUNT(*) FROM features').fetchone()[0]
        assert count == index.execute('SELECT COUNT(*) FROM models').fetchone()[0]
        assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
    finally:
        db.close(); index.close()
    assert file_digest(index_path) == before
    return {'rows': count, 'sources': sources, 'index_sha256': before, 'database_sha256': file_digest(out)}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--spec', type=Path, required=True)
    p.add_argument('--freeze', type=Path, required=True)
    p.add_argument('--parent-plan', type=Path, required=True)
    p.add_argument('--implementation-seal', type=Path, required=True)
    p.add_argument('--batch-root', type=Path, nargs='+', required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    spec, plan = load_spec(a.spec, a.freeze, a.parent_plan)
    seal = json.loads(a.implementation_seal.read_text())
    if seal['specification_sha256'] != file_digest(a.spec) or seal['source_hashes'] != source_hashes():
        raise ValueError('validation implementation differs from sealed sources')
    files, empty, _ = discover(a.batch_root, plan)
    require_dates(files, empty, plan['dates'])
    a.out.mkdir(parents=True, exist_ok=False)
    hashes = source_hashes()
    spec_hash = file_digest(a.spec)
    atomic(a.out/'started.json', {'started_at': time.time(), 'specification_sha256': spec_hash,
        'source_hashes': hashes, 'implementation_seal_sha256': file_digest(a.implementation_seal),
        'independent_audit': 'pending'})
    index = a.out/'input.sqlite'
    coverage = build_index(a.batch_root, plan, index)
    require_dates(coverage['observed_dates'], coverage['empty_scope_dates'], plan['dates'])
    if coverage['missing_dates']:
        raise ValueError('incomplete paired validation coverage')
    # Include certified empty dates in the reporting horizon, never fabricated gaps.
    coverage['observed_dates'] = sorted(plan['dates'])
    feature_path = a.out/'features.sqlite'
    cert = build_features(index, files, feature_path)
    atomic(a.out/'feature_certificate.json', cert)
    db = sqlite3.connect(feature_path.resolve().as_uri()+'?mode=ro', uri=True)
    records = []; purge = None
    try:
        for policy in spec['policies']:
            for regime in spec['regimes']:
                filt = HeldoutFixtureFilter(Path(spec['exclusion_manifest']['path']),
                    spec['exclusion_manifest']['sha256'], plan['dates'], plan['timezone'])
                rows = filt.rows(iter_model(index, policy['model']))
                if policy['marginal_reserve_fraction']:
                    rows = with_reserve(rows, db, policy['model'], policy['marginal_reserve_fraction'], 'sha256:'+cert['database_sha256'])
                print('running', policy['id'], regime, flush=True)
                record, _ = evaluate_one(rows, policy['model'], policy['id'], policy['id'],
                    DeploymentConfig(**policy['configuration']), regime=='funded', coverage, plan,
                    a.out/(policy['id']+'__'+regime), artifact_codec='zstd', ledger_factory=DeploymentCappedRiskLedger)
                receipt = filt.receipt()
                if purge is not None and receipt != purge:
                    raise ValueError('candidate cohorts differ after purge')
                purge = receipt
                record['frozen_role'] = policy['role']
                record['marginal_reserve_fraction'] = policy['marginal_reserve_fraction']
                records.append(record)
                atomic(a.out/'progress.json', {'records': records, 'purge': purge})
    finally:
        db.close()
    assert len(records) == 28
    assert hashes == source_hashes() and spec_hash == file_digest(a.spec)
    assert cert['index_sha256'] == file_digest(index) and cert['database_sha256'] == file_digest(feature_path)
    atomic(a.out/'summary.json', {'records': records, 'purge': purge, 'coverage': coverage,
        'specification_sha256': spec_hash, 'source_hashes': hashes})
    atomic(a.out/'complete.json', {'portfolios': len(records), 'summary_sha256': file_digest(a.out/'summary.json'),
        'independent_admission_and_policy_audit': 'pending'})


if __name__ == '__main__':
    main()

import gzip
import json
from pathlib import Path
import sqlite3
import pytest
from run_frozen_august_validation import build_features, load_spec, require_dates


def test_frozen_spec_and_full_window_requirement(tmp_path):
    root = Path(__file__).resolve().parents[1]
    path = root/'config/mlb_august_candidates_20260909.json'
    receipt = root/'runs/mlb_validation_preparation_20260909/candidate_freeze.json'
    parent = root/'config/mlb_validation_20260907_expanded.json'
    spec, plan = load_spec(path, receipt, parent)
    assert len(spec['policies']) == 14
    assert len(plan['dates']) == 15
    assert not plan['evaluation']['purge_shared_fixtures_between_development_and_validation']
    dates = sorted(plan['dates'])
    with pytest.raises(ValueError, match='awaiting_completed'):
        require_dates(dates[:-1], [], dates)
    require_dates(dates[:-1], dates[-1:], dates)
    changed = tmp_path/'spec.json'
    changed.write_text(path.read_text()+' ')
    with pytest.raises(ValueError, match='changed after freeze'):
        load_spec(changed, receipt, parent)


def make_context(tmp_path, future=False):
    index = tmp_path/'input.sqlite'
    db = sqlite3.connect(index)
    db.execute('CREATE TABLE prints(id INTEGER,date TEXT,evaluation_id TEXT,at REAL)')
    db.execute('CREATE TABLE models(print_id INTEGER,model TEXT,payload TEXT)')
    db.execute("INSERT INTO prints VALUES(1,'2026-08-02','one',100)")
    models = ['kalshi', 'polymarket', 'exchange_blend_equal', 'exchange_blend_pm75']
    for model in models:
        # First selected leg NO: .5 point and .6 upper; second YES identical.
        db.execute('INSERT INTO models VALUES(1,?,?)', (model,json.dumps({'fair_point':.25,'stressed_upper':.4})))
    db.commit(); db.close()
    context = {m:{'interval':{'lower':.4,'point':.5,'upper':.6}} for m in models}
    for m in ('kalshi','polymarket'):
        context[m]['available_at'] = 101 if future else 99
    row = {'evaluation_id':'one','at':100,'legs':[{'side':'no'},{'side':'yes'}],
           'context':[context,context]}
    with gzip.open(tmp_path/'pricing_context.jsonl.gz','wt') as h:
        h.write(json.dumps(row)+'\n')
    return index, {'2026-08-02':tmp_path/'opportunities.json'}


def test_validation_features_preserve_no_complement_and_reject_future(tmp_path):
    index, files = make_context(tmp_path)
    out = tmp_path/'features.sqlite'
    cert = build_features(index, files, out)
    assert cert['rows'] == 4
    db = sqlite3.connect(out)
    assert db.execute('SELECT point,independent_upper FROM features').fetchone() == pytest.approx((.25,.36))
    db.close()
    other = tmp_path/'future'; other.mkdir()
    index, files = make_context(other, future=True)
    with pytest.raises(ValueError, match='future_source_availability'):
        build_features(index, files, other/'features.sqlite')


def test_all_frozen_policies_replay_same_purged_cohort(tmp_path, monkeypatch):
    import sys
    import run_frozen_august_validation as runner
    from mlb_disk_index import SHARED, file_digest
    from test_mlb_longitudinal_sweep import opportunity
    root = Path(__file__).resolve().parents[1]
    spec_path = root/'config/mlb_august_candidates_20260909.json'
    spec = json.loads(spec_path.read_text())
    dates = sorted(spec['dates'])
    # Acquisition certificates and feature storage are synthetic here; the
    # actual candidate evaluator, exclusion reader and risk ledger run below.
    monkeypatch.setattr(runner, 'discover', lambda *a: ({dates[0]:tmp_path/'unused'}, dates[1:], {}))
    def index_builder(roots, plan, path):
        db = sqlite3.connect(path)
        db.execute('CREATE TABLE prints(id INTEGER, date TEXT, evaluation_id TEXT, at REAL, shared TEXT)')
        db.execute('CREATE TABLE models(print_id INTEGER, model TEXT, payload TEXT)')
        for i, identifier in enumerate(('excluded','retained'),1):
            for model in spec['primary_models']:
                r = opportunity(dates[0],identifier,model,result=0)
                r['settled_at'] = r['at']+3600
                r['source']['start_at'] = r['at']+1800
                r['buckets']['fixture'] = ['mlb:26AUG011507STLTOR' if i==1 else 'mlb:26AUG031507STLTOR', 'mlb:26AUG031610MIANYM']
                if model == spec['primary_models'][0]:
                    db.execute('INSERT INTO prints VALUES(?,?,?,?,?)',(i,dates[0],identifier,r['at'],json.dumps({k:r[k] for k in SHARED})))
                db.execute('INSERT INTO models VALUES(?,?,?)',(i,model,json.dumps({k:v for k,v in r.items() if k not in SHARED})))
        db.commit(); db.close()
        return {'observed_dates':[dates[0]],'empty_scope_dates':dates[1:],'missing_dates':[]}
    monkeypatch.setattr(runner,'build_index',index_builder)
    def feature_builder(index, files, path):
        db = sqlite3.connect(path)
        db.execute('CREATE TABLE features(evaluation_id TEXT,model TEXT,point REAL,independent_upper REAL)')
        for model in spec['primary_models']:
            for eid in ('excluded','retained'):
                db.execute('INSERT INTO features VALUES(?,?,.2,.24)',(eid,model))
        db.commit(); db.close()
        return {'index_sha256':file_digest(index),'database_sha256':file_digest(path)}
    monkeypatch.setattr(runner,'build_features',feature_builder)
    out = tmp_path/'replay'
    seal = tmp_path/'seal.json'
    seal.write_text(json.dumps({'specification_sha256':file_digest(spec_path),'source_hashes':runner.source_hashes()}))
    monkeypatch.setattr(sys,'argv',['runner','--spec',str(spec_path),
        '--freeze',str(root/'runs/mlb_validation_preparation_20260909/candidate_freeze.json'),
        '--parent-plan',str(root/'config/mlb_validation_20260907_expanded.json'),
        '--implementation-seal',str(seal),
        '--batch-root',str(tmp_path),'--out',str(out)])
    runner.main()
    summary = json.loads((out/'summary.json').read_text())
    assert len(summary['records']) == 28
    assert summary['purge']['dates'][dates[0]] == {'input':2,'excluded':1,'retained':1}
    for r in summary['records']:
        assert r['portfolio']['evaluations'] == r['portfolio']['fills'] == 1
        assert r['portfolio']['trade_attributed_pnl'] == pytest.approx(35.9)
        assert len(r['sampled_statistics']['daily_contributions']) == 15
    import audit_frozen_august_validation as auditor
    verification = tmp_path/'independent_audit.json'
    monkeypatch.setattr(sys,'argv',['audit','--study',str(out),'--spec',str(spec_path),
        '--freeze',str(root/'runs/mlb_validation_preparation_20260909/candidate_freeze.json'),
        '--out',str(verification)])
    auditor.main()
    audit = json.loads(verification.read_text())
    assert audit['passed'] and len(audit['portfolios']) == 28

import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from creator_evidence_store import CreatorEvidenceStore
from review_creator_evidence_asof import review


def setup(tmp_path):
    runtime=tmp_path/'runtime.json';runtime.write_text(json.dumps({'mappings':[{'market_key':'m','fixture_key':'f'}]}))
    marks=tmp_path/'marks.sqlite';db=sqlite3.connect(marks)
    db.executescript('CREATE TABLE checkpoint(id INTEGER PRIMARY KEY,identity TEXT);CREATE TABLE labels(decision_seq INTEGER,horizon REAL,computed_at REAL,value TEXT)')
    identity={'horizons':[10],'identity':{'hashes':{str(runtime):hashlib.sha256(runtime.read_bytes()).hexdigest()}}}
    db.execute('INSERT INTO checkpoint VALUES(1,?)',(json.dumps(identity),))
    row={'decision_seq':1,'horizon_seconds':10,'rfq_id':'r','creator_id':'c','status':'observed',
        'entry_at':1,'valuation_at':11,'entry_scenario':{'legs':[{'market_key':'m'}]},'adverse_move_cents':.1}
    db.execute('INSERT INTO labels VALUES(1,10,12,?)',(json.dumps(row),));db.commit()
    return runtime,marks,db,CreatorEvidenceStore(tmp_path/'review.sqlite'),row


def test_restart_deduplicates_and_preserves_first_seen(tmp_path):
    runtime,marks,source,store,row=setup(tmp_path)
    assert store.import_source(marks,runtime,lambda:20)['added']==1
    store.close();store=CreatorEvidenceStore(tmp_path/'review.sqlite')
    assert store.import_source(marks,runtime,lambda:30)['added']==0
    assert store.db.execute('SELECT first_seen_at FROM evidence').fetchone()[0]==20
    store.close();source.close()


def test_changed_label_and_disappeared_label_are_rejected(tmp_path):
    runtime,marks,source,store,row=setup(tmp_path);store.import_source(marks,runtime,lambda:20)
    row['adverse_move_cents']=2;source.execute('UPDATE labels SET value=?',(json.dumps(row),));source.commit()
    with pytest.raises(ValueError,match='changed'):store.import_source(marks,runtime,lambda:30)
    source.execute('DELETE FROM labels');source.commit()
    with pytest.raises(ValueError,match='disappeared'):store.import_source(marks,runtime,lambda:30)
    assert store.db.execute('SELECT COUNT(*) FROM evidence').fetchone()[0]==1
    store.close();source.close()


def test_mid_import_failure_rolls_back_all_new_rows(tmp_path):
    runtime,marks,source,store,row=setup(tmp_path)
    row=dict(row,decision_seq=2,rfq_id='second');source.execute('INSERT INTO labels VALUES(2,10,12,?)',(json.dumps(row),));source.commit()
    store.db.executescript("CREATE TRIGGER fail_second BEFORE INSERT ON evidence WHEN NEW.decision_seq=2 BEGIN SELECT RAISE(ABORT,'injected'); END;")
    with pytest.raises(sqlite3.IntegrityError):store.import_source(marks,runtime,lambda:20)
    assert store.db.execute('SELECT COUNT(*) FROM evidence').fetchone()[0]==0
    assert store.db.execute('SELECT COUNT(*) FROM sources').fetchone()[0]==0
    store.db.execute('DROP TRIGGER fail_second');store.db.commit()
    assert store.import_source(marks,runtime,lambda:20)['added']==2
    store.close();source.close()


def test_uncommitted_source_label_is_not_visible(tmp_path):
    runtime,marks,source,store,row=setup(tmp_path)
    row=dict(row,decision_seq=2,rfq_id='second');source.execute('INSERT INTO labels VALUES(2,10,12,?)',(json.dumps(row),))
    assert store.import_source(marks,runtime,lambda:20)['labels']==1
    source.commit();assert store.import_source(marks,runtime,lambda:21)['added']==1
    store.close();source.close()


def test_mapping_identity_change_rejected(tmp_path):
    runtime,marks,source,store,row=setup(tmp_path);runtime.write_text('{}')
    with pytest.raises(ValueError,match='runtime identity'):store.import_source(marks,runtime,lambda:20)
    store.close();source.close()


def test_missing_creator_cannot_enter_observed_evidence(tmp_path):
    runtime,marks,source,store,row=setup(tmp_path);row['creator_id']=None
    source.execute('UPDATE labels SET value=?',(json.dumps(row),));source.commit()
    with pytest.raises(ValueError,match='lacks creator'):store.import_source(marks,runtime,lambda:20)
    assert store.db.execute('SELECT COUNT(*) FROM evidence').fetchone()[0]==0
    store.close();source.close()


def test_asof_waits_for_post_commit_confirmation(tmp_path):
    runtime,marks,source,store,row=setup(tmp_path)
    ticks=iter([20,22]);store.import_source(marks,runtime,lambda:next(ticks))
    assert review(tmp_path/'review.sqlite',21)['available_labels']==0
    assert review(tmp_path/'review.sqlite',22)['available_labels']==1
    store.close();source.close()


def test_receipt_failure_recovers_without_backdating(tmp_path):
    runtime,marks,source,store,row=setup(tmp_path)
    store.db.executescript("CREATE TRIGGER fail_receipt BEFORE INSERT ON availability BEGIN SELECT RAISE(ABORT,'receipt'); END;")
    with pytest.raises(sqlite3.IntegrityError):store.import_source(marks,runtime,lambda:20)
    assert store.db.execute('SELECT COUNT(*) FROM evidence').fetchone()[0]==1
    assert review(tmp_path/'review.sqlite',25)['available_labels']==0
    store.db.execute('DROP TRIGGER fail_receipt');store.db.commit()
    assert store.import_source(marks,runtime,lambda:30)['added']==0
    assert review(tmp_path/'review.sqlite',25)['available_labels']==0
    assert review(tmp_path/'review.sqlite',30)['available_labels']==1
    store.close();source.close()

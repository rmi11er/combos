import importlib.util
from pathlib import Path
import sqlite3

spec=importlib.util.spec_from_file_location('markout_launcher',Path(__file__).resolve().parents[1]/'scripts/capture_with_scenario_worker.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


def test_checkpoint_readiness_waits_for_committed_row(tmp_path):
    path=tmp_path/'decisions.sqlite'
    assert not module.decision_checkpoint_ready(path)
    db=sqlite3.connect(path);db.execute('PRAGMA journal_mode=WAL')
    assert not module.decision_checkpoint_ready(path)
    db.execute('CREATE TABLE checkpoint(id INTEGER PRIMARY KEY)');db.commit()
    assert not module.decision_checkpoint_ready(path)
    db.execute('INSERT INTO checkpoint VALUES(1)')
    assert not module.decision_checkpoint_ready(path)
    db.commit()
    assert module.decision_checkpoint_ready(path)
    db.close()

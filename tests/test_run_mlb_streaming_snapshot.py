import json,sqlite3,sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import run_mlb_streaming_snapshot as job

def test_refuses_existing_output(tmp_path,monkeypatch):
 out=tmp_path/'old';out.mkdir();(out/'important').write_text('original')
 monkeypatch.setattr(sys,'argv',['job','--batch-root',str(tmp_path),'--plan',str(tmp_path/'plan'),'--out',str(out)])
 with pytest.raises(FileExistsError):job.main()
 assert (out/'important').read_text()=='original'

def test_atomic_final_manifest_and_source_change_failure(tmp_path,monkeypatch):
 plan=tmp_path/'plan';plan.write_text('{}');out=tmp_path/'new';hashes={'source':'fixed'}
 monkeypatch.setattr(job,'source_hashes',lambda:dict(hashes))
 def fake_run():
  with sqlite3.connect(out/'input.sqlite') as db:db.execute('CREATE TABLE metadata(key,value)');db.execute('INSERT INTO metadata VALUES(?,?)',('coverage','{}'))
  (out/'summary.json').write_text(json.dumps({'records':[{}]*48}))
 monkeypatch.setattr(job.runner,'main',fake_run)
 monkeypatch.setattr(sys,'argv',['job','--batch-root',str(tmp_path),'--plan',str(plan),'--out',str(out)])
 job.main();assert (out/'snapshot_complete.json').exists()
 out=tmp_path/'changed'
 def changed():fake_run();hashes['source']='modified'
 monkeypatch.setattr(job.runner,'main',changed)
 monkeypatch.setattr(sys,'argv',['job','--batch-root',str(tmp_path),'--plan',str(plan),'--out',str(out)])
 with pytest.raises(RuntimeError,match='code_or_plan_changed'):job.main()
 assert not (out/'snapshot_complete.json').exists()
 assert (out/'snapshot_failed.json').exists()

#!/usr/bin/env python3
"""Publish a fresh, immutable full-policy snapshot. Local research only.

Restart is intentionally a fresh replay, never appending cash/positions after an
out-of-order date or a changed fixture purge. snapshot_complete.json is the final
publication marker; incomplete folders are retained for diagnosis.
"""
import argparse,json,os,resource,sqlite3,sys,time
from pathlib import Path
from mlb_disk_index import file_digest
import mlb_streaming_longitudinal as runner
ROOT=Path(__file__).resolve().parents[1]

def atomic(path,data):
 temporary=path.with_suffix(path.suffix+'.tmp')
 temporary.write_text(json.dumps(data,indent=2,allow_nan=False)+'\n');os.replace(temporary,path)

def source_hashes():
 files=[Path(m.__file__).resolve() for m in list(sys.modules.values()) if getattr(m,'__file__',None) and (Path(m.__file__).resolve().is_relative_to(ROOT/'src') or Path(m.__file__).resolve().is_relative_to(ROOT/'scripts')) and str(m.__file__).endswith('.py')]+[Path(__file__).resolve()]
 files=sorted(set(files))
 return {str(p.relative_to(ROOT)):file_digest(p) for p in sorted(files)}

def main():
 p=argparse.ArgumentParser();p.add_argument('--batch-root',nargs='+',type=Path,required=True);p.add_argument('--plan',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--artifact-codec',choices=('gzip','zstd'),default='gzip');a=p.parse_args()
 # Never overwrite a retained oracle, completed snapshot, or interrupted output.
 a.out.mkdir(parents=True,exist_ok=False);began=time.time();before=source_hashes();plan_hash=file_digest(a.plan)
 atomic(a.out/'snapshot_started.json',{'started_at':began,'plan':str(a.plan.resolve()),'plan_sha256':plan_hash,'sources':before,'artifact_format_version':2,'artifact_codec':a.artifact_codec,'restart_policy':'new output directory; full certified snapshot replay, no checkpoint reuse'})
 try:
  sys.argv=[str(ROOT/'scripts/mlb_streaming_longitudinal.py'),'--batch-root',*[str(v) for v in a.batch_root],'--plan',str(a.plan),'--out',str(a.out),'--artifact-codec',a.artifact_codec]
  runner.main()
  if before!=source_hashes() or plan_hash!=file_digest(a.plan):raise RuntimeError('code_or_plan_changed_during_snapshot')
  summary=json.loads((a.out/'summary.json').read_text())
  if len(summary['records'])!=48:raise RuntimeError('expected_all_48_policy_regimes')
  with sqlite3.connect(a.out/'input.sqlite') as db:metadata={k:json.loads(v) for k,v in db.execute('SELECT key,value FROM metadata')}
  outputs={p.name:{'bytes':p.stat().st_size,'sha256':file_digest(p)} for p in sorted(a.out.iterdir()) if p.is_file() and p.name!='snapshot_started.json'}
  atomic(a.out/'snapshot_complete.json',{'started_at':began,'completed_at':time.time(),'elapsed_seconds':time.time()-began,'peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'records':48,'artifact_format_version':2,'artifact_codec':summary.get('artifact_codec',{'name':a.artifact_codec}),'source_hashes':before,'plan_sha256':plan_hash,'input_metadata':metadata,'outputs':outputs,'restart_policy':'fresh full replay only; no append or cash reset'})
 except BaseException as exc:
  atomic(a.out/'snapshot_failed.json',{'at':time.time(),'exception':type(exc).__name__,'message':str(exc)})
  raise
if __name__=='__main__':main()

"""Supervise a bounded shadow capture, pricing, markouts and evidence importer."""
import argparse
import json
from pathlib import Path
import signal
import subprocess
import sys
import time
from capture_with_scenario_worker import decision_checkpoint_ready


def run(a):
    a.out.mkdir(parents=True,exist_ok=False)
    root=Path(__file__).resolve().parents[1]
    pipeline=None;importer=None
    try:
        with (a.out/'pipeline.log').open('w') as log:
            pipeline=subprocess.Popen([sys.executable,str(root/'scripts/capture_with_scenario_worker.py'),
                '--capture',str(a.capture),'--out',str(a.out/'pipeline'),'--catalog',str(a.catalog),
                '--policy',str(a.policy),'--key-file',str(a.key_file),'--markouts','--seconds',str(a.seconds)],stdout=log,stderr=subprocess.STDOUT)
        marks=a.out/'pipeline/markouts/markouts.sqlite'
        deadline=time.monotonic()+30
        while not decision_checkpoint_ready(marks):
            if pipeline.poll() is not None:raise RuntimeError('pipeline stopped before markout checkpoint')
            if time.monotonic()>deadline:raise RuntimeError('markout checkpoint startup timeout')
            time.sleep(.1)
        plan=a.out/'evidence_plan.json';plan.write_text(json.dumps({'captures':[{'marks':str(marks.resolve()),'runtime':str((a.capture/'runtime.json').resolve())}]},indent=2))
        with (a.out/'importer.log').open('w') as log:
            importer=subprocess.Popen([sys.executable,str(root/'scripts/import_creator_evidence.py'),
                '--plan',str(plan),'--out',str(a.evidence),'--seconds',str(a.seconds+120)],stdout=log,stderr=subprocess.STDOUT)
        deadline=time.monotonic()+a.seconds+300
        while pipeline.poll() is None or importer.poll() is None:
            if pipeline.poll() not in (None,0) or importer.poll() not in (None,0):raise RuntimeError('integrated child failed')
            if pipeline.poll() is None and importer.poll() is not None:raise RuntimeError('importer stopped before pipeline')
            if time.monotonic()>deadline:raise RuntimeError('integrated deadline exceeded')
            (a.out/'status.json').write_text(json.dumps({'status':'running','pipeline_pid':pipeline.pid,'importer_pid':importer.pid,'checked_at':time.time()}))
            time.sleep(1)
        result={'status':'completed','pipeline_returncode':pipeline.returncode,'importer_returncode':importer.returncode,'orders_submitted':0}
        (a.out/'completion.json').write_text(json.dumps(result,indent=2));(a.out/'status.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
    finally:
        for child in (importer,pipeline):
            if child and child.poll() is None:
                child.send_signal(signal.SIGINT)
                try:child.wait(timeout=60)
                except subprocess.TimeoutExpired:child.kill();child.wait(timeout=10)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('capture','out','catalog','policy','key-file','evidence'):p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--seconds',type=float,default=120)
    run(p.parse_args())

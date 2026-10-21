"""Attach a durable research worker to a prepared bounded three-source capture."""
import argparse,importlib.util,json,subprocess,sys,time,signal,math,sqlite3
from pathlib import Path


def decision_checkpoint_ready(path):
    if not path.is_file():return False
    try:
        db=sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True,timeout=.1)
        try:return db.execute('SELECT 1 FROM checkpoint WHERE id=1').fetchone() is not None
        finally:db.close()
    except sqlite3.OperationalError:return False


def run(a):
    if not math.isfinite(a.seconds) or not 90<=a.seconds<=600:raise ValueError('bounded capture duration required')
    root=Path(__file__).resolve().parents[1]
    spec=importlib.util.spec_from_file_location('capture',root/'scripts/shadow_research_capture.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    if not (a.capture/'prepared.json').is_file() or (a.capture/'events.sqlite').exists():raise ValueError('fresh prepared capture required')
    if a.out.exists():raise ValueError('fresh worker output required')
    a.out.mkdir(parents=True)
    capture_log=(a.out/'capture.log').open('w');worker_log=(a.out/'worker.log').open('w');worker=None;markouts=None;markout_log=None
    capture=subprocess.Popen([sys.executable,str(root/'scripts/shadow_research_capture.py'),'run','--out',str(a.capture),'--key-file',str(a.key_file),'--seconds',str(a.seconds),'--code-freeze',module.source_digest()],stdout=capture_log,stderr=capture_log)
    try:
        deadline=time.monotonic()+20
        while not (a.capture/'events.sqlite').exists():
            if capture.poll() is not None:raise RuntimeError('capture ended before initialization')
            if time.monotonic()>=deadline:raise RuntimeError('capture initialization timeout')
            time.sleep(.1)
        worker=subprocess.Popen([sys.executable,str(root/'scripts/run_scenario_worker.py'),'--db',str(a.capture/'events.sqlite'),'--runtime',str(a.capture/'runtime.json'),'--catalog',str(a.catalog),'--weights',str(a.capture/'weighting.json'),'--out',str(a.out/'worker'),'--seconds',str(a.seconds+90)]+(['--policy',str(a.policy)] if a.policy else []),stdout=worker_log,stderr=worker_log)
        if a.markouts:
            ready_by=time.monotonic()+20
            while not decision_checkpoint_ready(a.out/'worker/decisions.sqlite'):
                if worker.poll() is not None or capture.poll() is not None:raise RuntimeError('source or pricing stopped before markout startup')
                if time.monotonic()>ready_by:raise RuntimeError('pricing checkpoint initialization timeout')
                time.sleep(.1)
            markout_log=(a.out/'markouts.log').open('w')
            markouts=subprocess.Popen([sys.executable,str(root/'scripts/run_markout_worker.py'),
                '--source',str(a.capture/'events.sqlite'),'--decisions',str(a.out/'worker/decisions.sqlite'),
                '--runtime',str(a.capture/'runtime.json'),'--catalog',str(a.catalog),
                '--weights',str(a.capture/'weighting.json'),'--out',str(a.out/'markouts'),
                '--seconds',str(a.seconds+105)],stdout=markout_log,stderr=markout_log)
        deadline=time.monotonic()+a.seconds+240
        while any(p is not None and p.poll() is None for p in (capture,worker,markouts)):
            if any(p is not None and p.poll() not in (None,0) for p in (capture,worker,markouts)):raise RuntimeError('integrated child failed')
            if capture.poll() is None and worker.poll() is not None:raise RuntimeError('worker ended during capture')
            if markouts is not None and worker.poll() is None and markouts.poll() is not None:raise RuntimeError('markout worker ended during pricing')
            if time.monotonic()>deadline:raise RuntimeError('integrated capture deadline')
            (a.out/'status.json').write_text(json.dumps({'capture_pid':capture.pid,'worker_pid':worker.pid,'markout_pid':markouts.pid if markouts else None,'status':'running','checked_at':time.time(),'requested_seconds':a.seconds}))
            time.sleep(1)
        capture_code=capture.returncode;worker_code=worker.returncode
        result={'capture_returncode':capture_code,'worker_returncode':worker_code,'markout_returncode':markouts.returncode if markouts else None,'orders_submitted':0,'requested_seconds':a.seconds}
        (a.out/'completion.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
        if capture_code or worker_code:raise SystemExit(1)
    finally:
        # Capture owns cleanup of its children; avoid abrupt termination while healthy.
        for child in (markouts,worker,capture):
            if child and child.poll() is None:
                child.send_signal(signal.SIGINT)
                try:child.wait(timeout=60)
                except subprocess.TimeoutExpired:child.kill();child.wait(timeout=10)
        capture_log.close();worker_log.close()
        if markout_log:markout_log.close()

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('capture','out','catalog','key-file'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--policy',type=Path)
    p.add_argument('--markouts',action='store_true')
    p.add_argument('--seconds',type=float,default=120)
    run(p.parse_args())

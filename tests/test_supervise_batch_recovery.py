from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from supervise_batch_recovery import recovery_candidate,TRANSIENT_END

def stage(**kw):
    return dict(status='failed',exit_code=1,attempts=1,ended_at='2026-09-09T00:00:00Z',log='log',**kw)

def test_only_exact_terminal_transient_failure_is_retried():
    s={'stages':{'day/cohort':stage()}}
    assert recovery_candidate(s,2,lambda p:'trace\n'+TRANSIENT_END)[0][0]=='day/cohort'
    for message in ('RuntimeError: Public API HTTP 401','ValueError: mapping','ValueError: budget',TRANSIENT_END+'\nValueError: other'):
        assert recovery_candidate(s,2,lambda p:message)[0] is None

def test_attempt_limit_and_newer_success_prevent_restart():
    s={'stages':{'old':stage()}};s['stages']['old']['attempts']=2
    assert recovery_candidate(s,2,lambda p:TRANSIENT_END)[1]=='stage_attempt_limit'
    s['stages']['old']['attempts']=1
    s['stages']['new']={**stage(),'status':'complete','exit_code':0,'ended_at':'2026-09-09T01:00:00Z'}
    assert recovery_candidate(s,2,lambda p:TRANSIENT_END)[0] is None

def test_missing_or_running_stage_is_not_a_failure():
    assert recovery_candidate({'stages':{}},2,lambda p:TRANSIENT_END)[0] is None
    assert recovery_candidate({'stages':{'x':{'status':'running'}}},2,lambda p:TRANSIENT_END)[0] is None


def test_supervisor_recovers_exited_fixture_without_network(tmp_path):
    import json,subprocess,time
    from supervise_batch_recovery import identity
    fake=tmp_path/'mlb_historical_batch.py'
    fake.write_text('''import json,sys,time,fcntl
from pathlib import Path
root=Path(sys.argv[sys.argv.index('--out')+1])
lock=(root/'batch.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
s=root/'batch_status.json'
if not s.exists():
 while not (root/'release').exists():time.sleep(.02)
 log=root/'failed.log';log.write_text('RuntimeError: Public request retries exhausted\\n')
 s.write_text(json.dumps({'status':'failed','stages':{'date/cohort':{'status':'failed','exit_code':1,'attempts':1,'ended_at':'2026-09-09T00:00:00Z','log':str(log)}}}))
else:
 s.write_text(json.dumps({'status':'complete','stages':{}}));time.sleep(.5)
''')
    (tmp_path/'batch_manifest.json').write_text('{}')
    command=[sys.executable,str(fake),'--out',str(tmp_path),'--max-metadata-requests','15000']
    batch=subprocess.Popen(command)
    supervisor=None
    try:
        observed=identity(batch.pid)
        plan=tmp_path/'plan.json'
        plan.write_text(json.dumps({'batch_root':str(tmp_path),'cwd':str(tmp_path),
             'command':command,'max_stage_attempts':2,'attach_identity':observed}))
        out=tmp_path/'supervisor'
        supervisor=subprocess.Popen([sys.executable,str(Path(__file__).resolve().parents[1]/'scripts/supervise_batch_recovery.py'),
            '--plan',str(plan),'--attach-pid',str(batch.pid),'--out',str(out)])
        deadline=time.monotonic()+45
        while not (out/'status.json').exists():
            assert supervisor.poll() is None and time.monotonic()<deadline
            time.sleep(.05)
        assert json.loads((out/'status.json').read_text())['restarts']==[]
        (tmp_path/'release').touch();batch.wait(timeout=5)
        supervisor.wait(timeout=40)
        state=json.loads((out/'status.json').read_text())
        assert supervisor.returncode==0 and state['status']=='batch_finished'
        assert len(state['restarts'])==1 and state['restarts'][0]['previous_attempts']==1
    finally:
        for process in (batch,supervisor):
            if process is not None and process.poll() is None:
                process.terminate();process.wait(timeout=5)

#!/usr/bin/env python3
"""Recover one explicitly identified transient failure without altering batch code.

An external supervisor retains the frozen batch generation and its persisted
stage-attempt limits. It never restarts live workers or broadens API budgets.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

TRANSIENT_END = 'RuntimeError: Public request retries exhausted'


def identity(pid):
    if not isinstance(pid, int) or pid <= 0:
        return None
    r = subprocess.run(['ps','-p',str(pid),'-o','lstart=,command='],
                       capture_output=True,text=True,check=False)
    return r.stdout.strip() if r.returncode == 0 else None


def recovery_candidate(state, max_attempts, read_log):
    terminal = [(k,s) for k,s in state.get('stages',{}).items() if s.get('ended_at')]
    if not terminal:
        return None, 'no_terminal_stage'
    key, stage = max(terminal,key=lambda pair:pair[1]['ended_at'])
    if stage.get('status') != 'failed' or stage.get('exit_code') in (None,0):
        return None, 'latest_stage_not_failed_process'
    attempts = stage.get('attempts')
    if type(attempts) is not int or attempts >= max_attempts or attempts < 1:
        return None, 'stage_attempt_limit'
    if read_log(stage['log']).rstrip().splitlines()[-1:] != [TRANSIENT_END]:
        return None, 'failure_not_allowlisted'
    return (key,stage), 'retryable_public_request_exhaustion'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(value,indent=2)+'\n');tmp.replace(path)


def main():
    p=argparse.ArgumentParser();p.add_argument('--plan',type=Path,required=True)
    p.add_argument('--attach-pid',type=int,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();plan=json.loads(a.plan.read_text());root=Path(plan['batch_root']).resolve()
    command=plan['command'];attempts=plan['max_stage_attempts']
    if attempts != 2 or '--max-stage-attempts' in command:
        raise ValueError('this_recovery_plan_requires_unchanged_default_two_attempts')
    if '--max-metadata-requests' not in command or command[command.index('--max-metadata-requests')+1]!='15000':
        raise ValueError('unexpected_request_budget')
    if str(root)!=str(Path(command[command.index('--out')+1]).resolve()):
        raise ValueError('batch_root_command_mismatch')
    observed=identity(a.attach_pid)
    if not observed or 'mlb_historical_batch.py' not in observed or observed != plan['attach_identity']:
        raise ValueError('attached_batch_not_live')
    a.out.mkdir(parents=True,exist_ok=False)
    pinned={str(a.plan.resolve()):sha(a.plan),str(Path(__file__).resolve()):sha(__file__),
            str(root/'batch_manifest.json'):sha(root/'batch_manifest.json')}
    # Same lock path across independently named output directories.
    with (root/'recovery_supervisor.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        state={'supervisor_pid':os.getpid(),'batch_pid':a.attach_pid,'batch_identity':observed,
               'pinned_sha256':pinned,'restarts':[],'status':'watching'}
        child=None
        with (a.out/'batch_restarts.log').open('a') as log:
            while True:
                for path,h in pinned.items():
                    if sha(path)!=h:raise RuntimeError('supervisor_or_generation_changed')
                current=identity(state['batch_pid'])
                if child is not None and child.poll() is not None:
                    current=None
                state['checked_at']=time.time()
                if current == state['batch_identity']:
                    save(a.out/'status.json',state);time.sleep(15);continue
                if current is not None:
                    state.update(status='stopped',reason='pid_identity_changed');break
                batch=json.loads((root/'batch_status.json').read_text())
                if batch.get('status') in ('complete','complete_with_pricing_gaps'):
                    state.update(status='batch_finished',batch_status=batch['status']);break
                candidate,reason=recovery_candidate(batch,attempts,lambda p:Path(p).read_text(errors='replace')[-12000:])
                if candidate is None:
                    state.update(status='stopped',reason=reason);break
                key,stage=candidate
                if identity(stage.get('child_pid')) is not None:
                    state.update(status='stopped',reason='failed_stage_pid_still_present');break
                # Existing batch lock prevents concurrent launch/recovery.
                with (root/'batch.lock').open('a') as batch_lock:
                    try:fcntl.flock(batch_lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
                    except BlockingIOError:
                        state.update(status='stopped',reason='another_batch_holds_lock');break
                state['restarts'].append({'stage':key,'previous_attempts':stage['attempts'],
                    'at':time.time(),'failure_log':stage['log'],'failure_log_sha256':sha(stage['log'])})
                child=subprocess.Popen(command,cwd=plan['cwd'],stdout=log,stderr=subprocess.STDOUT)
                observed=identity(child.pid)
                if observed is None:
                    child.wait();state.update(status='stopped',reason='restart_exited_before_observation');break
                state.update(batch_pid=child.pid,batch_identity=observed,status='watching')
                save(a.out/'status.json',state)
        save(a.out/'status.json',state)


if __name__=='__main__':main()

"""Wait for the complete frozen cohort, then run replay and audit exactly once."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(value,indent=2)+'\n'); temp.replace(path)


def identity(pid):
    if type(pid) is not int or pid <= 0:
        return None
    r = subprocess.run(['ps','-p',str(pid),'-o','lstart=,command='],capture_output=True,text=True)
    return r.stdout.strip() if r.returncode==0 else None


def pending_dates(batch, dates):
    terminal = {'complete','complete_empty_eligible_scope'}
    return [d for d in dates if batch.get('days',{}).get(d,{}).get('status') not in terminal]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--plan',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    a = p.parse_args(); plan = json.loads(a.plan.read_text())
    root = Path(plan['cwd'])
    a.out.mkdir(parents=True,exist_ok=False)
    pinned = {**plan['pinned_sha256'],str(a.plan.resolve()):sha(a.plan),str(Path(__file__).resolve()):sha(__file__)}
    state = {'supervisor_pid':os.getpid(),'status':'waiting_for_complete_cohort','stages':[], 'started_at':time.time()}
    def update(**fields):
        state.update(fields,checked_at=time.time());save(a.out/'status.json',state)
    def check_pins():
        for path,digest in pinned.items():
            if sha(path)!=digest:
                raise ValueError('pinned_input_or_code_changed:'+path)
    with Path(plan['lock_path']).open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        try:
            while True:
                check_pins()
                batch = json.loads(Path(plan['batch_status']).read_text())
                missing = pending_dates(batch,plan['validation_dates'])
                free = shutil.disk_usage(root).free
                if not missing and free >= plan['minimum_free_bytes']:
                    break
                monitor = json.loads(Path(plan['recovery_status']).read_text())
                live_identity = identity(monitor.get('batch_pid'))
                live = live_identity is not None and live_identity == monitor.get('batch_identity')
                recovery_live = identity(monitor.get('supervisor_pid')) == plan['recovery_identity']
                update(pending_dates=missing,free_bytes=free,
                    status='waiting_for_complete_cohort' if missing else 'waiting_for_disk_headroom',
                    collection_process_live=live, recovery_process_live=recovery_live)
                if missing and not live and not recovery_live:
                    raise RuntimeError('collection_and_recovery_terminal_with_incomplete_dates')
                time.sleep(15)
            for stage in plan['stages']:
                check_pins()
                output = Path(stage['expected_receipt'])
                if output.exists():
                    raise RuntimeError('stage_output_already_exists:'+str(output))
                log_path = a.out/(stage['name']+'.log')
                with log_path.open('x') as log:
                    child = subprocess.Popen(stage['command'],cwd=root,stdout=log,stderr=subprocess.STDOUT)
                    item = {'name':stage['name'],'pid':child.pid,'started_at':time.time(),'log':str(log_path),'status':'running'}
                    state['stages'].append(item)
                    while child.poll() is None:
                        update(status='running_'+stage['name'],child_pid=child.pid)
                        time.sleep(5)
                    item.update(exit_code=child.returncode,ended_at=time.time())
                if child.returncode != 0:
                    item['status']='failed'
                    raise RuntimeError('stage_failed:'+stage['name'])
                check_pins()
                receipt = json.loads(output.read_text())
                if any(receipt.get(k)!=v for k,v in stage['required_receipt_fields'].items()):
                    raise RuntimeError('stage_receipt_not_complete:'+stage['name'])
                item.update(status='complete',receipt_sha256=sha(output))
                update()
            update(status='complete',ended_at=time.time())
        except BaseException as exc:
            update(status='stopped',error=type(exc).__name__+':'+str(exc),ended_at=time.time())
            raise


if __name__=='__main__':
    main()

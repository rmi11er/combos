#!/usr/bin/env python3
"""Run verified storage maintenance only when new research stages complete."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def checkpoint(state):
    return {key: stage['output_sha256'] for key, stage in state.get('stages', {}).items()
            if (key.startswith('validation/') or key.endswith('/replay'))
            and stage.get('status') == 'complete' and stage.get('exit_code') == 0
            and stage.get('output_sha256')}


def save(path, value):
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(value, indent=2)+'\n')
    temp.replace(path)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--batch-root', required=True, type=Path)
    p.add_argument('--out', required=True, type=Path)
    p.add_argument('--timing-root', action='append', type=Path, default=[])
    p.add_argument('--watch', action='store_true')
    p.add_argument('--execute', action='store_true')
    p.add_argument('--max-hours', type=float, default=48)
    a = p.parse_args()
    if not 0 < a.max_hours <= 48:
        raise ValueError('max_hours_out_of_bounds')
    a.out.mkdir(parents=True, exist_ok=True)
    with (a.out/'watch.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        scripts = [Path(__file__), ROOT/'scripts/deduplicate_validation_clones.py', ROOT/'scripts/compress_completed_json.py']
        frozen = {str(f.resolve()): digest(f) for f in scripts}
        status_path = a.out/'status.json'
        previous = json.loads(status_path.read_text()).get('completed_checkpoint') if status_path.exists() else None
        status = {'pid':os.getpid(), 'started_at':time.time(), 'frozen_sha256':frozen,
                  'completed_checkpoint':previous, 'execute':a.execute}
        deadline = time.monotonic()+a.max_hours*3600
        try:
            while time.monotonic() < deadline:
                if any(digest(Path(f)) != h for f,h in frozen.items()):
                    raise ValueError('storage_workflow_code_changed')
                state = json.loads((a.batch_root/'batch_status.json').read_text())
                identity = hashlib.sha256(json.dumps(checkpoint(state),sort_keys=True).encode()).hexdigest()
                free = shutil.disk_usage(a.out).free
                status.update(updated_at=time.time(), free_disk_bytes=free,
                              capacity_review='urgent' if free < 15*2**30 else 'review' if free < 20*2**30 else 'monitor',
                              status='watching', observed_checkpoint=identity)
                save(status_path,status)
                if identity != previous:
                    commands = [
                        [sys.executable,str(scripts[1]),'--batch-root',str(a.batch_root),'--out',str(a.out/'clones'),'--max-files','10000'],
                        [sys.executable,str(scripts[2]),'--batch-root',str(a.batch_root),'--out',str(a.out/'compression'),'--max-files','200']]
                    for timing in a.timing_root:
                        commands[1] += ['--timing-root',str(timing)]
                    if not a.execute:
                        status.update(status='plan', commands=commands)
                        save(status_path,status)
                        return
                    for index,command in enumerate(commands):
                        command.append('--execute')
                        log = a.out/f'{identity[:16]}_{index}.log'
                        with log.open('a') as handle:
                            child = subprocess.Popen(command,stdout=handle,stderr=subprocess.STDOUT)
                            status.update(status='maintaining_completed_artifacts',child_pid=child.pid,command=command,log=str(log))
                            save(status_path,status)
                            code = child.wait()
                        status.pop('child_pid',None)
                        if code:
                            raise RuntimeError(f'maintenance_exit_{code}: {log}')
                    previous = identity
                    status.update(completed_checkpoint=identity, completed_at=time.time())
                    save(status_path,status)
                if not a.watch:
                    status.update(status='snapshot_complete',updated_at=time.time())
                    save(status_path,status)
                    return
                time.sleep(30)
            status.update(status='runtime_complete',updated_at=time.time())
            save(status_path,status)
        except BaseException as exc:
            status.update(status='stopped',reason=f'{type(exc).__name__}: {exc}',updated_at=time.time())
            save(status_path,status)
            raise


if __name__ == '__main__':
    main()

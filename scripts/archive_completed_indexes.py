#!/usr/bin/env python3
"""Losslessly compress closed, completed-day scratch indexes; preserve raw tape."""
import argparse
import fcntl
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time


def digest(path, compressed=False):
    h=hashlib.sha256()
    with (gzip.open(path,'rb') if compressed else path.open('rb')) as f:
        for chunk in iter(lambda:f.read(1024*1024),b''): h.update(chunk)
    return h.hexdigest()


def save(path,value):
    tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(value,indent=2)+'\n');tmp.replace(path)


def archive(path):
    # No open writer/readers, WAL, or pending SQLite rollback journal.
    if any(Path(str(path)+suffix).exists() for suffix in ('-wal','-journal','-shm')):
        return {'status':'deferred_sqlite_auxiliary_files'}
    opened=subprocess.run(['lsof','-t',str(path)],capture_output=True,text=True)
    if opened.returncode not in (0,1) or opened.stdout.strip():
        return {'status':'deferred_open_or_unverified_file'}
    before=path.stat();expected=digest(path)
    dest=Path(str(path)+'.gz');temp=Path(str(dest)+'.tmp')
    if dest.exists():
        if digest(dest,True)!=expected:
            raise ValueError('existing_archive_mismatch')
    else:
        with path.open('rb') as src,gzip.open(temp,'wb',compresslevel=1) as dst:
            shutil.copyfileobj(src,dst,1024*1024)
        if digest(temp,True)!=expected:
            raise ValueError('archive_roundtrip_failed')
        temp.replace(dest)
    after=path.stat()
    if (after.st_size,after.st_mtime_ns)!=(before.st_size,before.st_mtime_ns) or digest(path)!=expected:
        raise ValueError('source_index_changed_during_archive')
    record={'status':'verified_archive','original':str(path),'archive':str(dest),
            'uncompressed_sha256':expected,'archive_sha256':digest(dest),
            'original_bytes':before.st_size,'archive_bytes':dest.stat().st_size,
            'raw_tape_and_report_inputs_retained':True,'at':time.time()}
    save(Path(str(dest)+'.manifest.json'),record)
    path.unlink()
    return record


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--batch-root',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--watch',action='store_true')
    p.add_argument('--max-hours',type=float,default=48.)
    args=p.parse_args();args.out.mkdir(parents=True,exist_ok=True)
    with (args.out/'archive.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        status={'pid':os.getpid(),'days':{}};end=time.monotonic()+args.max_hours*3600
        while True:
            state=json.loads((args.batch_root/'batch_status.json').read_text())
            for date,day in state.get('days',{}).items():
                if day.get('status') not in ('complete','complete_empty_eligible_scope'):
                    continue
                stage=state['stages'].get(date+'/cohort',{})
                if stage.get('status')!='complete':
                    continue
                index=args.batch_root/date/'cohort/tape_index.sqlite'
                if str(index.resolve()) in stage.get('output_sha256',{}):
                    raise ValueError('index_is_a_required_frozen_output')
                if index.exists():
                    status['days'][date]=archive(index)
            status.update(status='watching' if args.watch else 'available_completed_indexes_archived',
                          updated_at=time.time(),free_disk_bytes=shutil.disk_usage(args.batch_root).free)
            save(args.out/'status.json',status)
            if not args.watch or state.get('status')=='complete':return
            if time.monotonic()>end:raise TimeoutError('archive_watch_deadline')
            time.sleep(30)


if __name__=='__main__':main()

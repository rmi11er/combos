#!/usr/bin/env python3
"""Bounded exact-byte native compression for four explicitly pinned generated DBs."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import sqlite3
import tempfile
from compress_completed_json import compress_copy, allocated, probe
from deduplicate_validation_clones import sha, fingerprint, closed, atomic_json

ROOT=Path(__file__).resolve().parents[1]
ALLOWED={str((ROOT/p).resolve()) for p in (
    'runs/mlb_longitudinal_disk_20260907/input.sqlite',
    'runs/mlb_longitudinal_streaming_verified_20260907/input.sqlite',
    'runs/cfb_performance_audit_20260907/market_benchmark/native_metadata.sqlite',
    'runs/mlb_historical_20260907/cohort/metadata_index.sqlite')}


def evidence(item):
    if not item.get('completion_evidence'):raise ValueError('completion_evidence_required')
    for ref in item['completion_evidence']:
        path=Path(ref['path'])
        if sha(path)!=ref['sha256']:raise ValueError('completion_evidence_changed')
        if ref.get('expected_fields'):
            value=json.loads(path.read_text())
            for key,expected in ref['expected_fields'].items():
                if value.get(key)!=expected:raise ValueError('completion_assertion_failed')


def guard(path,check_closed=closed):
    states={}
    for p in [path]+[Path(str(path)+suffix) for suffix in ('-wal','-shm','-journal')]:
        if p.is_symlink():raise ValueError('symlink_refused')
        if not p.exists():states[str(p)]=None;continue
        if p!=path and p.stat().st_size:raise ValueError('nonempty_sqlite_sidecar')
        if not check_closed(p):raise ValueError('sqlite_or_sidecar_open')
        states[str(p)]=fingerprint(p)
    if states[str(path)] is None:raise ValueError('missing_sqlite')
    return states


def quick_check(path):
    db=sqlite3.connect(path.resolve().as_uri()+'?mode=ro&immutable=1',uri=True)
    try:
        rows=db.execute('PRAGMA quick_check').fetchall()
        if rows!=[('ok',)]:raise ValueError('sqlite_quick_check_failed')
        return {'quick_check':'ok','page_count':db.execute('PRAGMA page_count').fetchone()[0],
                'freelist_count':db.execute('PRAGMA freelist_count').fetchone()[0],
                'page_size':db.execute('PRAGMA page_size').fetchone()[0]}
    finally:db.close()


def process(item,check_closed=closed):
    path=Path(item['path']);evidence(item);initial=guard(path,check_closed);st=path.stat()
    if st.st_size!=item['logical_bytes'] or sha(path)!=item['file_sha256']:raise ValueError('pinned_database_changed')
    before_check=quick_check(path)
    if guard(path,check_closed)!=initial:raise ValueError('source_changed_after_quick_check')
    if st.st_flags & 32:return {'path':str(path),'status':'already_native_compressed','sqlite':before_check}
    before=allocated(path);fd,name=tempfile.mkstemp(prefix='.sqlite-native-',dir=path.parent);os.close(fd);os.unlink(name);tmp=Path(name)
    try:
        compress_copy(path,tmp)
        if tmp.stat().st_size!=st.st_size or sha(tmp)!=item['file_sha256']:raise ValueError('temporary_database_bytes_mismatch')
        if quick_check(tmp)!=before_check:raise ValueError('temporary_database_validation_mismatch')
        os.chmod(tmp,st.st_mode & 0o7777);os.utime(tmp,ns=(st.st_atime_ns,st.st_mtime_ns))
        if not tmp.stat().st_flags & 32 or allocated(tmp)>=before:return {'path':str(path),'status':'no_physical_benefit','sqlite':before_check}
        evidence(item)
        if guard(path,check_closed)!=initial or sha(path)!=item['file_sha256']:raise ValueError('source_or_sidecars_changed_before_swap')
        os.replace(tmp,path)
        if path.stat().st_size!=st.st_size or sha(path)!=item['file_sha256'] or quick_check(path)!=before_check:raise ValueError('post_swap_database_verification_failed')
        return {'path':str(path),'status':'native_compressed_exact_bytes','sha256_before':item['file_sha256'],'sha256_after':sha(path),
                'logical_bytes':st.st_size,'allocated_bytes_before':before,'allocated_bytes_after':allocated(path),
                'allocated_bytes_saved':before-allocated(path),'sqlite':before_check,'completion_evidence':item['completion_evidence']}
    finally:tmp.unlink(missing_ok=True)


def validate_manifest(manifest):
    if manifest.get('schema_version')!=1 or not 0<len(manifest.get('databases',[]))<=4:raise ValueError('bounded_manifest_required')
    paths=[item['path'] for item in manifest['databases']]
    if len(set(paths))!=len(paths) or set(paths)-ALLOWED:raise ValueError('outside_four_database_allowlist')
    for item in manifest['databases']:
        if str(Path(item['path']).resolve())!=item['path']:raise ValueError('canonical_path_required')
        if len(item['file_sha256'])!=64 or item['logical_bytes']<=0:raise ValueError('pinned_identity_required')


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--manifest',type=Path,required=True);parser.add_argument('--out',type=Path,required=True);parser.add_argument('--execute',action='store_true');args=parser.parse_args()
    manifest=json.loads(args.manifest.read_text());validate_manifest(manifest);args.out.mkdir(parents=True,exist_ok=True)
    with (args.out/'maintenance.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        result={'manifest_sha256':sha(args.manifest),'script_sha256':sha(Path(__file__)),
                'dependency_sha256':{p:sha(Path(__file__).with_name(p)) for p in ('compress_completed_json.py','deduplicate_validation_clones.py')},
                'execute':args.execute,'records':[],'status':'running'}
        if args.execute:result['native_probe']=probe(args.out)
        for item in manifest['databases']:
            if sha(args.manifest)!=result['manifest_sha256']:raise ValueError('manifest_changed')
            if args.execute:record=process(item)
            else:
                evidence(item);path=Path(item['path']);guard(path)
                if sha(path)!=item['file_sha256'] or path.stat().st_size!=item['logical_bytes']:raise ValueError('pinned_database_changed')
                record={'path':str(path),'status':'planned_only','logical_bytes':path.stat().st_size,'allocated_bytes':allocated(path),'sqlite':quick_check(path)}
            result['records'].append(record);atomic_json(args.out/'summary.json',result)
        result.update(status='complete',allocated_bytes_saved=sum(r.get('allocated_bytes_saved',0) for r in result['records']));atomic_json(args.out/'summary.json',result)
        print(json.dumps({'status':result['status'],'execute':args.execute,'files':len(result['records']),'allocated_bytes_saved':result['allocated_bytes_saved']}))


if __name__=='__main__':main()

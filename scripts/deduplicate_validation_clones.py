#!/usr/bin/env python3
"""Exact-byte APFS clone deduplication of certified completed validation gzip files."""
import argparse
import ctypes
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile


def sha(path, normalize=False):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        first=f.read(10)
        if normalize:
            if len(first)!=10 or first[:3]!=b'\x1f\x8b\x08':raise ValueError('not_gzip')
            first=first[:4]+b'\0'*4+first[8:]
        h.update(first)
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()


def fingerprint(path):
    s=path.stat();return (s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)


def clone(source,dest):
    lib=ctypes.CDLL(None,use_errno=True)
    fn=lib.clonefile;fn.argtypes=[ctypes.c_char_p,ctypes.c_char_p,ctypes.c_int];fn.restype=ctypes.c_int
    if fn(os.fsencode(source),os.fsencode(dest),0):raise OSError(ctypes.get_errno(),'clonefile failed')


def probe(directory):
    with tempfile.TemporaryDirectory(prefix='clone-probe-',dir=directory) as temp:
        p=Path(temp)/'a';q=Path(temp)/'b';p.write_bytes(os.urandom(1024*1024));before=sha(p)
        clone(p,q)
        if sha(q)!=before:raise ValueError('clone_probe_bytes_differ')
        with q.open('r+b') as f:f.seek(4);f.write(b'test');f.flush();os.fsync(f.fileno())
        if sha(p)!=before:raise ValueError('clone_probe_not_copy_on_write')
    return {'status':'clonefile_copy_on_write_verified','probe_bytes':1024*1024}


def closed(path):
    result=subprocess.run(['/usr/sbin/lsof','-t','--',str(path)],capture_output=True,text=True,timeout=15)
    if result.returncode not in (0,1) or result.stderr.strip():raise RuntimeError('cannot_verify_file_closed:'+str(path))
    return not result.stdout.strip()


def atomic_json(path,data):
    tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(data,indent=2)+'\n');os.replace(tmp,path)


def certificates(root):
    state=json.loads((root/'batch_status.json').read_text());result={}
    for key,stage in state.get('stages',{}).items():
        if not key.startswith('validation/') or stage.get('status')!='complete' or stage.get('exit_code')!=0:continue
        version=root/key;certificate=(version/'validation.json').resolve();expected=stage.get('output_sha256',{}).get(str(certificate))
        if not expected or sha(certificate)!=expected:raise ValueError('validation_certificate_changed')
        # Retired child must actually be absent. A reused PID conservatively skips.
        pid=stage.get('child_pid')
        if pid:
            try:os.kill(pid,0)
            except ProcessLookupError:pass
            else:continue
        result[version.resolve()]=(certificate,expected)
    return result


def replace_with_clone(source,dest,check_closed=closed):
    if source.is_symlink() or dest.is_symlink():raise ValueError('symlink_refused')
    src_fp,dst_fp=fingerprint(source),fingerprint(dest)
    source_hash,original_hash=sha(source),sha(dest)
    if sha(source,True)!=sha(dest,True):raise ValueError('gzip_bytes_differ_beyond_mtime')
    if not check_closed(source) or not check_closed(dest):raise ValueError('open_file_refused')
    with dest.open('rb') as f:f.seek(4);mtime=f.read(4)
    original_stat=dest.stat()
    fd,name=tempfile.mkstemp(prefix='clone-dedup-',dir=dest.parent);os.close(fd);os.unlink(name);tmp=Path(name)
    try:
        clone(source,tmp)
        with tmp.open('r+b') as f:f.seek(4);f.write(mtime);f.flush();os.fsync(f.fileno())
        os.chmod(tmp,original_stat.st_mode & 0o7777);os.utime(tmp,ns=(original_stat.st_atime_ns,original_stat.st_mtime_ns))
        if sha(tmp)!=original_hash:raise ValueError('reconstructed_bytes_mismatch')
        if fingerprint(source)!=src_fp or fingerprint(dest)!=dst_fp or sha(source)!=source_hash or sha(dest)!=original_hash:raise ValueError('file_changed_during_clone')
        if not check_closed(dest):raise ValueError('destination_opened_during_clone')
        os.replace(tmp,dest)
        if sha(dest)!=original_hash or sha(source)!=source_hash:raise ValueError('post_replace_hash_mismatch')
        return {'path':str(dest),'canonical':str(source),'original_sha256':original_hash,'after_sha256':sha(dest),
                'canonical_sha256':source_hash,'bytes':original_stat.st_size,
                'logical_duplicate_body_bytes':max(0,original_stat.st_size-4096),
                'stat_allocated_bytes_before':original_stat.st_blocks*512,'stat_allocated_bytes_after':dest.stat().st_blocks*512,
                'gzip_mtime_hex':mtime.hex(),'status':'exact_bytes_preserved_clone_replaced'}
    finally:
        tmp.unlink(missing_ok=True)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--batch-root',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--execute',action='store_true');p.add_argument('--max-files',type=int,default=1000);a=p.parse_args()
    if a.max_files<1:raise ValueError('positive_max_files_required')
    a.out.mkdir(parents=True,exist_ok=True)
    with (a.out/'dedup.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        certs=certificates(a.batch_root.resolve());canonical={};pairs=[]
        # Only known generated ledgers in certified date directories, not arbitrary gzip.
        allowed={f'{regime}_{kind}.jsonl.gz' for regime in ('constrained','unconstrained') for kind in ('decisions','curves','fills')}
        receipt_path=a.out/'receipts.json';receipts=json.loads(receipt_path.read_text()) if receipt_path.exists() else {}
        for version in sorted(certs):
            for path in sorted(version.glob('*/*.jsonl.gz')):
                if path.name not in allowed or path.is_symlink():continue
                key=(path.stat().st_size,sha(path,True))
                if key not in canonical:canonical[key]=path;continue
                if str(path) in receipts and sha(path)==receipts[str(path)]['after_sha256']:continue
                pairs.append((canonical[key],path,version))
        pairs=pairs[:a.max_files];free=lambda:os.statvfs(a.out).f_bavail*os.statvfs(a.out).f_frsize
        result={'started_at':datetime.now(timezone.utc).isoformat(),'execute':a.execute,'candidate_files':len(pairs),'certified_versions':[str(v) for v in certs],
                'filesystem_free_bytes_before':free(),'script_sha256':sha(Path(__file__)),'records':[],
                'storage_interpretation':'APFS clone shares extents; per-file st_blocks can still count shared blocks. Logical duplicate body bytes are not guaranteed immediate physical reclamation. Concurrent writers and snapshots affect free-space changes.'}
        if a.execute:
            result['probe']=probe(a.out)
            for source,dest,version in pairs:
                # Re-attest completion immediately before each immutable replacement.
                current=certificates(a.batch_root.resolve())
                if version not in current or current[version]!=certs[version]:raise ValueError('certificate_no_longer_complete')
                src_version=next((v for v in certs if source.is_relative_to(v)),None)
                if src_version not in current:raise ValueError('canonical_certificate_no_longer_complete')
                record=replace_with_clone(source,dest);result['records'].append(record);receipts[str(dest)]=record;atomic_json(receipt_path,receipts)
        result['filesystem_free_bytes_after']=free();result['logical_duplicate_body_bytes']=sum(r['logical_duplicate_body_bytes'] for r in result['records'])
        result['status']='complete';atomic_json(a.out/'summary.json',result);print(json.dumps({k:v for k,v in result.items() if k!='records'}))


if __name__=='__main__':main()

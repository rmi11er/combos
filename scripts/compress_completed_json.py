#!/usr/bin/env python3
"""Transparent native compression of certified completed generated JSON files."""
import argparse
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import subprocess
import tempfile
from deduplicate_validation_clones import sha, fingerprint, closed, atomic_json


def allocated(path):return path.stat().st_blocks*512


def compress_copy(source,dest):
    subprocess.run(['/usr/bin/ditto','--hfsCompression',str(source),str(dest)],check=True,capture_output=True,timeout=300)


def probe(directory):
    with tempfile.TemporaryDirectory(prefix='hfs-probe-',dir=directory) as temp:
        p=Path(temp)/'source.json';q=Path(temp)/'compressed.json';p.write_bytes(b'{"probe":"unchanged logical bytes"}\n'*40000);h=sha(p)
        compress_copy(p,q)
        if sha(q)!=h or q.stat().st_size!=p.stat().st_size or not q.stat().st_flags & 32 or allocated(q)>=allocated(p):raise ValueError('native_compression_probe_failed')
        return {'status':'native_transparent_compression_verified','logical_bytes':p.stat().st_size,'allocated_before':allocated(p),'allocated_after':allocated(q)}


def replace_compressed(path,check_closed=closed):
    if path.is_symlink():raise ValueError('symlink_refused')
    if path.stat().st_flags & 32:return {'path':str(path),'status':'already_native_compressed'}
    if not check_closed(path):return {'path':str(path),'status':'open_file_skipped'}
    before_fp=fingerprint(path);st=path.stat();h=sha(path);before=allocated(path)
    fd,name=tempfile.mkstemp(prefix='.hfs-compress-',dir=path.parent);os.close(fd);os.unlink(name);tmp=Path(name)
    try:
        compress_copy(path,tmp)
        if sha(tmp)!=h or tmp.stat().st_size!=st.st_size:raise ValueError('compressed_logical_bytes_mismatch')
        os.chmod(tmp,st.st_mode & 0o7777);os.utime(tmp,ns=(st.st_atime_ns,st.st_mtime_ns))
        after=allocated(tmp)
        if not tmp.stat().st_flags & 32 or after>=before:return {'path':str(path),'status':'no_physical_benefit_skipped'}
        if fingerprint(path)!=before_fp or sha(path)!=h:raise ValueError('source_changed_during_compression')
        if not check_closed(path):return {'path':str(path),'status':'opened_during_compression_skipped'}
        os.replace(tmp,path)
        if sha(path)!=h or path.stat().st_size!=st.st_size:raise ValueError('post_compression_verification_failed')
        return {'path':str(path),'status':'compressed_exact_logical_bytes','logical_bytes':st.st_size,'before_sha256':h,'after_sha256':sha(path),
                'allocated_bytes_before':before,'allocated_bytes_after':allocated(path),'allocated_bytes_saved':before-allocated(path),'st_flags_after':path.stat().st_flags}
    finally:tmp.unlink(missing_ok=True)


def candidates(batch_root,timing_roots):
    result={};root=Path(batch_root).resolve();state=json.loads((root/'batch_status.json').read_text())
    for date,day in state.get('days',{}).items():
        if day.get('status')!='complete':continue
        stage=state.get('stages',{}).get(date+'/replay',{})
        if stage.get('status')!='complete' or stage.get('exit_code')!=0:continue
        for filename,kind in (('opportunities.json','completed_primary_replay'),('pricing_context.jsonl','completed_plain_pricing_context')):
            path=root/date/'replay'/filename
            if not path.exists() or path.stat().st_flags & 32:continue
            expected=stage.get('output_sha256',{}).get(str(path))
            if not expected:
                if filename=='opportunities.json':raise ValueError('replay_hash_certificate_missing')
                continue
            if sha(path)!=expected:raise ValueError('replay_or_context_certificate_changed')
            result[path]={'certificate':str(root/'batch_status.json'),'expected_sha256':expected,'kind':kind}
    for root in map(Path,timing_roots):
        root=root.resolve();summary=root/'summary.json';verification=root/'verification.json';report=root/'REPORT.md'
        if not all(p.exists() for p in (summary,verification,report)):continue
        s=json.loads(summary.read_text());v=json.loads(verification.read_text())
        if v.get('source_hashes_match') is not True or not s.get('zero_extra_lag_parity',{}).get('all_fields_exactly_equal'):continue
        for lag in (0,30,60,120):
            path=root/f'opportunities_extra{lag}.json'
            if path.exists() and not path.stat().st_flags & 32:result[path]={'kind':'completed_timing_derivative','certificate':str(summary),'certificate_sha256':sha(summary),
                                          'verification':str(verification),'verification_sha256':sha(verification)}
    return result


def attest_target(path,certificate,batch_root):
    if certificate['kind'].startswith('completed_primary') or certificate['kind']=='completed_plain_pricing_context':
        state=json.loads((Path(batch_root)/'batch_status.json').read_text());date=path.parents[1].name
        stage=state.get('stages',{}).get(date+'/replay',{})
        if state.get('days',{}).get(date,{}).get('status')!='complete' or stage.get('status')!='complete' or stage.get('exit_code')!=0 or stage.get('output_sha256',{}).get(str(path))!=certificate['expected_sha256']:
            raise ValueError('target_completion_certificate_changed')
        if sha(path)!=certificate['expected_sha256']:raise ValueError('target_hash_changed')
    else:
        if sha(Path(certificate['certificate']))!=certificate['certificate_sha256'] or sha(Path(certificate['verification']))!=certificate['verification_sha256']:
            raise ValueError('timing_certificate_changed')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--batch-root',type=Path,required=True);p.add_argument('--timing-root',type=Path,action='append',default=[]);p.add_argument('--out',type=Path,required=True);p.add_argument('--execute',action='store_true');p.add_argument('--max-files',type=int,default=20);p.add_argument('--minimum-bytes',type=int,default=1048576);a=p.parse_args()
    if a.max_files<1 or a.minimum_bytes<1:raise ValueError('positive_bounds_required')
    a.out.mkdir(parents=True,exist_ok=True)
    with (a.out/'compression.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        paths=candidates(a.batch_root,a.timing_root);free=lambda:os.statvfs(a.out).f_bavail*os.statvfs(a.out).f_frsize
        result={'started_at':datetime.now(timezone.utc).isoformat(),'execute':a.execute,'script_sha256':sha(Path(__file__)),
                'dependency_sha256':sha(Path(__file__).with_name('deduplicate_validation_clones.py')),'filesystem_free_bytes_before':free(),'records':[]}
        if a.execute:result['probe']=probe(a.out)
        attempted=0
        for path,certificate in sorted(paths.items()):
            if path.stat().st_size<a.minimum_bytes:continue
            if path.stat().st_flags & 32:
                result['records'].append({'path':str(path),'status':'already_native_compressed','provenance':certificate});continue
            if attempted>=a.max_files:break
            attempted+=1
            if a.execute:
                attest_target(path,certificate,a.batch_root)
                record=replace_compressed(path)
            else:record={'path':str(path),'status':'plan','logical_bytes':path.stat().st_size,'allocated_bytes':allocated(path),'st_flags':path.stat().st_flags}
            result['records'].append({**record,'provenance':certificate});atomic_json(a.out/'summary.json',result)
        result.update(status='complete',filesystem_free_bytes_after=free(),allocated_bytes_saved=sum(r.get('allocated_bytes_saved',0) for r in result['records']))
        atomic_json(a.out/'summary.json',result);print(json.dumps({k:v for k,v in result.items() if k!='records'}))


if __name__=='__main__':main()

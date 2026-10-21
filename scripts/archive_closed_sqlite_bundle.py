"""Reversible byte-exact archive of a closed SQLite file and its sidecars."""
import argparse,gzip,hashlib,json,os,subprocess,tarfile,time
from pathlib import Path


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()


def closed(paths):
    p=subprocess.run(['lsof','-t',*[str(p) for p in paths]],capture_output=True,text=True)
    return p.returncode==1 and not p.stdout.strip()


def verify(archive,manifest):
    seen=set()
    with tarfile.open(archive,'r:gz') as t:
        for member in t:
            if not member.isfile() or member.name not in manifest['files'] or member.name in seen:raise ValueError('archive member mismatch')
            seen.add(member.name);h=hashlib.sha256();n=0
            with t.extractfile(member) as f:
                for b in iter(lambda:f.read(1024*1024),b''):h.update(b);n+=len(b)
            expected=manifest['files'][member.name]
            if h.hexdigest()!=expected['sha256'] or n!=expected['bytes']:raise ValueError('archive content mismatch')
    if seen!=set(manifest['files']):raise ValueError('incomplete archive')


def archive(db,out,replace=False,check_closed=closed):
    paths=[p for p in (db,Path(str(db)+'-wal'),Path(str(db)+'-shm'),Path(str(db)+'-journal')) if p.exists()]
    if not db.is_file() or any(p.is_symlink() for p in paths):raise ValueError('regular source files required')
    if not check_closed(paths):raise ValueError('source open or unverifiable')
    out.mkdir(parents=True,exist_ok=False)
    manifest={'database':str(db.resolve()),'created_at':time.time(),'status':'preparing','files':{p.name:{'sha256':sha(p),'bytes':p.stat().st_size,'mtime_ns':p.stat().st_mtime_ns,'allocated_bytes':p.stat().st_blocks*512,'mode':p.stat().st_mode&0o777} for p in paths}}
    target=out/'bundle.tar.gz';temporary=out/'bundle.tar.gz.tmp'
    with tarfile.open(temporary,'w:gz',compresslevel=1) as t:
        for p in paths:t.add(p,arcname=p.name,recursive=False)
    verify(temporary,manifest)
    if not check_closed(paths):raise ValueError('source opened during archive')
    for p in paths:
        e=manifest['files'][p.name]
        if p.stat().st_mtime_ns!=e['mtime_ns'] or sha(p)!=e['sha256']:raise ValueError('source changed during archive')
    temporary.replace(target);manifest.update(status='verified_archive',archive_sha256=sha(target),archive_bytes=target.stat().st_size)
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2))
    if replace:
        for durable in (target,out/'manifest.json'):
            with durable.open('rb') as handle:os.fsync(handle.fileno())
        if not check_closed(paths):raise ValueError('source opened before replacement')
        for p in paths:p.unlink()
        manifest['status']='originals_replaced_by_verified_archive';(out/'manifest.json').write_text(json.dumps(manifest,indent=2))
    return manifest


def restore(out):
    manifest=json.loads((out/'manifest.json').read_text());target=out/'bundle.tar.gz'
    if sha(target)!=manifest['archive_sha256']:raise ValueError('archive digest mismatch')
    verify(target,manifest);parent=Path(manifest['database']).parent
    names=set(manifest['files']);db_name=Path(manifest['database']).name
    if not names<={db_name,db_name+'-wal',db_name+'-shm',db_name+'-journal'}:raise ValueError('invalid restoration members')
    paths=[parent/name for name in names]
    existing=[p for p in paths if p.exists()]
    if existing and not closed(existing):raise ValueError('restoration target open')
    for p in existing:
        if sha(p)!=manifest['files'][p.name]['sha256']:raise ValueError('conflicting restoration target')
    staged=[]
    with tarfile.open(target,'r:gz') as t:
        for member in t:
            dest=parent/member.name
            if dest.exists():continue
            temp=parent/(member.name+'.restore.tmp')
            with temp.open('xb') as f,t.extractfile(member) as source:
                for b in iter(lambda:source.read(1024*1024),b''):f.write(b)
                f.flush();os.fsync(f.fileno())
            e=manifest['files'][member.name];os.chmod(temp,e['mode']);os.utime(temp,ns=(e['mtime_ns'],e['mtime_ns']));staged.append((temp,dest))
    for temp,dest in staged:temp.replace(dest)
    return {'restored_files':len(staged),'database':manifest['database']}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='action',required=True)
    a=s.add_parser('archive');a.add_argument('--db',type=Path,required=True);a.add_argument('--out',type=Path,required=True);a.add_argument('--replace',action='store_true')
    a=s.add_parser('restore');a.add_argument('--out',type=Path,required=True)
    a=p.parse_args();r=archive(a.db,a.out,a.replace) if a.action=='archive' else restore(a.out);print(json.dumps(r,indent=2))

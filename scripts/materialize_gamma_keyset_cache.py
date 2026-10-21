"""Materialize explicitly derived legacy-cache pages from a complete keyset scan.

Raw HTTP envelopes are retained separately. Derived cache status is local success,
not a claim that the deprecated offset request returned HTTP200.
"""
import argparse,fcntl,gzip,hashlib,json,os,shutil,time
from pathlib import Path
import requests

URL='https://gamma-api.polymarket.com/events'


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):
    with gzip.open(p,'rt') as f:return json.load(f)
def write(p,value):
    tmp=p.with_suffix(p.suffix+'.tmp')
    with gzip.open(tmp,'wt',compresslevel=1) as f:json.dump(value,f)
    with tmp.open('rb') as f:os.fsync(f.fileno())
    tmp.replace(p)


def run(failed,out,batch_root,apply=False):
    original=load(failed)
    if original['status']!=422 or original['payload'].get('error')!='offset too large, use /events/keyset for deeper pagination':raise ValueError('exact keyset migration failure required')
    params={k:v for k,v in original['params'].items() if k!='offset'}
    if params.get('limit')!=100 or original['url']!=URL:raise ValueError('unexpected legacy request')
    out.mkdir(parents=True,exist_ok=False);session=requests.Session();session.trust_env=False
    events=[];ids=set();cursor=None;seen=set();refs=[]
    for index in range(50):
        query={**params,**({'after_cursor':cursor} if cursor else {})}
        response=session.get(URL+'/keyset',params=query,timeout=35,allow_redirects=False)
        envelope={'url':URL+'/keyset','params':query,'status':response.status_code,'retrieved_at':time.time(),'payload':response.json()}
        path=out/f'raw_{index:03d}.json.gz';write(path,envelope);refs.append({'path':str(path.resolve()),'sha256':sha(path)})
        if response.status_code!=200:raise ValueError('keyset request failed; raw evidence retained')
        body=envelope['payload'];page=body['events']
        if not isinstance(page,list):raise ValueError('invalid keyset events')
        for event in page:
            identifier=event['id']
            if identifier in ids:raise ValueError('duplicate keyset event')
            ids.add(identifier);events.append(event)
        next_cursor=body.get('next_cursor')
        if next_cursor is None or next_cursor=='':break
        if not isinstance(next_cursor,str) or next_cursor in seen:raise ValueError('invalid or repeated keyset cursor')
        seen.add(next_cursor);cursor=next_cursor
    else:raise ValueError('keyset pagination ceiling reached')
    if len(events)>=5000:raise ValueError('catalog exceeds frozen reader ceiling')
    # Ensure prior successful pages' membership is preserved; do not silently
    # drop previously observed events when repairing a pagination mechanism.
    previous_ids=set();old_files=[]
    for p in failed.parent.glob('pm_events_*.json.gz'):
        old=load(p)
        if old.get('url')==URL and {k:v for k,v in old.get('params',{}).items() if k!='offset'}==params:
            old_files.append(p)
            if old['status']==200:previous_ids.update(e['id'] for e in old['payload'])
    if not previous_ids<=ids:raise ValueError('keyset scan lost previously observed event identities')
    manifest={'status':'verified_complete_keyset_scan','events':len(events),'prior_event_ids':len(previous_ids),
        'params':params,'raw_pages':refs,'legacy_failure':{'path':str(failed),'sha256':sha(failed)},
        'derived_pages':[],'source_sha256':sha(Path(__file__))}
    for offset in range(0,len(events)+1,100):
        logical={**params,'offset':offset};digest=hashlib.sha256(json.dumps([URL,logical],sort_keys=True).encode()).hexdigest()
        name='pm_events_'+digest+'.json.gz';dest=out/name
        value={'url':URL,'params':logical,'status':200,'status_semantics':'local_materialization_success_not_legacy_HTTP_status',
            'retrieved_at':envelope['retrieved_at'],'payload':events[offset:offset+100],
            'provenance':{'kind':'derived_keyset_catalog_slice','manifest':str((out/'manifest.json').resolve()),'offset':offset}}
        write(dest,value);manifest['derived_pages'].append({'name':name,'sha256':sha(dest)})
        if len(value['payload'])<100:break
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2))
    if apply:
        with (batch_root/'batch.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            backup=out/'original_cache';backup.mkdir()
            for p in old_files:shutil.copy2(p,backup/p.name)
            manifest['legacy_failure']['original_path']=manifest['legacy_failure']['path']
            manifest['legacy_failure']['path']=str((backup/failed.name).resolve())
            for item in manifest['derived_pages']:
                target=failed.parent/item['name'];temp=target.with_suffix('.install.tmp')
                shutil.copy2(out/item['name'],temp)
                if sha(temp)!=item['sha256']:raise ValueError('cache copy mismatch')
                temp.replace(target)
            for item in manifest['derived_pages']:
                if sha(failed.parent/item['name'])!=item['sha256']:raise ValueError('installed cache mismatch')
        manifest['status']='installed_derived_cache';(out/'manifest.json').write_text(json.dumps(manifest,indent=2))
    print(json.dumps({'status':manifest['status'],'events':len(events),'prior_event_ids':len(previous_ids),'pages':len(refs)}))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('failed','out','batch-root'):p.add_argument('--'+k,type=Path,required=True)
    p.add_argument('--apply',action='store_true');a=p.parse_args();run(a.failed,a.out,a.batch_root,a.apply)

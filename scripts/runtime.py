#!/usr/bin/env python3
"""Run independent collectors, creator monitoring, and shadow quoting services."""
import argparse
import asyncio
from contextlib import contextmanager
import fcntl
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import uuid

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from combos.event_store import EventStore,encode
from combos.creator_service import CreatorService,DEFAULT_POLICY
from combos.shadow_engine import ShadowEngine
from combos.weighted_fair import WeightPolicy
from combos.observations import Observation
from combos.runtime_clock import Deadline


def creator_policy(config):
    """Resolve an explicit runtime policy; legacy manifests retain defaults."""
    supplied=config.get('creator_policy',{})
    if not isinstance(supplied,dict) or set(supplied)-set(DEFAULT_POLICY):
        raise ValueError('creator_policy must contain only supported runtime policy fields')
    policy=dict(DEFAULT_POLICY,**supplied)
    for key,value in policy.items():
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<=0:
            raise ValueError('creator_policy requires positive finite numbers: '+key)
        if key in ('minimum_requests','bursts_before_cooldown','long_legs') and type(value) is not int:
            raise ValueError('creator_policy requires an integer: '+key)
    if policy['duplicate_fraction']>1:
        raise ValueError('creator_policy duplicate_fraction must not exceed one')
    return policy


def validate_manifest(store, config, weights=None):
    manifest=store.get('runtime','manifest')
    if not manifest:raise ValueError('runtime init is required before starting services')
    if encode(manifest['config'])!=encode(config):raise ValueError('runtime config differs from initialized manifest')
    if weights is not None and encode(WeightPolicy(**manifest['weights']).__dict__)!=encode(weights.__dict__):
        raise ValueError('weight config differs from initialized manifest')
    for name,expected in manifest['code_sha256'].items():
        path=ROOT/name
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=expected:
            raise ValueError('runtime source differs from initialized manifest: '+name+'; start a new experiment or use the saved source snapshot')


@contextmanager
def lock(path,role):
    handle=open(str(path)+'.'+role+'.lock','a')
    try:
        try:fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise ValueError(f'{role} is already running for this database') from None
        yield
    finally:handle.close()


def worker(path,role,config,weights,seconds,replay=False,drain=False):
    with lock(path,role):
        store=EventStore(path)
        try:
            validate_manifest(store,config,weights)
            service=CreatorService(store,creator_policy(config)) if role=='creators' else ShadowEngine(store,config,weights,replay)
            deadline=Deadline(seconds)
            while not deadline.expired():
                count=service.step()
                if not count:
                    if drain:break
                    time.sleep(.05)
        finally:store.close()


def archive(store,directory,chunk_rows=10000):
    out=Path(directory);out.mkdir(parents=True,exist_ok=False)
    end=store.db.execute('SELECT COALESCE(MAX(seq),0) FROM events').fetchone()[0]
    manifest={'complete':False,'through_seq':end,'chunks':[],'schema_version':1,
              'runtime_manifest':store.get('runtime','manifest'),
              'consumers':[dict(r) for r in store.db.execute('SELECT * FROM consumers')]}
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2))
    cursor=0;handle=None;count=0;total=0
    def close_chunk():
        nonlocal handle
        if handle is None:return
        handle.close();handle=None
        final=current.with_suffix('');current.replace(final)
        with final.open('rb') as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
        manifest['chunks'].append({'file':final.name,'rows':count,'sha256':digest,'bytes':final.stat().st_size})
    try:
        while cursor<end:
            rows=store.read(cursor,500)
            if not rows:raise ValueError('event archive encountered missing tail')
            for event in rows:
                if event['seq']>end:break
                if handle is None:
                    current=out/f'events_{len(manifest["chunks"]):06d}.jsonl.gz.open'
                    handle=gzip.open(current,'wt',compresslevel=3);count=0
                handle.write(encode(event)+'\n');count+=1;total+=1;cursor=event['seq']
                if count>=chunk_rows:close_chunk()
        close_chunk()
    finally:
        if handle:handle.close()
    manifest.update(complete=True,rows=total,created_at=time.time())
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2))
    return manifest


def restore_inputs(store,directory):
    directory=Path(directory);manifest=json.loads((directory/'manifest.json').read_text())
    if not manifest.get('complete'):raise ValueError('incomplete archive')
    if store.db.execute('SELECT COUNT(*) FROM events').fetchone()[0]:raise ValueError('restore requires an empty event database')
    derived={'creator_policy','creator_diagnostic','consumer_error','decision','risk_transition','markout',
             'quote_invalidated','simulation_fill_rejected','simulation_fill_confirmed'}
    total=0;restored=0
    with store.transaction():
        for chunk in manifest['chunks']:
            if Path(chunk['file']).name!=chunk['file']:raise ValueError('invalid archive chunk path')
            path=directory/chunk['file']
            with path.open('rb') as f:
                if hashlib.file_digest(f,'sha256').hexdigest()!=chunk['sha256']:raise ValueError('archive checksum mismatch')
            count=0
            with gzip.open(path,'rt') as f:
                for line in f:
                    event=json.loads(line);count+=1;total+=1
                    digest=hashlib.sha256(encode([event['kind'],event['source'],event['received_at'],event['payload']]).encode()).hexdigest()
                    if digest!=event['digest']:raise ValueError('event content checksum mismatch')
                    if event['kind'] in derived:continue
                    store.append(event['kind'],event['source'],event['payload'],event['event_key'],event['received_at']);restored+=1
            if count!=chunk['rows']:raise ValueError('archive row count mismatch')
        if total!=manifest['rows']:raise ValueError('archive total row count mismatch')
        store.put('runtime','restored_from',{'directory':str(directory),'manifest':manifest,'restored_inputs':restored})
    return {'archive_events':total,'restored_input_events':restored}


def export_review(store,directory):
    out=Path(directory);out.mkdir(parents=True,exist_ok=False)
    kinds={'decision':'decisions.jsonl','creator_policy':'blacklist.jsonl','markout':'markouts.jsonl',
           'risk_transition':'risk_transitions.jsonl','venue_reset':'feed_resets.jsonl','consumer_error':'errors.jsonl',
           'quote_invalidated':'quote_invalidations.jsonl','simulation_fill_rejected':'simulation_fill_rejections.jsonl',
           'simulation_fill_confirmed':'fill_edge.jsonl'}
    handles={kind:(out/name).open('w') for kind,name in kinds.items()}
    end=store.db.execute('SELECT COALESCE(MAX(seq),0) FROM events').fetchone()[0];cursor=0
    try:
        while cursor<end:
            rows=store.read(cursor,500)
            for event in rows:
                if event['seq']>end:break
                if event['kind'] in handles:handles[event['kind']].write(encode(event)+'\n')
                cursor=event['seq']
    finally:
        for handle in handles.values():handle.close()
    (out/'status.json').write_text(json.dumps(status(store),indent=2))
    (out/'manifest.json').write_text(json.dumps({'through_seq':end,'created_at':time.time(),
        'files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.glob('*.json*'))}},indent=2))
    return {'directory':str(out),'through_seq':end}


def status(store):
    tail=store.db.execute('SELECT COALESCE(MAX(seq),0) seq,MAX(received_at) last_at FROM events').fetchone()
    consumers=[dict(r,lag_events=tail['seq']-r['seq']) for r in store.db.execute('SELECT name,seq,updated_at FROM consumers')]
    summary={'events':tail['seq'],'last_event_at':tail['last_at'],'consumers':consumers,
             'database_bytes':store.path.stat().st_size,'wal_bytes':Path(str(store.path)+'-wal').stat().st_size if Path(str(store.path)+'-wal').exists() else 0}
    if store.db.execute("SELECT 1 FROM sqlite_master WHERE name='decisions'").fetchone():
        summary['decisions']=[dict(r) for r in store.db.execute("SELECT json_extract(result,'$.status') status,json_extract(result,'$.reason') reason,COUNT(*) count FROM decisions GROUP BY status,reason")]
        summary['reservations']=[dict(r) for r in store.db.execute('SELECT status,COUNT(*) count,SUM(cost)/10000.0 dollars FROM reservations GROUP BY status')]
    return summary


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db',required=True)
    parser.add_argument('--config',default=str(ROOT/'config/runtime.json'))
    parser.add_argument('--weights',default=str(ROOT/'config/weighting.json'))
    sub=parser.add_subparsers(dest='command',required=True)
    sub.add_parser('init');sub.add_parser('status')
    w=sub.add_parser('worker');w.add_argument('role',choices=['creators','shadow']);w.add_argument('--seconds',type=float,default=3600);w.add_argument('--replay',action='store_true');w.add_argument('--drain',action='store_true')
    c=sub.add_parser('collect');c.add_argument('venue',choices=['kalshi','polymarket']);c.add_argument('--seconds',type=float,default=3600)
    r=sub.add_parser('run');r.add_argument('--seconds',type=float,required=True)
    r.add_argument('--polling',default=str(ROOT/'config/oddspapi_polling.json'))
    r.add_argument('--pinnacle-cache',default=str(ROOT/'data/raw/oddspapi_live'))
    a=sub.add_parser('archive');a.add_argument('--out',required=True)
    restore=sub.add_parser('restore-inputs');restore.add_argument('archive')
    review=sub.add_parser('export-review');review.add_argument('--out',required=True)
    p=sub.add_parser('publish');p.add_argument('input',help='JSONL event envelopes; use - for a streaming stdin adapter')
    replay=sub.add_parser('replay');replay.add_argument('--seconds',type=float,default=3600)
    args=parser.parse_args()
    config=json.loads(Path(args.config).read_text());weights=WeightPolicy(**json.loads(Path(args.weights).read_text()))
    if hasattr(args,'seconds'):Deadline(args.seconds)
    Path(args.db).parent.mkdir(parents=True,exist_ok=True)
    if args.command=='worker':return worker(args.db,args.role,config,weights,args.seconds,args.replay,args.drain)
    if args.command=='collect':
        from combos.live_collectors import collect
        checked=EventStore(args.db)
        try:validate_manifest(checked,config,weights)
        finally:checked.close()
        with lock(args.db,'collector_'+args.venue):return asyncio.run(collect(args.db,config,args.venue,args.seconds))
    store=EventStore(args.db)
    try:
        if args.command=='init':
            creator_policy(config)
            existing=store.get('runtime','manifest')
            if existing:raise ValueError('runtime already initialized; existing manifest preserved')
            code_paths=[*sorted((ROOT/'src/combos').glob('*.py')),Path(__file__).resolve()]
            code_sources={str(p.relative_to(ROOT)):p.read_text() for p in code_paths}
            store.put('runtime','manifest',{'config':config,'weights':weights.__dict__,
                'created_at':time.time(),'code_sources':code_sources,
                'code_sha256':{name:hashlib.sha256(source.encode()).hexdigest() for name,source in code_sources.items()}})
        elif args.command=='status':print(json.dumps(status(store),indent=2))
        elif args.command=='archive':
            archived=archive(store,args.out)
            print(json.dumps({'directory':args.out,'complete':archived['complete'],'rows':archived['rows'],
                'chunks':len(archived['chunks']),'bytes':sum(c['bytes'] for c in archived['chunks'])},indent=2))
        elif args.command=='restore-inputs':print(json.dumps(restore_inputs(store,args.archive),indent=2))
        elif args.command=='export-review':print(json.dumps(export_review(store,args.out),indent=2))
        elif args.command=='publish':
            handle=sys.stdin if args.input=='-' else open(args.input)
            allowed={'observation','rfq','combo_book','heartbeat','creator_override','simulation_fill','simulation_settlement','venue_reset','external_raw','fixture_status','paper_trade'}
            count=0
            try:
                for line in handle:
                    if not line.strip():continue
                    event=json.loads(line)
                    if event['kind'] not in allowed:raise ValueError('unsupported adapter event kind')
                    if event['kind']=='observation':Observation.from_record(event['payload'])
                    with store.transaction():store.append(event['kind'],event['source'],event['payload'],event['event_key'],event['received_at'])
                    count+=1
            finally:
                if handle is not sys.stdin:handle.close()
            print(json.dumps({'published':count}))
        elif args.command=='replay':
            with lock(args.db,'creators'),lock(args.db,'shadow'):
                creators=CreatorService(store,creator_policy(config));engine=ShadowEngine(store,config,weights,replay=True)
                deadline=time.monotonic()+args.seconds
                while time.monotonic()<deadline:
                    a=creators.step();b=engine.step()
                    if not a and not b:break
                else:raise ValueError('replay deadline reached before draining')
                print(json.dumps(status(store),indent=2))
        elif args.command=='run':
            validate_manifest(store,config,weights)
            # Child services remain usable independently. The supervisor is bounded,
            # propagates failures and interrupts children on exit.
            with lock(args.db,'supervisor'):
                commands=[['worker','creators','--seconds',str(args.seconds+10)],['worker','shadow','--seconds',str(args.seconds+10)],['collect','kalshi','--seconds',str(args.seconds)]]
                if any(m.get('polymarket_yes_token') for m in config['mappings']):commands.append(['collect','polymarket','--seconds',str(args.seconds)])
                prefix=[sys.executable,str(Path(__file__).resolve()),'--db',args.db,'--config',args.config,'--weights',args.weights]
                children=[];logs=[];deadline=Deadline(args.seconds+15)
                fallback=config.get('source_fallback',{}).get('enabled',False)
                optional=set();reported=set()
                try:
                    for command in commands:
                        log=open(str(args.db)+'.'+command[0]+'_'+command[1]+'.log','ab');logs.append(log)
                        children.append(subprocess.Popen(prefix+command,stdout=log,stderr=log))
                        if fallback and command[:2]==['collect','polymarket']:optional.add(len(children)-1)
                    # Pinnacle is a separate quota-controlled REST collector;
                    # launch it under the same bounded supervisor so the
                    # three-source shadow runtime cannot silently run without
                    # its sharp reference feed.
                    pin_log=open(str(args.db)+'.pinnacle.log','ab');logs.append(pin_log)
                    pin_command=[sys.executable,str(ROOT/'scripts/oddspapi_feed.py'),'--cache',args.pinnacle_cache,
                                 'capture','--db',args.db,'--runtime',args.config,'--polling',args.polling,
                                 '--seconds',str(args.seconds)]
                    if not fallback or os.environ.get('ODDSPAPI_API_KEY'):
                        children.append(subprocess.Popen(pin_command,stdout=pin_log,stderr=pin_log))
                        if fallback:optional.add(len(children)-1)
                    while any(c.poll() is None for c in children):
                        for i,child in enumerate(children):
                            if child.poll() not in (None,0):
                                if i not in optional:raise RuntimeError('a runtime service failed; inspect adjacent service logs')
                                if i not in reported:
                                    print('Optional source collector failed; source fallback remains active; inspect adjacent logs.',file=sys.stderr,flush=True)
                                    reported.add(i)
                        if deadline.expired():raise RuntimeError('runtime shutdown deadline exceeded')
                        time.sleep(.2)
                finally:
                    for child in children:
                        if child.poll() is None:child.send_signal(signal.SIGINT)
                    for child in children:
                        try:child.wait(timeout=5)
                        except subprocess.TimeoutExpired:child.terminate();child.wait(timeout=5)
                    for log in logs:log.close()
                print(json.dumps(status(store),indent=2))
    finally:store.close()


if __name__=='__main__':
    try:main()
    except KeyboardInterrupt:pass
    except (ValueError,RuntimeError,KeyError) as exc:
        print(str(exc),file=sys.stderr);sys.exit(1)

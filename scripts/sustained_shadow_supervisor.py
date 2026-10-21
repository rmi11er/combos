#!/usr/bin/env python3
"""Bounded shadow-only lifecycle. No quote/order submission commands exist here."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from combos.event_store import EventStore, rfq_payload
from combos.shadow_engine import ShadowEngine
from combos.weighted_fair import WeightPolicy
from combos.request_budget import RequestBudget
from combos.readiness import readiness
from shadow_research_capture import choose_subscription, child_env


def digest(path):
    with Path(path).open('rb') as handle:
        return hashlib.file_digest(handle,'sha256').hexdigest()


def save(path,data):
    temporary=path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(data,indent=2,allow_nan=False)+'\n')
    temporary.replace(path)


def code_files():
    return [*sorted((ROOT/'src/combos').glob('*.py')),ROOT/'scripts/runtime.py',ROOT/'scripts/oddspapi_feed.py',ROOT/'scripts/shadow_research_capture.py',Path(__file__).resolve()]


def validate_runtime(config,weights):
    if config.get('mode')!='shadow':raise ValueError('shadow_mode_required_live_rejected')
    for key,limit in {'capital_dollars':10000,'per_contract_dollars':100,'per_combo_dollars':100,'per_fixture_dollars':250}.items():
        if config.get(key)!=limit:raise ValueError('existing_risk_limits_required:'+key)
    policy=WeightPolicy(**weights)
    if not policy.delayed_pinnacle or policy.pinnacle_delay_seconds<30:raise ValueError('delayed_feed_guards_required')
    store=EventStore(':memory:')
    try:ShadowEngine(store,config,policy)  # Existing constructor and RFQ guards, unchanged.
    finally:store.close()
    return policy


def assert_frozen(hashes):
    for name,expected in hashes.items():
        if not Path(name).is_file() or digest(name)!=expected:raise ValueError('frozen_input_changed:'+name)


def stop_groups(children,grace=2):
    # Signal the group even when its leader exited, so descendants cannot escape cleanup.
    for sig in (signal.SIGINT,signal.SIGTERM,signal.SIGKILL):
        for child in children:
            # Capture the process group while the leader is alive.  Once a
            # short-lived leader exits, asking the kernel to infer its group
            # from the old PID can produce EPERM on macOS when that PID has
            # been reused.  The captured group ID keeps descendant cleanup
            # deterministic while the fallback preserves direct-child cleanup.
            group_id=getattr(child,'_combos_process_group',child.pid)
            try:os.killpg(group_id,sig)
            except (ProcessLookupError,PermissionError):
                try:os.kill(child.pid,sig)
                except (ProcessLookupError,PermissionError):pass
        deadline=time.monotonic()+grace
        for child in children:
            try:child.wait(timeout=max(.001,deadline-time.monotonic()))
            except subprocess.TimeoutExpired:pass
    for child in children:child.wait()


def supervise(commands,timeout,check=lambda:None,poll=.2,stop_grace=2,minimum_seconds=0):
    children=[];logs=[];began=time.monotonic();failure=None;exits={}
    try:
        check()
        for name,command,environment,log_path in commands:
            log=open(log_path,'wb');logs.append(log)
            child=subprocess.Popen(command,cwd=ROOT,env=environment,stdout=log,stderr=log,start_new_session=True)
            try:child._combos_process_group=os.getpgid(child.pid)
            except ProcessLookupError:child._combos_process_group=child.pid
            children.append(child)
        while any(c.poll() is None for c in children):
            check()
            for i,c in enumerate(children):
                if c.poll() is not None:exits.setdefault(commands[i][0],time.monotonic()-began)
            if any(c.poll()==0 and exits.get(commands[i][0],minimum_seconds)<minimum_seconds for i,c in enumerate(children)):
                failure='child_exited_before_requested_duration';break
            if any(c.poll() not in (None,0) for c in children):failure='child_failed';break
            if time.monotonic()-began>=timeout:failure='supervisor_timeout';break
            time.sleep(poll)
        for i,c in enumerate(children):
            if c.poll() is not None:exits.setdefault(commands[i][0],time.monotonic()-began)
        if failure is None and any(c.returncode!=0 for c in children):failure='child_failed'
        if failure is None and any(v<minimum_seconds for v in exits.values()):failure='child_exited_before_requested_duration'
        check()
    except BaseException as exc:
        failure='interrupted' if isinstance(exc,KeyboardInterrupt) else 'supervisor_exception:'+type(exc).__name__
    finally:
        stop_groups(children,stop_grace)
        for log in logs:log.close()
    return {'failure':failure,'elapsed_seconds':time.monotonic()-began,
            'returncodes':{commands[i][0]:c.returncode for i,c in enumerate(children)},
            'observed_exit_seconds':exits,'children_started':len(children),'all_direct_children_reaped':all(c.poll() is not None for c in children)}


def prepare(args):
    args.out.mkdir(parents=True,exist_ok=False)
    config=json.loads(args.runtime.read_text());weights=json.loads(args.weights.read_text());polling=json.loads(args.polling.read_text())
    policy=validate_runtime(config,weights)
    if polling['active_poll_seconds']<30 or polling['nominal_delay_seconds']<30:raise ValueError('minimum_30_second_provider_delay_and_poll_required')
    environment=child_env(args.key_file)
    if args.account_summary:
        account=json.loads(args.account_summary.read_text())
    else:
        result=subprocess.run([sys.executable,str(ROOT/'scripts/oddspapi_feed.py'),'--cache',str(args.out/'account_cache'),'inspect'],cwd=ROOT,env=environment,capture_output=True,text=True,timeout=65)
        if result.returncode:raise RuntimeError('account_inspection_failed_output_suppressed')
        account=json.loads(result.stdout)
    if not 0<=time.time()-account['retrieved_at']<=300:raise ValueError('fresh_account_summary_required')
    polling=choose_subscription(account,polling)
    polling['budget_path']=str((ROOT/polling['budget_path']).resolve())
    polling['usage_reference']=str((args.out/'account_summary.json').resolve())
    budget=RequestBudget(polling['budget_path'],polling['billing_cycle_start'],polling['billing_cycle_end'],polling['subscription_request_limit'],polling['reserve_fraction'],polling['known_used'])
    try:used=budget.used()
    finally:budget.close()
    status=readiness(config,policy,polling,time.time())
    # The validated key is supplied only through the feed child's environment.
    blockers=[x for x in status['shadow_configuration_blockers'] if x!='oddspapi_key_unavailable_to_process']
    if args.purpose=='pricing' and blockers:raise ValueError('pricing_configuration_blocked:'+','.join(blockers))
    inputs={'runtime.json':config,'weighting.json':weights,'polling.json':polling,'account_summary.json':account}
    hashes={str(p.resolve()):digest(p) for p in [args.runtime,args.weights,args.polling,*code_files()]}
    snapshot=args.out/'snapshot'
    for path in code_files():
        relative=path.relative_to(ROOT);target=snapshot/relative;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(path.read_bytes());hashes[str(target.resolve())]=digest(target)
    for name,data in inputs.items():
        save(args.out/name,data);save(snapshot/name,data)
        hashes[str((args.out/name).resolve())]=digest(args.out/name);hashes[str((snapshot/name).resolve())]=digest(snapshot/name)
    prepared={'mode':'shadow','purpose':args.purpose,'prepared_at':time.time(),'hashes':hashes,
              'source_freeze':hashlib.sha256(json.dumps(hashes,sort_keys=True).encode()).hexdigest(),
              'shared_budget_used':used,'configuration_readiness':status,
              'mapping_changes_made':False,'orders_enabled':False}
    save(args.out/'prepared.json',prepared)
    print(json.dumps({'prepared':str(args.out),'source_freeze':prepared['source_freeze'],'shared_budget_used':used,'purpose':args.purpose}))


def quote_context_errors(payload, maximum_lag):
    errors=[]
    lag=payload.get('completed_processing_lag_seconds')
    if not isinstance(lag,(int,float)) or isinstance(lag,bool) or not math.isfinite(lag) or not 0<=lag<=maximum_lag:errors.append('invalid_completed_lag')
    if payload.get('mode')!='shadow' or payload.get('fills_assumed') is not False:errors.append('invalid_shadow_mode')
    if payload.get('risk',{}).get('allowed') is not True:errors.append('risk_not_allowed')
    pricing=payload.get('pricing',{})
    legs=pricing.get('legs',[])
    if pricing.get('quote_allowed') is not True or not 2<=len(legs)<=4:errors.append('invalid_pricing_guard')
    for leg in legs:
        if leg.get('phase')!='pregame' or leg.get('guard',{}).get('quote_allowed') is not True:errors.append('invalid_leg_guard')
        venues=leg.get('venues',{})
        if not all(v in venues for v in ('kalshi','polymarket','pinnacle')):errors.append('missing_quote_venue')
        for venue in ('kalshi','polymarket'):
            depth=venues.get(venue,{}).get('two_sided_depth_payout_dollars')
            if not isinstance(depth,(int,float)) or not math.isfinite(depth) or depth<=0:errors.append('missing_quote_depth')
    return errors


def evidence(out,processes,post,config):
    store=EventStore(out/'events.sqlite');counts=Counter();active=Counter();depth=Counter();dispositions=Counter();invalid=Counter();rfqs=0;quotes=0;valid_quotes=0;maximum_lag=None;seq=0
    # Disk-backed temporary reconciliation, bounded Python memory for long captures.
    store.db.execute('PRAGMA temp_store=FILE')
    store.db.execute('CREATE TEMP TABLE rfq_dispositions(seq INTEGER PRIMARY KEY)')
    store.db.execute('CREATE TEMP TABLE decisions(source_seq INTEGER, status TEXT, mode TEXT)')
    try:
        while True:
            events=store.read(seq,500)
            if not events:break
            for event in events:
                seq=event['seq'];kind=event['kind'];payload=event['payload'];counts[kind]+=1
                if rfq_payload(event) is not None:
                    rfqs+=1;store.db.execute('INSERT INTO rfq_dispositions VALUES (?)',(seq,))
                if kind=='observation' and payload.get('active'):
                    venue=payload['venue'];active[venue]+=1
                    if venue!='pinnacle' and min(payload.get('yes_bid_size',0),payload.get('yes_ask_size',0))>0:depth[venue]+=1
                if kind=='decision':
                    source_seq=payload.get('source_seq')
                    if type(source_seq) is not int:source_seq=None
                    store.db.execute('INSERT INTO decisions VALUES (?,?,?)',(source_seq,payload.get('status'),payload.get('mode')))
                    dispositions[str(payload.get('status'))+':'+str(payload.get('reason'))]+=1
                    if payload.get('status')=='shadow_quote':
                        quotes+=1;errors=quote_context_errors(payload,config['maximum_processing_lag_seconds'])
                        invalid.update(errors)
                        if not errors:valid_quotes+=1
                        lag=payload.get('completed_processing_lag_seconds')
                        if isinstance(lag,(int,float)) and math.isfinite(lag):maximum_lag=max(maximum_lag or 0,lag)
        store.db.execute('CREATE INDEX decisions_source ON decisions(source_seq)')
        missing=store.db.execute('SELECT COUNT(*) FROM rfq_dispositions r WHERE NOT EXISTS (SELECT 1 FROM decisions d WHERE d.source_seq=r.seq)').fetchone()[0]
        duplicates=store.db.execute('SELECT COALESCE(SUM(n-1),0) FROM (SELECT COUNT(*) n FROM decisions GROUP BY source_seq HAVING COUNT(*)>1)').fetchone()[0]
        orphan=store.db.execute('SELECT COUNT(*) FROM decisions d WHERE NOT EXISTS (SELECT 1 FROM rfq_dispositions r WHERE r.seq=d.source_seq)').fetchone()[0]
        malformed=store.db.execute("SELECT COUNT(*) FROM decisions WHERE mode IS NOT 'shadow' OR status IS NULL OR status NOT IN ('skipped','shadow_quote')").fetchone()[0]
        reconciled=not (missing or duplicates or orphan or malformed)
        cursors={r['name']:r['seq'] for r in store.db.execute('SELECT name,seq FROM consumers')}
        drained=all(cursors.get(role,-1)>=seq for role in ('creators','shadow'))
    finally:store.close()
    complete=processes['failure'] is None and all(x['failure'] is None for x in post.values()) and drained and reconciled
    healthy=complete and valid_quotes>0 and not invalid and counts['consumer_error']==0
    result={'processes':processes,'postprocessing':post,'event_counts':dict(counts),'rfqs':rfqs,'decision_count':counts['decision'],'all_rfq_dispositions_recorded':reconciled,'disposition_reconciliation':{'missing':missing,'duplicate':duplicates,'orphan':orphan,'malformed':malformed},'dispositions':dict(dispositions),'shadow_quotes':quotes,'valid_guarded_shadow_quotes':valid_quotes,'invalid_quote_context':dict(invalid),'active_observations':dict(active),'positive_two_sided_depth_observations':dict(depth),'maximum_quote_completed_lag_seconds':maximum_lag,'consumer_cursors':cursors,'event_tail':seq,'consumers_drained':drained,'capture_complete':complete,'capture_evidence_observed':counts['observation']>0,'healthy_pricing_observed':healthy,'outcome':'healthy_pricing_observed' if healthy else 'capture_only_pricing_not_demonstrated','orders_submitted':0,'orders_enabled':False,'live_ready':False,'limitation':'Healthy means guarded shadow quotes with per-quote source depth were observed, not RFQ acceptance, durable alpha or live execution readiness.'}
    save(out/'readiness.json',result);return result


def run(args):
    if not math.isfinite(args.seconds) or not 120<=args.seconds<=21600:raise ValueError('duration_must_be_120_to_21600_seconds')
    out=args.out;prepared=json.loads((out/'prepared.json').read_text())
    if prepared.get('mode')!='shadow' or prepared.get('source_freeze')!=args.code_freeze or hashlib.sha256(json.dumps(prepared['hashes'],sort_keys=True).encode()).hexdigest()!=args.code_freeze:raise ValueError('shadow_freeze_mismatch')
    assert_frozen(prepared['hashes'])
    config=json.loads((out/'runtime.json').read_text());validate_runtime(config,json.loads((out/'weighting.json').read_text()))
    account=json.loads((out/'account_summary.json').read_text())
    if not 0<=time.time()-account['retrieved_at']<=600:raise ValueError('prepare_again_account_reconciliation_expired')
    if (out/'events.sqlite').exists():raise ValueError('fresh_event_database_required')
    environment=child_env(args.key_file);snapshot=out/'snapshot'
    prefix=[sys.executable,str((snapshot/'scripts/runtime.py').resolve()),'--db',str((out/'events.sqlite').resolve()),'--config',str((snapshot/'runtime.json').resolve()),'--weights',str((snapshot/'weighting.json').resolve())]
    def step(command,name,timeout=60):
        return supervise([(name,prefix+command,None,out/(name+'.log'))],timeout)
    initial=step(['init'],'init')
    if initial['failure']:raise RuntimeError('runtime_init_failed')
    commands=[(role,prefix+['worker',role,'--seconds',str(args.seconds+10)],None,out/(role+'.log')) for role in ('creators','shadow')]
    commands.append(('kalshi',prefix+['collect','kalshi','--seconds',str(args.seconds)],None,out/'kalshi.log'))
    if any(m.get('polymarket_yes_token') for m in config['mappings']):
        commands.append(('polymarket',prefix+['collect','polymarket','--seconds',str(args.seconds)],None,out/'polymarket.log'))
    commands.append(('pinnacle',[sys.executable,str((snapshot/'scripts/oddspapi_feed.py').resolve()),'--cache',str((out/'pinnacle_raw').resolve()),'capture','--db',str((out/'events.sqlite').resolve()),'--runtime',str((snapshot/'runtime.json').resolve()),'--polling',str((snapshot/'polling.json').resolve()),'--seconds',str(args.seconds)],environment,out/'pinnacle.log'))
    processes=supervise(commands,args.seconds+30,lambda:assert_frozen(prepared['hashes']),minimum_seconds=args.seconds-.5)
    # The original source may have changed. Postprocessing uses the intact frozen clone.
    frozen={p:h for p,h in prepared['hashes'].items() if Path(p).is_relative_to(snapshot.resolve())}
    try:assert_frozen(frozen)
    except ValueError:
        save(out/'failed.json',{'failure':'frozen_snapshot_changed_postprocessing_refused','processes':processes,'orders_enabled':False})
        return 1
    post={}
    for iteration in range(3):
        for role in ('creators','shadow'):
            name=f'drain_{iteration}_{role}';post[name]=step(['worker',role,'--seconds','15','--drain'],name,30)
    for name,command in [('archive',['archive','--out',str((out/'archive').resolve())]),('export',['export-review','--out',str((out/'review').resolve())])]:
        post[name]=step(command,name,180)
    result=evidence(out,processes,post,config)
    save(out/'finished.json',{'source_freeze':prepared['source_freeze'],'readiness_sha256':digest(out/'readiness.json'),'finished_at':time.time(),'orders_enabled':False})
    print(json.dumps({k:result[k] for k in ('capture_complete','healthy_pricing_observed','shadow_quotes','rfqs','consumers_drained','orders_enabled')}))
    return 0 if result['capture_complete'] else 1


def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    prepare_parser=sub.add_parser('prepare');prepare_parser.add_argument('--out',type=Path,required=True)
    for name,default in [('runtime','runtime_nfl_week1_nonplayer.json'),('weights','weighting.json'),('polling','oddspapi_polling.json')]:prepare_parser.add_argument('--'+name,type=Path,default=ROOT/'config'/default)
    prepare_parser.add_argument('--account-summary',type=Path);prepare_parser.add_argument('--key-file',type=Path,required=True);prepare_parser.add_argument('--purpose',choices=['capture','pricing'],default='pricing')
    run_parser=sub.add_parser('run');run_parser.add_argument('--out',type=Path,required=True);run_parser.add_argument('--key-file',type=Path,required=True);run_parser.add_argument('--seconds',type=float,default=1800);run_parser.add_argument('--code-freeze',required=True)
    args=p.parse_args()
    if args.command=='prepare':prepare(args);return 0
    def interrupted(signum,frame):raise KeyboardInterrupt()
    signal.signal(signal.SIGTERM,interrupted)
    signal.signal(signal.SIGINT,interrupted)
    return run(args)


if __name__=='__main__':
    sys.exit(main())

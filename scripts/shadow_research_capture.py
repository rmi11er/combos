#!/usr/bin/env python3
"""Prepare and run a bounded, read-only three-source research capture.

Runtime and Pinnacle processes share an initialized event DB and source freeze.
All mapping pricing blocks are retained. No exchange order/quote API is invoked.
"""
import argparse,hashlib,json,math,os,signal,subprocess,sys,time,shutil
from collections import Counter,defaultdict
from datetime import datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from combos.request_budget import RequestBudget

def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def source_digest():
 files=[*sorted((ROOT/'src/combos').glob('*.py')),ROOT/'scripts/runtime.py']
 return hashlib.sha256(json.dumps({str(p.relative_to(ROOT)):digest(p) for p in files},sort_keys=True).encode()).hexdigest()
def validate_runtime(config):
 if config.get('mode')!='shadow':raise ValueError('shadow_mode_required')
 mappings=config.get('mappings',[])
 if not mappings:raise ValueError('mappings_required')
 for m in mappings:
  greenlit=m.get('pinnacle',{}).get('settlement_policy') in ('full_game_moneyline_rules_v1','nonplayer_rules_v1')
  if not m.get('pricing_block_reason') and not greenlit and not config.get('shadow_allow_unreviewed_families'):
   raise ValueError('pricing_blocks_required')
 if config.get('minimum_legs')!=2 or config.get('maximum_legs')!=4 or config.get('pregame_only') is not True:raise ValueError('reviewed_runtime_scope_required')
 return Counter(m['pricing_block_reason'] for m in mappings)
def choose_subscription(account,polling,now=None):
 now=time.time() if now is None else now;matches=[]
 for s in account.get('subscriptions',[]):
  if s.get('is_active') is not True or polling['bookmakers'][0] not in s.get('bookmakers',{}) or polling['sport_id'] not in s.get('sport_ids',[]):continue
  start=datetime.fromisoformat(s['valid_from'].replace('Z','+00:00')).timestamp();end=datetime.fromisoformat(s['valid_until'].replace('Z','+00:00')).timestamp()
  if start<=now<end:matches.append((s,start,end))
 if len(matches)!=1:raise ValueError('one_active_matching_subscription_required')
 s,start,end=matches[0]
 if not isinstance(s['request_count'],int) or s['request_count']<0 or s['request_limit']!=polling['subscription_request_limit']:raise ValueError('account_usage_or_tier_mismatch')
 return {**polling,'billing_cycle_start':start,'billing_cycle_end':end,'known_used':s['request_count'],'usage_verified_at':account['retrieved_at']}
def child_env(key_file):
 env=os.environ.copy();env['ODDSPAPI_API_KEY']=Path(key_file).read_text().strip()
 if not env['ODDSPAPI_API_KEY'] or '\n' in env['ODDSPAPI_API_KEY']:raise ValueError('invalid_key_file')
 return env

def prepare(args):
 out=args.out;out.mkdir(parents=True,exist_ok=True)
 if (out/'prepared.json').exists() or (out/'events.sqlite').exists():raise ValueError('fresh_capture_directory_required')
 config=json.loads(args.runtime.read_text());blocked=validate_runtime(config);weights=json.loads(args.weights.read_text());polling=json.loads(args.polling.read_text())
 if polling['active_poll_seconds']<30 or polling['nominal_delay_seconds']<30:raise ValueError('reviewed_delay_and_polling_required')
 if args.account_summary:
  account=json.loads(args.account_summary.read_text())
  if not 0<=time.time()-account['retrieved_at']<=300:raise ValueError('account_summary_older_than_5_minutes')
 else:
  command=[sys.executable,str(ROOT/'scripts/oddspapi_feed.py'),'--cache',str(out/'account_cache'),'inspect']
  p=subprocess.run(command,cwd=ROOT,env=child_env(args.key_file),capture_output=True,text=True,timeout=65)
  if p.returncode:raise RuntimeError('account_inspection_failed_output_suppressed')
  account=json.loads(p.stdout)
 polling=choose_subscription(account,polling);polling['budget_path']=str((ROOT/polling['budget_path']).resolve());polling['usage_reference']=str(out/'account_summary.json')
 budget=RequestBudget(polling['budget_path'],polling['billing_cycle_start'],polling['billing_cycle_end'],polling['subscription_request_limit'],polling['reserve_fraction'],polling['known_used'])
 try:used=budget.used()
 finally:budget.close()
 for name,data in [('runtime.json',config),('weighting.json',weights),('polling.json',polling),('account_summary.json',account)]: (out/name).write_text(json.dumps(data,indent=2)+'\n')
 prepared={'mode':'shadow','mappings':len(config['mappings']),'pricing_block_counts':dict(blocked),'shared_budget_used_after_reconciliation':used,'account_used':polling['known_used'],'prepared_at':time.time(),'inputs_sha256':{name:digest(out/name) for name in ['runtime.json','weighting.json','polling.json','account_summary.json']},'source_inputs_sha256':{str(p):digest(p) for p in [args.runtime,args.weights,args.polling]},'runner_sha256':digest(Path(__file__))}
 (out/'prepared.json').write_text(json.dumps(prepared,indent=2)+'\n');print(json.dumps(prepared,indent=2))

def stop_groups(children):
 for p in children:
  if p.poll() is None:
   try:os.killpg(p.pid,signal.SIGINT)
   except ProcessLookupError:pass
 until=time.monotonic()+5
 while time.monotonic()<until and any(p.poll() is None for p in children):time.sleep(.05)
 for sig in [signal.SIGTERM,signal.SIGKILL]:
  for p in children:
   if p.poll() is None:
    try:os.killpg(p.pid,sig)
    except ProcessLookupError:pass
  for p in children:
   try:p.wait(timeout=2)
   except subprocess.TimeoutExpired:pass

def health(out,process_results):
 from combos.event_store import EventStore
 store=EventStore(out/'events.sqlite');kinds=Counter();active=Counter();invalid=defaultdict(Counter);keys=defaultdict(set);activekeys=defaultdict(set);depthkeys=defaultdict(set);observed_ranges={};statuses=[];resets=[];timings=[];seq=0
 try:
  while True:
   rows=store.read(seq,500)
   if not rows:break
   for e in rows:
    seq=e['seq'];k=e['kind'];v=e['source'];r=e['payload'];kinds[k+':'+v]+=1
    if k=='observation':
     v=r['venue'];keys[v].add(r['market_key']);observed_ranges.setdefault(v,[e['received_at'],e['received_at']])[1]=e['received_at']
     if r.get('active'):
      active[v]+=1;activekeys[v].add(r['market_key'])
      if v!='pinnacle' and min(r.get('yes_bid_size',0),r.get('yes_ask_size',0))>0:depthkeys[v].add(r['market_key'])
     else:invalid[v][r.get('invalid_reason','unspecified')]+=1
    elif k=='feed_status':statuses.append(r)
    elif k=='venue_reset':resets.append(r)
    elif k=='capture_timing':timings.append(r)
  decisions=[]
  if store.db.execute("select 1 from sqlite_master where name='decisions'").fetchone():decisions=[dict(r) for r in store.db.execute("select json_extract(result,'$.status') status,json_extract(result,'$.reason') reason,count(*) count from decisions group by status,reason")]
  mapping=json.loads((out/'runtime.json').read_text())['mappings'];expected={m['market_key'] for m in mapping};three=set.intersection(*(keys.get(v,set()) for v in ['kalshi','polymarket','pinnacle']))
  result={'processes':process_results,'event_counts':dict(kinds),'active_observations':dict(active),'invalid_observation_reasons':{k:dict(v) for k,v in invalid.items()},'unique_observed_market_keys':{k:len(v) for k,v in keys.items()},'unique_keys_with_positive_two_sided_exchange_depth':{k:len(v) for k,v in depthkeys.items()},'three_venue_observed_key_intersection':len(three),'three_venue_active_key_intersection':len(set.intersection(*(activekeys.get(v,set()) for v in ['kalshi','polymarket','pinnacle']))),'observation_time_ranges':observed_ranges,'missing_observation_keys':{v:sorted(expected-keys.get(v,set())) for v in ['kalshi','polymarket','pinnacle']},'feed_status':statuses,'feed_resets':resets,'capture_timings':timings,'decisions':decisions,'expected_pricing_blocks':dict(Counter(m.get('pricing_block_reason','') for m in mapping if m.get('pricing_block_reason'))),'orders_submitted':0,'acceptance_basis':'No submitted orders or invented acceptance events. This records real market data with reviewed full-game moneylines and retained blocks for other families.','finished_at':time.time()}
 finally:store.close()
 (out/'readiness.json').write_text(json.dumps(result,indent=2)+'\n');return result

def run(args):
 if not math.isfinite(args.seconds) or not 90<=args.seconds<=600:raise ValueError('duration_must_be_90_to_600_seconds')
 out=args.out;prepared=json.loads((out/'prepared.json').read_text())
 for n,h in prepared['inputs_sha256'].items():
  if digest(out/n)!=h:raise ValueError('prepared_inputs_changed')
 validate_runtime(json.loads((out/'runtime.json').read_text()))
 if source_digest()!=args.code_freeze:raise ValueError('code_freeze_mismatch')
 if time.time()-json.loads((out/'account_summary.json').read_text())['retrieved_at']>600:raise ValueError('account_reconciliation_older_than_10_minutes_prepare_new_run')
 if (out/'events.sqlite').exists():raise ValueError('fresh_event_database_required')
 prefix=[sys.executable,str(ROOT/'scripts/runtime.py'),'--db',str(out/'events.sqlite'),'--config',str(out/'runtime.json'),'--weights',str(out/'weighting.json')]
 def step(command,name):
  with (out/(name+'.log')).open('w') as log:return subprocess.run(command,cwd=ROOT,stdout=log,stderr=log,timeout=45).returncode
 if step(prefix+['init'],'init'):raise RuntimeError('runtime_initialization_failed')
 commands=[('runtime',prefix+['run','--seconds',str(args.seconds)],None),('pinnacle',[sys.executable,str(ROOT/'scripts/oddspapi_feed.py'),'--cache',str(out/'pinnacle_raw'),'capture','--db',str(out/'events.sqlite'),'--runtime',str(out/'runtime.json'),'--polling',str(out/'polling.json'),'--seconds',str(args.seconds)],child_env(args.key_file))]
 children=[];logs=[];failure=None;began=time.time();deadline=time.monotonic()+args.seconds+30
 try:
  for name,cmd,env in commands:
   log=(out/(name+'.log')).open('w');logs.append(log);children.append(subprocess.Popen(cmd,cwd=ROOT,env=env,stdout=log,stderr=log,start_new_session=True))
  while any(p.poll() is None for p in children):
   if any(p.poll() not in (None,0) for p in children):failure='child_failed';break
   if time.monotonic()>=deadline:failure='capture_supervisor_deadline';break
   if shutil.disk_usage(out).free<8*2**30:failure='disk_space_floor';break
   time.sleep(.2)
 except KeyboardInterrupt:failure='interrupted'
 finally:
  stop_groups(children)
  for log in logs:log.close()
 results={'started_at':began,'elapsed_seconds':time.time()-began,'requested_seconds':args.seconds,'failure':failure,'returncodes':{commands[i][0]:p.returncode for i,p in enumerate(children)},'code_freeze':args.code_freeze}
 for command in [['worker','creators','--seconds','10','--drain'],['worker','shadow','--seconds','10','--drain'],['archive','--out',str(out/'archive')],['export-review','--out',str(out/'review')]]:
  name='post_'+command[0]+('_'+command[1] if command[0]=='worker' else '');results[name]=step(prefix+command,name)
 result=health(out,results);print(json.dumps({k:result[k] for k in ['processes','event_counts','active_observations','invalid_observation_reasons','unique_observed_market_keys','unique_keys_with_positive_two_sided_exchange_depth','three_venue_observed_key_intersection','decisions','orders_submitted']},indent=2))
 if failure or any(v not in (0,None) for v in results['returncodes'].values()) or any(results[k] for k in results if k.startswith('post_')):raise SystemExit(1)

def main():
 p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True);a=sub.add_parser('prepare');a.add_argument('--out',type=Path,required=True);a.add_argument('--runtime',type=Path,default=ROOT/'config/runtime_nfl_week1_nonplayer.json');a.add_argument('--weights',type=Path,default=ROOT/'config/weighting.json');a.add_argument('--polling',type=Path,default=ROOT/'config/oddspapi_polling.json');a.add_argument('--account-summary',type=Path);a.add_argument('--key-file',type=Path,required=True)
 a=sub.add_parser('run');a.add_argument('--out',type=Path,required=True);a.add_argument('--key-file',type=Path,required=True);a.add_argument('--seconds',type=float,default=100);a.add_argument('--code-freeze',required=True)
 sub.add_parser('source-digest');args=p.parse_args()
 if args.command=='prepare':prepare(args)
 elif args.command=='run':run(args)
 else:print(source_digest())
if __name__=='__main__':main()

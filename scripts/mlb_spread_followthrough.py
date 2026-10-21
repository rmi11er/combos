#!/usr/bin/env python3
"""Read-only follow-through on completed dated MLB replays; no provider calls."""
import argparse
from collections import Counter
import fcntl
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from mlb_longitudinal_sweep import discover, save, load, digest
from opposite_moneyline_study import PairHistory
from mlb_historical_batch import frozen_code_paths

ROOT = Path(__file__).resolve().parents[1]


def extract(day, out):
    """Entire eligible moneyline subset, independent of model trade selection."""
    out.mkdir(parents=True, exist_ok=True)
    replay = day/'replay/opportunities.json'
    context = day/'replay/pricing_context.jsonl.gz'
    data = load(replay)
    ids = {r['evaluation_id'] for r in data['opportunities']}
    provider = PairHistory(day, 'mlb')
    counts, exclusions, seen = Counter(), Counter(), set()
    temp = out/'features.jsonl.gz.tmp'
    with gzip.open(context, 'rt') as source, gzip.open(temp, 'wt') as target:
        for line in source:
            r = json.loads(line); key = r['evaluation_id']
            if key not in ids:
                continue
            legs = r['legs']
            if not 2 <= len(legs) <= 4 or any(not l['market_ticker'].startswith('KXMLBGAME-') for l in legs):
                exclusions['not_moneyline_only'] += 1; continue
            if len({l['market_ticker'].rsplit('-',1)[0] for l in legs}) != len(legs):
                exclusions['shared_game'] += 1; continue
            counts['eligible_moneyline_prints'] += 1
            try:
                pairs = [provider.pair(l['market_ticker'], r['at'], c['kalshi']['fee_basis']['taker_rate']) for l,c in zip(legs,r['context'])]
                if len(pairs) != len(legs):
                    raise ValueError('incomplete_leg_context')
            except (ValueError, KeyError, FileNotFoundError) as exc:
                exclusions[str(exc)] += 1; continue
            if key in seen:
                raise ValueError('duplicate_feature_print')
            seen.add(key)
            value = {'evaluation_id':key, 'at':r['at'], 'legs':legs, 'pairs':pairs,
                     'max_raw_pair_width_cents':max(p['raw_width_cents'] for p in pairs),
                     'synchronized_recent':all(max(p['age_seconds'])<=300 and p['state_skew_seconds']<=120 for p in pairs),
                     'pm_complete':all('pm' in p for p in pairs)}
            target.write(json.dumps(value,separators=(',',':'),allow_nan=False)+'\n')
    temp.replace(out/'features.jsonl.gz')
    manifest = {'counts':dict(counts), 'paired_prints':len(seen), 'exclusions':dict(exclusions),
        'replay':str(replay.resolve()), 'source_sha256':{str(p.resolve()):digest(p) for p in provider.used|{replay,context}},
        'features_sha256':digest(out/'features.jsonl.gz'),
        'scope':'All available 2–4 distinct-game moneyline primary prints, no edge or outcome filter. Ordinary-game complement assumptions inherited.',
        'complete':True}
    save(out/'feature_manifest.json',manifest)
    return manifest


def execute(command, log, state, path, timeout=7200):
    with log.open('w') as handle:
        child = subprocess.Popen(command,cwd=ROOT,stdout=handle,stderr=subprocess.STDOUT)
        state.update(child_pid=child.pid,command=command,log=str(log),updated_at=time.time()); save(path,state)
        deadline=time.monotonic()+timeout
        try:
            while child.poll() is None:
                if time.monotonic()>deadline:
                    raise TimeoutError('followthrough_stage_timeout')
                try:
                    child.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    state['updated_at']=time.time(); save(path,state)
            if child.returncode:
                raise RuntimeError('followthrough_child_failed:'+str(log))
        finally:
            if child.poll() is None:
                child.terminate(); child.wait(timeout=10)
            state.pop('child_pid',None)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--batch-root',type=Path,required=True)
    p.add_argument('--plan',type=Path,default=ROOT/'config/mlb_validation_20260907_expanded.json')
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--watch',action='store_true')
    p.add_argument('--max-hours',type=float,default=48.)
    args=p.parse_args();args.out.mkdir(parents=True,exist_ok=True)
    with (args.out/'watch.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        identity={'plan_sha256':digest(args.plan),'batch_root':str(args.batch_root.resolve()),
            'code_sha256':{str(path):digest(path) for path in [Path(__file__),ROOT/'scripts/opposite_moneyline_study.py',
                ROOT/'scripts/spread_calibration_study.py',ROOT/'scripts/spread_profitability.py',ROOT/'scripts/mlb_longitudinal_sweep.py',
                *frozen_code_paths()]}}
        manifest=args.out/'watch_manifest.json'
        if manifest.exists() and load(manifest)!=identity:
            raise ValueError('followthrough_frozen_identity_changed')
        save(manifest,identity)
        path=args.out/'status.json';state=load(path) if path.exists() else {'days':{}}
        state.update(pid=os.getpid(),status='running',started_at=time.time())
        plan=load(args.plan);deadline=time.monotonic()+args.max_hours*3600
        try:
            while True:
                for file, expected in identity['code_sha256'].items():
                    if digest(Path(file))!=expected:
                        raise ValueError('followthrough_code_changed:'+file)
                files,empty,batch_states=discover([args.batch_root],plan)
                state.update(available_dates=sorted(files),empty_dates=empty,batch_states=batch_states,updated_at=time.time())
                save(path,state)
                for date,replay in sorted(files.items()):
                    prior=state['days'].get(date,{})
                    if prior.get('status')=='complete':
                        if prior['replay_sha256']!=digest(replay):
                            raise ValueError('completed_followthrough_input_changed')
                        continue
                    day=replay.parent.parent;out=args.out/date
                    state.update(status='extracting',active_date=date,updated_at=time.time());save(path,state)
                    feature=extract(day,out)
                    if not feature['paired_prints']:
                        state['days'][date]={'status':'complete','replay_sha256':digest(replay),'empty_moneyline_scope':True}
                        save(path,state);continue
                    config={'schema_version':1,'datasets':[{'name':'mlb_'+date,'sport':'mlb',
                        'opportunities':str(replay.resolve()),'features':str((out/'features.jsonl.gz').resolve())}],
                        'spread_measures':['raw','fee_expanded'],'regression_specs':['spread_only','price_and_leg_count'],
                        'weight':'payout_quantity','minimum_edge_filter':None,'orders_enabled':False}
                    save(out/'config.json',config)
                    state.update(status='calibration',active_date=date,updated_at=time.time());save(path,state)
                    execute([sys.executable,str(ROOT/'scripts/spread_calibration_study.py'),'--config',str((out/'config.json').resolve()),
                        '--out',str((out/'calibration').resolve())],out/'calibration.log',state,path)
                    output=out/'calibration/manifest.json'
                    if load(output).get('output_complete') is not True:
                        raise ValueError('missing_calibration_completion')
                    state['days'][date]={'status':'complete','replay_sha256':digest(replay),
                        'paired_prints':feature['paired_prints'],'calibration_manifest':str(output),
                        'calibration_manifest_sha256':digest(output),'ended_at':time.time()}
                    save(path,state)
                requested={d for d,fold in plan['dates'].items() if fold!='previously_inspected_reference'}
                complete=set(state['days'])|set(empty)
                if complete==requested:
                    state.update(status='complete',updated_at=time.time());save(path,state);return
                if not args.watch:
                    state.update(status='available_dates_complete',updated_at=time.time());save(path,state);return
                if time.monotonic()>deadline:
                    raise TimeoutError('followthrough_wait_deadline')
                state.update(status='watching',updated_at=time.time());save(path,state)
                time.sleep(30)
        except BaseException as exc:
            state.update(status='failed',error=repr(exc),updated_at=time.time());save(path,state);raise


if __name__=='__main__':
    main()

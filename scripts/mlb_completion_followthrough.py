#!/usr/bin/env python3
"""Run full-universe and partial-sizing audits after each certified MLB day."""
import argparse
import fcntl
import os
from pathlib import Path
import sys
import time

from mlb_longitudinal_sweep import discover,save,load,digest
from mlb_spread_followthrough import execute
from mlb_historical_batch import frozen_code_paths

ROOT=Path(__file__).resolve().parents[1]


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
        paths=[Path(__file__),args.plan,ROOT/'scripts/mlb_dated_universe_report.py',ROOT/'scripts/mlb_partial_sizing.py',
               ROOT/'src/combos/partial_sizing_research.py',ROOT/'scripts/mlb_spread_followthrough.py',
               ROOT/'src/combos/backtest.py',ROOT/'src/combos/fees.py',ROOT/'src/combos/risk.py',
               *frozen_code_paths()]
        identity={'batch_root':str(args.batch_root.resolve()),'frozen_sha256':{str(p):digest(p) for p in paths},'orders_enabled':False}
        mp=args.out/'manifest.json'
        if mp.exists() and load(mp)!=identity:raise ValueError('followthrough_identity_changed')
        save(mp,identity)
        sp=args.out/'status.json';state=load(sp) if sp.exists() else {'stages':{}}
        state.update(pid=os.getpid(),status='running',updated_at=time.time());save(sp,state)
        plan=load(args.plan);deadline=time.monotonic()+args.max_hours*3600
        try:
            while True:
                for f,h in identity['frozen_sha256'].items():
                    if digest(Path(f))!=h:raise ValueError('followthrough_code_changed:'+f)
                files,empty,batch_states=discover([args.batch_root],plan)
                state.update(available_dates=sorted(files),empty_dates=empty,batch_states=batch_states)
                for date,replay in sorted(files.items()):
                    base=args.out/date;base.mkdir(exist_ok=True)
                    jobs=[('universe',[sys.executable,str(ROOT/'scripts/mlb_dated_universe_report.py'),
                            '--cohort',str(replay.parent.parent/'cohort'),'--out',str(base/'universe')],base/'universe/summary.json'),
                          ('partial_sizing',[sys.executable,str(ROOT/'scripts/mlb_partial_sizing.py'),
                            '--input',str(replay),'--date',date,'--out',str(base/'partial_sizing')],base/'partial_sizing/summary.json')]
                    for stage,cmd,output in jobs:
                        key=date+'/'+stage
                        prior=state['stages'].get(key,{})
                        if prior.get('status')=='complete':
                            if prior['replay_sha256']!=digest(replay) or prior['output_sha256']!=digest(output):
                                raise ValueError('completed_followthrough_evidence_changed:'+key)
                            continue
                        state.update(status='running',stage=key,updated_at=time.time());save(sp,state)
                        execute(cmd,base/(stage+'.log'),state,sp)
                        load(output)
                        state['stages'][key]={'status':'complete','replay_sha256':digest(replay),
                            'output':str(output),'output_sha256':digest(output),'ended_at':time.time()}
                        save(sp,state)
                requested={d for d,fold in plan['dates'].items() if fold!='previously_inspected_reference'}
                complete={d for d in files if all(state['stages'].get(d+'/'+s,{}).get('status')=='complete' for s in ('universe','partial_sizing'))}|set(empty)
                state.update(completed_dates=sorted(complete),updated_at=time.time())
                if complete==requested:
                    state.update(status='complete');save(sp,state);return
                if not args.watch:
                    state.update(status='available_dates_complete');save(sp,state);return
                if time.monotonic()>deadline:raise TimeoutError('followthrough_watch_deadline')
                state['status']='watching';save(sp,state);time.sleep(30)
        except BaseException as exc:
            state.update(status='failed',error=repr(exc),updated_at=time.time());save(sp,state);raise


if __name__=='__main__':main()

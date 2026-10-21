"""Freeze certified development-only batch inputs without reading held-out outcomes."""
import argparse
import hashlib
import json
from pathlib import Path


def select(plan, state):
    dates={d:f for d,f in plan['dates'].items() if f=='development'}
    if not dates: raise ValueError('no development dates')
    allowed={'complete','complete_empty_eligible_scope','collected_unpriced_identity'}
    pending={d:state.get('days',{}).get(d,{}).get('status','missing') for d in dates
             if state.get('days',{}).get(d,{}).get('status') not in allowed}
    projection={**state,'days':{d:state['days'][d] for d in dates if d in state.get('days',{})},
                'stages':{k:v for k,v in state.get('stages',{}).items() if k.split('/')[0] in dates}}
    return {**plan,'dates':dates},projection,pending


def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--plan',type=Path,required=True);p.add_argument('--batch-root',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    plan_bytes=a.plan.read_bytes();state_path=a.batch_root/'batch_status.json';state_bytes=state_path.read_bytes()
    plan,state,pending=select(json.loads(plan_bytes),json.loads(state_bytes))
    if pending:
        print(json.dumps({'ready':False,'pending':pending}));return
    # Reuse the existing completion-certificate and hash validation, without any August paths.
    from mlb_longitudinal_sweep import discover
    files,empty,_=discover([a.batch_root],plan)
    gaps={d:v['status'] for d,v in state['days'].items() if v['status']=='collected_unpriced_identity'}
    assert set(files)|set(empty)|set(gaps)==set(plan['dates'])
    hashes={str(path.resolve()):digest(path) for path in files.values()}
    a.out.mkdir(parents=True,exist_ok=False)
    for day in plan['dates']:(a.out/day).symlink_to((a.batch_root/day).resolve(),target_is_directory=True)
    (a.out/'batch_status.json').write_text(json.dumps(state,indent=2)+'\n')
    (a.out/'development_plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    (a.out/'projection.json').write_text(json.dumps({'original_plan':str(a.plan.resolve()),
        'original_plan_sha256':hashlib.sha256(plan_bytes).hexdigest(),
        'original_status_sha256':hashlib.sha256(state_bytes).hexdigest(),
        'priced_dates':sorted(files),'empty_dates':empty,'unpriced_gaps':gaps,
        'input_sha256':hashes,'held_out_outcomes_read':False,
        'limitation':'Development-only projection of the original full study; gaps remain missing priced coverage, never zero-profit observations.'},indent=2)+'\n')
    print(json.dumps({'ready':True,'priced_dates':len(files),'unpriced_gaps':gaps,'out':str(a.out)}))


if __name__=='__main__':main()

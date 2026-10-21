"""Rebuild the offline research program; no provider requests or live changes."""
import argparse
from datetime import datetime,timezone
import json
import hashlib
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
TESTS=['tests/test_research_program_extract.py','tests/test_research_volume_markouts.py',
       'tests/test_research_inventory_relief.py','tests/test_research_followups.py','tests/test_research_spend_risk.py']


def run(out):
    out=out.resolve();out.mkdir(parents=True,exist_ok=True)
    jobs=[('research_program_extract',[]),('research_volume_markouts',[]),
        ('research_inventory_relief',[]),
        ('research_inventory_relief',['--contract-cap','1000','--combo-cap','250','--tag','_fixture_constrained']),
        ('research_inventory_relief',['--contract-cap','1000','--combo-cap','250','--tag','_conditioned','--condition-settled']),
        ('research_inventory_fee_followup',[]),('research_inventory_repricing',[]),('research_hedge_followup',[]),
        ('research_samegame_history',[]),('research_mlb_volume_clock',[]),
        ('research_final_analysis',[]),('build_research_atlas',[])]
    log={'started_at':datetime.now(timezone.utc).isoformat(),'steps':[]}
    for name,extra in jobs:
        command=[sys.executable,str(ROOT/'scripts'/f'{name}.py'),'--out',str(out),*extra]
        before=hashlib.sha256(Path(command[1]).read_bytes()).hexdigest()
        print('Running',name,*extra,flush=True)
        result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True)
        assert before==hashlib.sha256(Path(command[1]).read_bytes()).hexdigest(),'study script changed during execution'
        log['steps'].append({'command':command,'script_sha256':before,'exit_code':result.returncode,'stdout':result.stdout,'stderr':result.stderr})
        (out/'pipeline_run.json').write_text(json.dumps(log,indent=2)+'\n')
        if result.returncode:raise RuntimeError(result.stderr)
    result=subprocess.run([sys.executable,'-m','pytest','-q',*TESTS],cwd=ROOT,capture_output=True,text=True)
    log['tests']={'command':[sys.executable,'-m','pytest','-q',*TESTS],'exit_code':result.returncode,'stdout':result.stdout,'stderr':result.stderr}
    log['completed_at']=datetime.now(timezone.utc).isoformat()
    (out/'pipeline_run.json').write_text(json.dumps(log,indent=2)+'\n')
    if result.returncode:raise RuntimeError(result.stdout+result.stderr)
    print(result.stdout)
    print('Offline computations complete. Run visual QA and final audit separately.')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);run(p.parse_args().out)

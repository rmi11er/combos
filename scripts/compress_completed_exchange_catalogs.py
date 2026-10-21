#!/usr/bin/env python3
"""Exact-byte native compression of completed dated MLB exchange catalogs only."""
import argparse
import json
import os
from pathlib import Path
from compress_completed_json import replace_compressed, probe
from deduplicate_validation_clones import sha, closed, atomic_json

ROOT=Path(__file__).resolve().parents[1]
BATCH=ROOT/'runs/mlb_historical_20260907/dated_fee_primary'


def certificate(root,date):
    state=json.loads((root/'batch_status.json').read_text());day=state.get('days',{}).get(date,{})
    stage=state.get('stages',{}).get(date+'/exchange',{})
    if day.get('status')!='complete' or stage.get('status')!='complete' or stage.get('exit_code')!=0:return None
    pid=stage.get('child_pid')
    if pid:
        try:os.kill(pid,0)
        except ProcessLookupError:pass
        else:return None
    outputs=stage.get('output_sha256',{})
    required=[(root/date/'exchange'/name).resolve() for name in ('acquisition.json','polymarket_mapping_reviewed.json')]
    for path in required:
        if outputs.get(str(path)) is None or sha(path)!=outputs[str(path)]:raise ValueError('exchange_certificate_output_changed')
    return {'date':date,'day_status':'complete','exchange_status':'complete','exit_code':0,'child_pid':pid,
            'output_sha256':{str(p):outputs[str(p)] for p in required}}


def execute_one(path,pin,root):
    def recheck(target):
        if certificate(root,pin['date'])!=pin['completion']:raise ValueError('completion_changed_before_swap')
        return closed(target)
    if sha(path)!=pin['sha256']:raise ValueError('catalog_changed_since_pin')
    result=replace_compressed(path,check_closed=recheck)
    if sha(path)!=pin['sha256'] or path.stat().st_size!=pin['bytes']:raise ValueError('catalog_logical_bytes_changed')
    if not recheck(path):raise ValueError('catalog_open_after_operation')
    return {**result,'source_sha256_pinned':pin['sha256'],'source_sha256_after':sha(path),'completion':pin['completion']}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--date',action='append');p.add_argument('--out',type=Path,required=True);p.add_argument('--execute',action='store_true');a=p.parse_args()
    a.out.mkdir(parents=True,exist_ok=True)
    state=json.loads((BATCH/'batch_status.json').read_text());dates=sorted(a.date or state.get('days',{}));pins=[];skips=[]
    for date in dates:
        # Prevent date traversal; only the fixed batch's own declared date keys.
        if date not in state.get('days',{}):raise ValueError('date_not_in_batch')
        cert=certificate(BATCH,date)
        if cert is None:skips.append({'date':date,'reason':'date_or_exchange_not_certified_inactive'});continue
        path=BATCH/date/'exchange/pm_events_complete.json'
        if path.is_symlink():raise ValueError('catalog_symlink_refused')
        if path.stat().st_flags & 32:skips.append({'date':date,'reason':'already_native_compressed'});continue
        if path.stat().st_size>=512*1024**2:skips.append({'date':date,'reason':'outside_observed_native_size_support'});continue
        if not closed(path):skips.append({'date':date,'reason':'catalog_open'});continue
        pins.append({'date':date,'path':str(path),'bytes':path.stat().st_size,'sha256':sha(path),'completion':cert})
    atomic_json(a.out/'pinned_inputs.json',{'inputs':pins,'skipped':skips,'script_sha256':sha(Path(__file__))})
    result={'execute':a.execute,'records':[],'skipped':skips,'status':'running','dependency_sha256':{name:sha(Path(__file__).with_name(name)) for name in ('compress_completed_json.py','deduplicate_validation_clones.py')}}
    if a.execute and pins:result['native_probe']=probe(a.out)
    for pin in pins:
        record=execute_one(Path(pin['path']),pin,BATCH) if a.execute else {'path':pin['path'],'status':'planned_only','sha256':pin['sha256']}
        result['records'].append(record);atomic_json(a.out/'summary.json',result)
    result.update(status='complete',allocated_bytes_saved=sum(r.get('allocated_bytes_saved',0) for r in result['records']));atomic_json(a.out/'summary.json',result)
    print(json.dumps({'status':'complete','execute':a.execute,'records':len(result['records']),'allocated_bytes_saved':result['allocated_bytes_saved'],'skipped':skips}))


if __name__=='__main__':main()

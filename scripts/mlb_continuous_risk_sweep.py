"""Continuous funded risk scenarios on an immutable certified development index."""
import argparse
from dataclasses import asdict,replace
import json
from pathlib import Path
import sqlite3
import time
from mlb_disk_index import iter_model,file_digest
from mlb_streaming_longitudinal import evaluate_one
from run_mlb_streaming_snapshot import source_hashes,atomic
from combos.backtest import BacktestConfig


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--index',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    with sqlite3.connect(a.index.resolve().as_uri()+'?mode=ro',uri=True) as db:
        metadata={k:json.loads(v) for k,v in db.execute('SELECT key,value FROM metadata')}
    plan=metadata['plan'];coverage=metadata['coverage']
    if any(f!='development' for f in plan['dates'].values()):raise ValueError('development-only index required')
    missing=[v['date'] if isinstance(v,dict) else v for v in coverage['missing_dates']]
    if len(coverage['observed_dates'])!=15 or missing!=['2026-07-13']:raise ValueError('requires full priced July with explicit July13 gap')
    baseline=BacktestConfig(entry_basis='point',minimum_net_edge_per_share=.003,timezone=plan['timezone'],**plan['baseline_limits'])
    scenarios=[('baseline',baseline),('balanced1000',replace(baseline,per_contract_dollars=1000,per_combo_dollars=1000,per_fixture_dollars=1000)),
        ('fixture1000',replace(baseline,per_contract_dollars=10000,per_combo_dollars=10000,per_fixture_dollars=1000)),
        ('fixture2000',replace(baseline,per_contract_dollars=10000,per_combo_dollars=10000,per_fixture_dollars=2000))]
    a.out.mkdir(parents=True,exist_ok=False);sources=source_hashes();index_hash=file_digest(a.index);began=time.time()
    atomic(a.out/'started.json',{'index':str(a.index.resolve()),'index_sha256':index_hash,'source_hashes':sources,'scenarios':{n:asdict(c) for n,c in scenarios},'coverage':coverage,'started_at':began,'execution':'Hypothetical full observed print quantities/prices; no partial sizing or live orders.'})
    records=[]
    for model in plan['primary_models']:
        for name,config in scenarios:
            print(json.dumps({'model':model,'scenario':name,'status':'running'}),flush=True)
            record,_=evaluate_one(iter_model(a.index,model),model,name,name,config,True,coverage,plan,a.out/(model+'__'+name),artifact_codec='zstd')
            records.append(record)
            atomic(a.out/'progress.json',{'completed_portfolios':len(records),'records':records})
            print(json.dumps({'model':model,'scenario':name,'status':'complete','net':record['portfolio']['trade_attributed_pnl'],'peak_cash':record['portfolio']['peak_committed_cash']}),flush=True)
    if sources!=source_hashes() or index_hash!=file_digest(a.index):raise RuntimeError('source or index changed')
    atomic(a.out/'summary.json',{'records':records,'coverage':coverage,'source_hashes':sources,'index_sha256':index_hash,'elapsed_seconds':time.time()-began})
    atomic(a.out/'complete.json',{'portfolios':len(records),'summary_sha256':file_digest(a.out/'summary.json'),'independent_risk_audit':'pending; completion here proves execution and provenance only'})


if __name__=='__main__':main()

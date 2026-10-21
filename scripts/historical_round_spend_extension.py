"""July/August MLB round-spend proxy replication, fixed policies and cash ledger."""
import argparse
from dataclasses import asdict
import gzip
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from round_spend_proxy_backtest import ROOT,POLICIES,label,metrics
from combos.backtest import BacktestConfig,run_backtest
from combos.event_store import EventStore
import combos.backtest as backtest_module
import tempfile
from unittest.mock import patch

SCENARIOS=[('principal_1cent',.01,None),('principal_5cents',.05,None),
           ('fee007_5cents',.05,'.07'),('fee0035_5cents',.05,'.035'),
           ('whole_contract_fee007','whole_contract_budget','.07')]
FUNDED={'principal_1cent','fee007_5cents','whole_contract_fee007'}


def selected_mask(d,policy,round_labels):
    low,high=POLICIES[policy]
    return d.quote_allowed.to_numpy() & (d.edge.to_numpy()>=np.where(round_labels,low,high)*d.quantity.to_numpy())


def summarize(d,mask):
    f=d[mask];known=f.settlement.notna()
    return {'prints':len(f),'contracts':float(f.quantity.sum()),'net_model_edge':float(f.edge.sum()),
            'net_settlement_pnl':float(f.loc[known,'pnl'].sum()),'unknown_outcomes':int((~known).sum())}


def cash_replay(rows,start,end,cfg):
    with tempfile.TemporaryDirectory(prefix='mlb-round-spend-') as tmp:
        with patch.object(backtest_module,'EventStore',lambda _:EventStore(Path(tmp)/'events.sqlite')):
            return run_backtest(rows,start,end,cfg,True)


def main():
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    cfg=BacktestConfig(entry_basis='point',entry_filter='all_priced');report={'configuration':asdict(cfg),'periods':{},'hashes':{}}
    seen=set();july_fixtures=set()
    for month in ['2026-07','2026-08']:
        rows=[];sample_dates=[];bounds=[];outside_scope=0
        paths=sorted((ROOT/'runs/mlb_historical_20260907/dated_fee_primary').glob(month+'-*/replay/opportunities.json'))
        for path in paths:
            with path.open('rb') as f:report['hashes'][str(path.relative_to(ROOT))]=hashlib.file_digest(f,'sha256').hexdigest()
            data=json.loads(path.read_text());bounds.append((data['start_at'],data['end_at']));date=path.parent.parent.name;sample_dates.append(date)
            for row in data['opportunities']:
                if row['model']!='kalshi':continue
                assert row['evaluation_id'] not in seen,'duplicate historical print across files'
                seen.add(row['evaluation_id'])
                if not (2<=row['source']['nlegs']<=4 and row['source']['series']==['KXMLBGAME'] and
                        len(set(row['buckets']['fixture']))==row['source']['nlegs']):
                    outside_scope+=1;continue
                row['_sample_date']=date;rows.append(row)
            print('loaded',date,'cumulative',len(rows),flush=True)
        del data
        d=pd.DataFrame([dict(id=r['evaluation_id'],quantity=r['quantity'],price=r['yes_price'],
            edge=r['quantity']*(r['yes_price']-r['fair_point'])-r['maker_fee'],quote_allowed=r['quote_allowed'],
            settlement=r['yes_settlement'],pnl=r['quantity']*(r['yes_price']-r['yes_settlement'])-r['maker_fee'] if r['yes_settlement'] is not None else np.nan,
            date=r['_sample_date'],fixture_disjoint=not bool(set(r['buckets']['fixture']) & july_fixtures)) for r in rows])
        result={'prints':len(rows),'outside_scope':outside_scope,'sample_dates':sample_dates,'fractional_quantity_prints':int((d.quantity%1!=0).sum()),
                'fixtures':len({v for r in rows for v in r['buckets']['fixture']}),'scenarios':[]}
        if month=='2026-08':result['july_fixture_disjoint_prints']=int(d.fixture_disjoint.sum())
        start=min(b[0] for b in bounds);end=max(b[1] for b in bounds);funded_cache={}
        for name,tol,fee in SCENARIOS:
            labels=np.array([label(r,tol,fee)[0] for r in rows],dtype=bool)
            s={'name':name,'round_prints':int(labels.sum()),'round_contracts':float(d.quantity[labels].sum()),'policies':{}}
            for policy in POLICIES:
                mask=selected_mask(d,policy,labels);reference='flat04' if POLICIES[policy][1]==.004 else 'flat03'
                base=selected_mask(d,reference,labels);delta=mask.astype(int)-base.astype(int)
                daily=(d.pnl.fillna(0)*delta).groupby(d.date).sum()
                adds=d[(delta==1)&d.settlement.notna()];removes=d[(delta==-1)&d.settlement.notna()]
                entry={'unlimited':summarize(d,mask),'comparison_flat':reference,
                    'incremental_unlimited_pnl':float((d.pnl.fillna(0)*delta).sum()),
                    'added':summarize(d,delta==1),'removed':summarize(d,delta==-1),
                    'daily_incremental_pnl':daily.to_dict(),'positive_sample_dates':int((daily>0).sum()),
                    'negative_sample_dates':int((daily<0).sum()),
                    'incremental_without_largest_added_win':float((d.pnl.fillna(0)*delta).sum()-max(0,adds.pnl.max())) if len(adds) else None}
                if month=='2026-08':entry['july_fixture_disjoint_unlimited']=summarize(d,mask & d.fixture_disjoint.to_numpy())
                if name in FUNDED:
                    key=mask.tobytes()
                    if key not in funded_cache:
                        selected=[r for r,keep in zip(rows,mask) if keep]
                        res=cash_replay(selected,start,end,cfg)
                        selected_ids=set(d.id[mask])
                        assert all(x['fill_id'] in selected_ids for x in res['fills'])
                        funded_cache[key]=metrics(res)
                        with gzip.open(a.out/f'{month}_{name}_{policy}_fills.json.gz','wt') as f:json.dump(res['fills'],f)
                    entry['funded']=funded_cache[key]
                s['policies'][policy]=entry
            result['scenarios'].append(s)
            print(month,name,'round',s['round_prints'],[(k,round(v['incremental_unlimited_pnl'],2),round(v.get('funded',{}).get('trade_attributed_pnl',0),2)) for k,v in s['policies'].items() if k.startswith('round')],flush=True)
        report['periods'][month]=result
        (a.out/'results.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
        if month=='2026-07':july_fixtures={v for r in rows for v in r['buckets']['fixture']}
        del rows,d,funded_cache
    report['limitations']=['Fixed schedules; historical partial fills assumed rare, original spend unknown.',
        'Sampled retained dates, not complete months; monthly risk/cash starts fresh, no daily resets.',
        'Funding runs prefilter ineligible prints; financial fill parity checked separately against the full-row engine.',
        'Observed prices and quantities unchanged; not a quote-discount or acceptance model.',
        'Archived maker fee assumptions and candle-mid fair; settlement PnL, not forward markouts.',
        'August is later-period replication, not claimed untouched research holdout; overlapping July fixtures reported.']
    (a.out/'results.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')


if __name__=='__main__':main()

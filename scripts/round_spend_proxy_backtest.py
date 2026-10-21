"""NFL observed-print replay using explicitly inferred, not known, spend labels."""
import argparse
from dataclasses import asdict
from decimal import Decimal
import gzip
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from combos.backtest import BacktestConfig,run_backtest
from combos.event_store import EventStore
from combos.fees import kalshi_fill_fee
import combos.backtest as backtest_module

def net_edge(row):return row['quantity']*(row['yes_price']-row['fair_point'])-row['maker_fee']


def economics(rows):
    known=[r for r in rows if r.get('yes_settlement') is not None]
    return {'prints':len(rows),'quantity':sum(r['quantity'] for r in rows),
            'net_model_edge':sum(net_edge(r) for r in rows),
            'net_pnl':sum(r['quantity']*(r['yes_price']-r['yes_settlement'])-r['maker_fee'] for r in known),
            'unknown_outcomes':len(rows)-len(known)}


def metrics(result):
    s=result['summaries'][0]
    return {k:s[k] for k in ['fills','trade_attributed_pnl','accepted_point_edge','peak_committed_cash',
        'max_trade_attributed_drawdown_dollars','minimum_starting_funding_for_path','unresolved_outcomes']}

POLICIES={'flat03':(.003,.003),'flat04':(.004,.004),'flat02':(.002,.002),'flat015':(.0015,.0015),
          'round02_other03':(.002,.003),'round015_other03':(.0015,.003),
          'round02_other04':(.002,.004),'round015_other04':(.0015,.004)}


def label(row,tolerance,requester_rate=None,amounts=(5,10,20,50)):
    q,p=Decimal(str(row['quantity'])),Decimal(str(row['yes_price']))
    spend=q*p
    if requester_rate is not None:
        spend+=kalshi_fill_fee(q,p,requester_rate,'buy','.0001')['net_fee']
    nearest=min(amounts,key=lambda v:abs(spend-Decimal(v)))
    if tolerance=='whole_contract_budget':
        # Sensitivity only: observed integer size is the maximum fitting a budget.
        # Integer prints alone do not prove that this was the exchange size grid.
        next_spend=(q+1)*p
        if requester_rate is not None:next_spend+=kalshi_fill_fee(q+1,p,requester_rate,'buy','.0001')['net_fee']
        matches=[v for v in amounts if spend<=Decimal(v)<next_spend]
        return q%1==0 and bool(matches),float(spend),matches[0] if matches else nearest
    return abs(spend-Decimal(nearest))<=Decimal(str(tolerance)),float(spend),nearest


def allowed(row,policy,is_round):
    hurdle=POLICIES[policy][0 if is_round else 1]
    return row['quote_allowed'] and net_edge(row)>=row['quantity']*hurdle


def funded(rows,labels,policy,data,cfg):
    inputs=[{**r,'quote_allowed':allowed(r,policy,labels[r['evaluation_id']])} for r in rows]
    with tempfile.TemporaryDirectory(prefix='round-spend-proxy-') as tmp:
        with patch.object(backtest_module,'EventStore',lambda _:EventStore(Path(tmp)/'events.sqlite')):
            return run_backtest(inputs,data['start_at'],data['end_at'],cfg,True)


def main():
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    path=ROOT/'runs/nfl_moneyline_replay_20260907/jan5_18/opportunities.json'
    data=json.loads(path.read_text());rows=[r for r in data['opportunities'] if r['model']=='kalshi']
    cfg=BacktestConfig(entry_basis='point',entry_filter='all_priced')
    report={'input':str(path),'input_sha256':hashlib.file_digest(path.open('rb'),'sha256').hexdigest(),
            'config':asdict(cfg),'policies':POLICIES,'prints':len(rows),'scenarios':[],
            'assumption':'Partial fills are uncommon; inferred spend is an approximate requester label, not ground truth.'}
    for name,tolerance,rate,amounts in [('principal_1cent',.01,None,(5,10,20,50)),
          ('principal_5cents',.05,None,(5,10,20,50)),('principal_exact',0,None,(5,10,20,50)),
          ('fee007_1cent',.01,'.07',(5,10,20,50)),
          ('fee0035_1cent',.01,'.035',(5,10,20,50)),
          ('principal_50cents',.5,None,(5,10,20,50)),
          ('whole_contract_fee007','whole_contract_budget','.07',(5,10,20,50)),
          ('whole_contract_fee0035','whole_contract_budget','.035',(5,10,20,50)),
          ('principal_broad_1cent',.01,None,(1,2,5,10,20,25,50,100))]:
        labels={r['evaluation_id']:label(r,tolerance,rate,amounts)[0] for r in rows}
        round_rows=[r for r in rows if labels[r['evaluation_id']]]
        base={r['evaluation_id'] for r in rows if allowed(r,'flat03',False)}
        result={'name':name,'round_amounts':amounts,'tolerance_dollars':tolerance,'requester_rate_scenario':rate,
                'round_prints':len(round_rows),'round_contracts':sum(r['quantity'] for r in round_rows),
                'round_economics_all':economics(round_rows),'policies':{}}
        for policy in POLICIES:
            selected=[r for r in rows if allowed(r,policy,labels[r['evaluation_id']])]
            ids={r['evaluation_id'] for r in selected};new=[r for r in selected if r['evaluation_id'] not in base]
            removed=[r for r in rows if r['evaluation_id'] in base-ids]
            replay=funded(rows,labels,policy,data,cfg)
            entry={'unlimited':economics(selected),'funded':metrics(replay),
                   'added_vs_flat03':economics(new),'removed_vs_flat03':economics(removed)}
            matching_flat='flat04' if POLICIES[policy][1]==.004 else 'flat03'
            entry['unlimited_delta_vs_same_other_flat_hurdle']=economics(selected)['net_pnl']-economics([r for r in rows if allowed(r,matching_flat,False)])['net_pnl']
            if name=='principal_1cent':
                with gzip.open(a.out/f'{policy}_funded.json.gz','wt') as f:json.dump(replay,f)
                fixtures=sorted({f for r in rows for f in r['buckets']['fixture']})
                deltas=[]
                for fixture in fixtures:
                    rr=[r for r in rows if fixture not in r['buckets']['fixture']]
                    delta=economics([r for r in rr if allowed(r,policy,labels[r['evaluation_id']])])['net_pnl']-economics([r for r in rr if allowed(r,'flat03',False)])['net_pnl']
                    deltas.append(delta)
                entry['leave_fixture_out_unlimited_delta_range']=[min(deltas),max(deltas)]
                late=[r for r in rows if r['at']>=1768370400] # 2026-01-14 00:00 America/Chicago
                entry['jan14_on_unlimited']=economics([r for r in late if allowed(r,policy,labels[r['evaluation_id']])])
                profits=[r['quantity']*(r['yes_price']-r['yes_settlement'])-r['maker_fee'] for r in new if r.get('yes_settlement') is not None]
                entry['added_pnl_without_largest_win']=sum(profits)-max(profits) if profits else None
            result['policies'][policy]=entry
        report['scenarios'].append(result)
        print(name,len(round_rows),[(p,round(v['unlimited']['net_pnl'],2),v['funded']['fills'],round(v['funded']['trade_attributed_pnl'],2)) for p,v in result['policies'].items()],flush=True)
    first=report['scenarios'][0]['policies']['flat03']
    old=json.loads((ROOT/'runs/nfl_edge_schedule_20260909/results.json').read_text())['results']['flat_0.3']
    assert abs(first['funded']['trade_attributed_pnl']-old['funded']['trade_attributed_pnl'])<1e-8
    assert first['funded']['fills']==old['funded']['fills']
    assert abs(first['unlimited']['net_pnl']-old['eligible']['net_pnl'])<1e-8
    report['baseline_parity']=True
    report['limitations']=['Proxy spends depend on observed execution price; not a known pre-quote field.',
        'Selection at observed prices/full quantities, not repricing or predicted acceptance; no live orders.',
        'Archived maker coefficient .035 is historically unverified; inferred requester fee scenarios also unverified.',
        'Nine shared NFL fixtures, prior candle mids and settlement rather than forward markouts.',
        'Near-round traded principal can also arise from fixed-size orders; partial-fill rarity does not remove this confound.',
        'Largest-win and fixture-omission checks are development diagnostics, not independent validation.']
    (a.out/'results.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')


if __name__=='__main__':main()

"""Fixed NFL edge schedule comparison on retained historical public prints."""
import argparse
from dataclasses import asdict
from datetime import datetime
from decimal import Decimal
import gzip
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch
from zoneinfo import ZoneInfo

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from combos.backtest import BacktestConfig, run_backtest
from combos.fees import kalshi_fill_fee
from combos.event_store import EventStore
import combos.backtest as backtest_module

SCHEDULES={
    'flat_0.2':('flat',.002,0), 'flat_0.3':('flat',.003,0), 'flat_0.5':('flat',.005,0),
    'mid_10_40':('mid',.1,.4), 'mid_10_50':('mid',.1,.5), 'mid_10_60':('mid',.1,.6),
    'trade_10_40':('trade',.1,.4), 'trade_10_50':('trade',.1,.5), 'trade_10_60':('trade',.1,.6),
}


def hurdle(row,name,kalshi_mid):
    basis,lo,hi=SCHEDULES[name]
    if basis=='flat':return lo
    price=kalshi_mid[row['evaluation_id']] if basis=='mid' else row['yes_price']
    return .002+.003*min(1,max(0,(price-lo)/(hi-lo)))


def net_edge(row):return row['quantity']*(row['yes_price']-row['fair_point'])-row['maker_fee']


def passes(row,name,mids):
    return row['quote_allowed'] and net_edge(row)>=row['quantity']*hurdle(row,name,mids)


def economics(rows):
    known=[r for r in rows if r.get('yes_settlement') is not None]
    return {'prints':len(rows),'quantity':sum(r['quantity'] for r in rows),
            'net_model_edge':sum(net_edge(r) for r in rows),
            'net_pnl':sum(r['quantity']*(r['yes_price']-r['yes_settlement'])-r['maker_fee'] for r in known),
            'unknown_outcomes':len(rows)-len(known)}


def replay(rows,name,mids,data,cfg,constrained):
    # Preserve prices, fees, fair values, sizes and risk identities. Apply the
    # schedule only to quote_allowed, then reuse the original settlement ledger.
    inputs=[{**r,'quote_allowed':passes(r,name,mids),
             'research_required_edge_per_share':hurdle(r,name,mids)} for r in rows]
    # The current EventStore periodically stats its on-disk path, even when
    # the core replay requests ':memory:'. Use a real temporary research DB
    # so runs with >256 ledger events exercise that check correctly.
    with tempfile.TemporaryDirectory(prefix='nfl-edge-schedule-') as tmp:
        with patch.object(backtest_module,'EventStore',lambda _:EventStore(Path(tmp)/'events.sqlite')):
            return run_backtest(inputs,data['start_at'],data['end_at'],cfg,constrained)


def metrics(result):
    s=result['summaries'][0]
    keys=['fills','trade_attributed_pnl','accepted_point_edge','peak_committed_cash',
          'max_trade_attributed_drawdown_dollars','minimum_starting_funding_for_path','unresolved_outcomes']
    return {k:s[k] for k in keys}


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
    a.out.mkdir(parents=True,exist_ok=True)
    source=ROOT/'runs/nfl_moneyline_replay_20260907/jan5_18/opportunities.json'
    data=json.loads(source.read_text());rows=[r for r in data['opportunities'] if r['model']=='kalshi']
    mids={r['evaluation_id']:r['fair_point'] for r in rows}
    assert len(mids)==len(rows)
    # The primary interpretation is a NET-after-maker-fee hurdle per contract.
    # Ramp anchor points are fixed scenarios, not fitted to realized outcomes.
    cfg=BacktestConfig(entry_basis='point',entry_filter='all_priced')
    report={'source':str(source.relative_to(ROOT)), 'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
      'schedule_units':'USD per payout contract after maker fee. 0.002 dollars = 0.2 cents.',
      'schedules':SCHEDULES,'primary':'mid_10_50', 'primary_configuration':asdict(cfg),
      'sample_prints':len(rows), 'fee_assumption':'Archived maker coefficient .035; effective January applicability unverified.',
      'interpretation':'Historical full-print selection at observed prices. No repricing, acceptance or queue model.',
      'results':{},'fee_sensitivity':[],'model_sensitivity':[],'capacity_sensitivity':[], 'fixture_omission':[]}
    baseline_ids={r['evaluation_id'] for r in rows if passes(r,'flat_0.3',mids)}
    cache={}
    for name in SCHEDULES:
        admitted=[r for r in rows if passes(r,name,mids)]
        ids={r['evaluation_id'] for r in admitted}
        entry={'eligible':economics(admitted),
               'new_vs_flat03':economics([r for r in rows if r['evaluation_id'] in ids-baseline_ids]),
               'removed_vs_flat03':economics([r for r in rows if r['evaluation_id'] in baseline_ids-ids])}
        for funded in [False,True]:
            regime='funded' if funded else 'unlimited'
            res=replay(rows,name,mids,data,cfg,funded)
            assert all(passes(r,name,mids) for r in res['decisions'] if r['accepted'])
            if not funded: assert {r['fill_id'] for r in res['fills']}==ids
            entry[regime]=metrics(res)
            if name in ['flat_0.2','flat_0.3','mid_10_50','trade_10_50']:
                cache[name,regime]=res
                with gzip.open(a.out/f'{name}_{regime}.json.gz','wt') as f:json.dump(res,f,separators=(',',':'))
        report['results'][name]=entry
        print(name,entry['funded'],flush=True)
    # Reproduce the archived fixed-0.3 baseline in both capacity regimes.
    for funded in [False,True]:
        regime='funded' if funded else 'unlimited'
        archive=source.parent/f'fee0.035_{regime}_selection.json.gz'
        with gzip.open(archive,'rt') as f:old=json.load(f)
        oldfills={r['fill_id']:r for r in old['fills'] if r['model']=='kalshi'}
        newfills={r['fill_id']:r for r in cache['flat_0.3',regime]['fills']}
        assert oldfills==newfills,'archived baseline fill parity failed'
        report[regime+'_baseline_exact_fill_parity']=len(oldfills)
    for rate in ['0','0.0175','0.035','0.07']:
        rr=[{**r,'maker_fee':float(kalshi_fill_fee(str(r['quantity']),1-Decimal(str(r['yes_price'])),rate)['net_fee'])} for r in rows]
        if rate=='0.035':assert all(abs(x['maker_fee']-y['maker_fee'])<1e-9 for x,y in zip(rows,rr))
        for name in ['flat_0.2','flat_0.3','mid_10_50','trade_10_50']:
            report['fee_sensitivity'].append({'rate':rate,'schedule':name,**economics([r for r in rr if passes(r,name,mids)])})
    for model in ['kalshi','polymarket','exchange_blend_pm75']:
        rr=[r for r in data['opportunities'] if r['model']==model]
        assert {r['evaluation_id'] for r in rr}==set(mids)
        for name in ['flat_0.3','mid_10_50','trade_10_50']:
            report['model_sensitivity'].append({'model':model,'schedule':name,**economics([r for r in rr if passes(r,name,mids)])})
    for cap in [500,1000,2000]:
        alt=BacktestConfig(entry_basis='point',entry_filter='all_priced',per_contract_dollars=cap,per_combo_dollars=cap,per_fixture_dollars=cap*2)
        for name in ['flat_0.2','flat_0.3','mid_10_50']:
            res=replay(rows,name,mids,data,alt,True)
            report['capacity_sensitivity'].append({'contract_combo_cap':cap,'fixture_cap':2*cap,'schedule':name,**metrics(res)})
    fixtures=sorted({f for r in rows for f in r['buckets']['fixture']})
    for fixture in fixtures:
        rr=[r for r in rows if fixture not in r['buckets']['fixture']]
        pair={}
        for name in ['flat_0.3','mid_10_50']:
            pair[name]={'funded':metrics(replay(rr,name,mids,data,cfg,True)),
                        'unlimited':economics([r for r in rr if passes(r,name,mids)])}
        report['fixture_omission'].append({'fixture':fixture,'reallocated':True,'results':pair})
    for name in ['flat_0.3','mid_10_50']:
        rr=[r for r in rows if passes(r,name,mids)]
        profits=sorted((r['quantity']*(r['yes_price']-r['yes_settlement'])-r['maker_fee'],r['evaluation_id']) for r in rr if r['yes_settlement'] is not None)
        report['results'][name]['largest_win']=profits[-1]
        report['results'][name]['pnl_excluding_largest_win']=economics(rr)['net_pnl']-profits[-1][0]
        for block in ['2026-01-14']:
            late=[r for r in rr if datetime.fromtimestamp(r['at'],ZoneInfo('America/Chicago')).date().isoformat()>=block]
            report['results'][name]['jan14_18_selected']=economics(late)
    report['limitations']=['Inspected development period with only nine games, not a new independent holdout.',
      'Demand elasticity and maker acceptance unobserved; filtering public prints cannot identify optimal quotes.',
      'Historical candle mids and fee assumptions; exceptional payoff parity not fully verified.',
      'Historical forward markouts absent for this study; settlement profit is not a short-horizon markout.',
      'Primary schedule basis is Kalshi midpoint probability; 10-to-40/50/60c are fixed sensitivity anchors.']
    (a.out/'results.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    fig,axes=plt.subplots(2,2,figsize=(12,8),layout='constrained')
    colors={'flat_0.2':'#888888','flat_0.3':'#333333','mid_10_50':'#277aa5','trade_10_50':'#b3611e'}
    for name in colors:
        x=np.linspace(0,.7,141)
        basis,lo,hi=SCHEDULES[name]
        y=np.full(len(x),lo*100) if basis=='flat' else .2+.3*np.clip((x-lo)/(hi-lo),0,1)
        axes[0,0].plot(x*100,y,label=name,color=colors[name])
        for regime,ax in [('funded',axes[0,1]),('unlimited',axes[1,0])]:
            curves=cache[name,regime]['curves']
            ax.plot([datetime.fromtimestamp(r['at'],ZoneInfo('America/Chicago')) for r in curves],[r['trade_attributed_pnl'] for r in curves],label=name,color=colors[name])
            ax.set_title(regime+' · eventual net P&L at trade time');ax.set_ylabel('Dollars');ax.tick_params(axis='x',rotation=25)
    axes[0,0].set_title('Net edge hurdle after maker fee');axes[0,0].set_xlabel('Schedule input price (¢)');axes[0,0].set_ylabel('Required net edge (¢/contract)');axes[0,0].legend(fontsize=8)
    for name in ['flat_0.2','flat_0.3','mid_10_50']:
        r=[x for x in report['capacity_sensitivity'] if x['schedule']==name]
        axes[1,1].plot([x['contract_combo_cap'] for x in r],[x['trade_attributed_pnl'] for x in r],'o-',label=name,color=colors[name])
    axes[1,1].set_title('Capacity sensitivity · fixed $10k capital');axes[1,1].set_xlabel('Contract/combo cap ($); fixture cap = 2×');axes[1,1].set_ylabel('Eventual net P&L ($)');axes[1,1].legend(fontsize=8)
    for ax in axes.flat:ax.grid(alpha=.2)
    fig.suptitle('NFL January 5–18 · public-print schedule sensitivity\nHypothetical full fills, archived fees, nine fixtures; no measured demand elasticity')
    fig.savefig(a.out/'schedules.png',dpi=160)
    print('Completed',a.out,flush=True)


if __name__=='__main__':main()

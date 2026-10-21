#!/usr/bin/env python3
"""MLB complete-day model selection against matched seller benchmarks.

Each constrained model has one shared portfolio. Facets attribute that same
portfolio's fills; they do not allocate a fresh $10,000 to each subgroup.
"""
import argparse
from collections import defaultdict
from dataclasses import asdict
from datetime import datetime,timezone,timedelta
import gzip
import hashlib
import json
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from combos.backtest import BacktestConfig,run_backtest
from mlb_exchange_acquire import stamp


def write(path,data):path.write_text(json.dumps(data,indent=2,allow_nan=False)+'\n')
def gziprows(path,rows):
    with gzip.open(path,'wt') as f:
        for r in rows:f.write(json.dumps(r,separators=(',',':'),allow_nan=False)+'\n')


def metrics(rows):
    known=[r for r in rows if r['yes_settlement'] is not None]
    unknown=[r for r in rows if r['yes_settlement'] is None]
    pnl=sum(r['quantity']*(r['yes_price']-r['yes_settlement'])-r['maker_fee'] for r in known)
    return {'prints':len(rows),'known_outcomes':len(known),'unknown_outcomes':len(unknown),
            'known_net_pnl':pnl,'yes_premium':sum(r['quantity']*r['yes_price'] for r in rows),
            'payout_notional':sum(r['quantity'] for r in rows),'fees':sum(r['maker_fee'] for r in rows),
            'point_edge':sum(r['quantity']*(r['yes_price']-r['fair_point'])-r['maker_fee'] for r in rows),
            'loose_final_pnl_bounds':[pnl+sum(r['quantity']*(r['yes_price']-1)-r['maker_fee'] for r in unknown),
                                    pnl+sum(r['quantity']*r['yes_price']-r['maker_fee'] for r in unknown)]}


def curve(rows,start,end,kind='pnl'):
    changes=defaultdict(float)
    for r in rows:
        if kind=='pnl':
            if r['yes_settlement'] is None:continue
            amount=r['quantity']*(r['yes_price']-r['yes_settlement'])-r['maker_fee']
        elif kind=='edge':amount=r['quantity']*(r['yes_price']-r['fair_point'])-r['maker_fee']
        elif kind=='premium':amount=r['quantity']*r['yes_price']
        elif kind=='payout':amount=r['quantity']
        changes[r['at']]+=amount
    points=[(start,10000. if kind=='pnl' else 0.)];total=points[0][1]
    for at,value in sorted(changes.items()):total+=value;points.append((at,total))
    points.append((end,total))
    return [datetime.fromtimestamp(at,timezone.utc) for at,_ in points],[v for _,v in points]


def cuts(row):
    premium=row['quantity']*row['yes_price'];lead=row['source']['start_at']-row['at']
    return {'legs':str(row['source']['nlegs']),
            'premium':'≤$10' if premium<=10 else '$10–50' if premium<=50 else '>$50',
            'family':'Moneyline only' if row['source']['series']==['KXMLBGAME'] else 'Includes run line / total',
            'time_to_start':'1–15 minutes' if lead<=900 else '15–60 minutes' if lead<=3600 else '>60 minutes'}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',type=Path,default=ROOT/'runs/mlb_historical_20260907/replay/opportunities.json')
    p.add_argument('--out',type=Path,default=ROOT/'runs/mlb_historical_20260907/model_report')
    p.add_argument('--common-only',action='store_true',help='Rerun complete portfolios on the common available-model intersection')
    p.add_argument('--date',default='2026-09-05',help='A complete census date in America/Chicago')
    args=p.parse_args();args.out.mkdir(parents=True,exist_ok=True)
    raw=args.input.read_bytes();data=json.loads(raw)
    day=datetime.strptime(args.date,'%Y-%m-%d').replace(tzinfo=ZoneInfo('America/Chicago'))
    start=day.timestamp();end=(day+timedelta(days=1)).timestamp()
    date_label=day.strftime('%B %d, %Y')
    rows=[r for r in data['opportunities'] if start<=r['at']<end and r['source']['sampling_method']=='census']
    if args.common_only:
        model_ids=defaultdict(set)
        for row in rows:model_ids[row['model']].add(row['evaluation_id'])
        common_ids=set.intersection(*model_ids.values()) if model_ids else set()
        rows=[r for r in rows if r['evaluation_id'] in common_ids]
    if not rows:raise ValueError('no_priced_complete_day_data')
    config=BacktestConfig(entry_basis='point')
    results={}
    for constrained in (True,False):
        name='constrained' if constrained else 'unconstrained'
        result=run_backtest(rows,start,end,config,constrained)
        gziprows(args.out/(name+'_decisions.jsonl.gz'),result['decisions'])
        gziprows(args.out/(name+'_curves.jsonl.gz'),result['curves'])
        gziprows(args.out/(name+'_fills.jsonl.gz'),result['fills'])
        write(args.out/(name+'_summary.json'),{k:v for k,v in result.items() if k not in ('decisions','curves','fills','daily')})
        results[name]=result
    by_model=defaultdict(list)
    for row in rows:by_model[row['model']].append(row)
    series={};summaries={};strata=[]
    for model,allrows in by_model.items():
        series[model]={'all_priced':allrows}
        for regime,result in results.items():
            ids={d['evaluation_id'] for d in result['decisions'] if d['model']==model and d['accepted']}
            series[model][regime]=[r for r in allrows if r['evaluation_id'] in ids]
        summaries[model]={group:metrics(rs) for group,rs in series[model].items()}
        for group,rs in series[model].items():
            subsets=defaultdict(list)
            for r in rs:
                for dimension,value in cuts(r).items():subsets[(dimension,value)].append(r)
            strata.extend({'model':model,'group':group,'dimension':dim,'value':value,**metrics(subset)}
                          for (dim,value),subset in subsets.items())
    write(args.out/'comparison.json',summaries);write(args.out/'strata.json',strata)
    plt.style.use('dark_background');plt.rcParams['text.parse_math']=False
    colors={'all_priced':'#cccccc','unconstrained':'#e7b078','constrained':'#84c9be'}
    labels={'all_priced':'Sell every priced print','unconstrained':'Selected, unlimited','constrained':'Selected, $10k + risk limits'}
    tz=ZoneInfo('America/Chicago')
    for model,groups in series.items():
        fig,axes=plt.subplots(4,1,figsize=(13,13),sharex=True)
        for ax,nlegs in zip(axes,[None,2,3,4]):
            for group,rs in groups.items():
                subset=[r for r in rs if nlegs is None or r['source']['nlegs']==nlegs]
                m=metrics(subset);x,y=curve(subset,start,end)
                ax.step(x,y,where='post',color=colors[group],label=f'{labels[group]}: ${m["known_net_pnl"]:,.0f}; {m["prints"]:,} prints')
            ax.set_title('All 2–4 legs' if nlegs is None else f'{nlegs} legs · contribution from the same portfolio')
            ax.set_ylabel('$10k base + known P&L');ax.grid(alpha=.2);ax.legend(fontsize=9)
            ax.ticklabel_format(axis='y',style='plain',useOffset=False)
        axes[0].plot([],[],color='none',label='Daily Sharpe / variance: N/A (one complete day)');axes[0].legend(fontsize=9)
        axes[-1].xaxis.set_major_formatter(mdates.DateFormatter('%H:%M',tz=tz));axes[-1].set_xlabel(date_label+' · America/Chicago')
        universe='common available-model intersection' if args.common_only else 'source-specific priceable universe'
        fig.suptitle(f'MLB {model} · {universe} and selections\nPoint-entry diagnostic: ≥0.3 cents net edge per contract; no premium cap',fontsize=13)
        fig.text(.07,.025,'Hypothetical public-print sells; no RFQ-win model. Known settlement P&L attributed to trade time; spendable cash releases at settlement.\n'
                 'All/unlimited curves exceed a $10k portfolio’s capacity. Limits: $100/underlying and combo, $250/fixture. Subsets share one portfolio.\n'
                 'Same-game combos excluded; normal-game, original-schedule proxy; historical prices and fee metadata assumptions. Unknown outcomes remain excluded.',fontsize=8)
        fig.tight_layout(rect=(0,.075,1,.95))
        for ext in ('png','svg'):fig.savefig(args.out/(model+'_selection.'+ext),dpi=155)
        plt.close(fig)
        fig,axes=plt.subplots(3,1,figsize=(13,10),sharex=True)
        for group in ('constrained','unconstrained'):
            rs=groups[group]
            for ax,kind in zip(axes,('edge','premium','payout')):
                x,y=curve(rs,start,end,kind);ax.step(x,y,where='post',label=labels[group],color=colors[group])
        for ax,title in zip(axes,('Cumulative selected net model edge ($)','Cumulative selected YES premium ($)','Cumulative selected payout notional ($)')):
            ax.set_ylabel(title);ax.grid(alpha=.2);ax.legend(fontsize=9)
        axes[-1].xaxis.set_major_formatter(mdates.DateFormatter('%H:%M',tz=tz))
        fig.suptitle(f'MLB {model} · selected edge and volume · {date_label}',fontsize=13)
        fig.text(.07,.02,'Edge is summed at trade time using observed quantities. It does not fund new trades before settlement. This is a public-print capacity diagnostic.',fontsize=8)
        fig.tight_layout(rect=(0,.05,1,.95))
        for ext in ('png','svg'):fig.savefig(args.out/(model+'_edge_volume.'+ext),dpi=155)
        plt.close(fig)
    # Separate portfolio scales keep a $100 funded move visible beside an
    # unlimited benchmark that can move hundreds of thousands of dollars.
    model_colors={'kalshi':'#73a0c4','polymarket':'#84c9be','pinnacle':'#e7b078',
                  'blend':'#b497d6','stronger_pinnacle':'#e493af',
                  'exchange_blend_equal':'#d2bd69','exchange_blend_pm75':'#c78aca'}
    for regime,result in results.items():
        fig,axes=plt.subplots(4,1,figsize=(13,12),sharex=True,gridspec_kw={'height_ratios':[2,1,1,1]})
        for model,groups in series.items():
            rs=groups[regime];m=metrics(rs);color=model_colors.get(model)
            for ax,kind in zip(axes[:3],('pnl','edge','premium')):
                x,y=curve(rs,start,end,kind)
                label=(f'{model}: P&L ${m["known_net_pnl"]:,.2f}; {m["prints"]} prints; '
                       f'{m["unknown_outcomes"]} unknown; Sharpe / daily variance N/A') if kind=='pnl' else model
                ax.step(x,y,where='post',color=color,label=label)
            cash=[r for r in result['curves'] if r['model']==model]
            axes[3].step([datetime.fromtimestamp(r['at'],timezone.utc) for r in cash],
                         [r['committed_cash'] for r in cash],where='post',color=color,label=model)
        for ax,title in zip(axes,('Trade-attributed equity ($)','Selected net model edge ($)','Selected YES premium ($)','Committed cash ($)')):
            ax.set_ylabel(title);ax.grid(alpha=.2);ax.legend(fontsize=9)
            ax.ticklabel_format(axis='y',style='plain',useOffset=False)
        axes[-1].xaxis.set_major_formatter(mdates.DateFormatter('%H:%M',tz=tz))
        axes[-1].set_xlabel(date_label+' · America/Chicago')
        basis='Common available-model intersection' if args.common_only else 'Each model’s available coverage'
        capital='$10k capital; $100/underlying and combo; $250/fixture' if regime=='constrained' else 'Unlimited funding and concentration; $10k reporting base'
        fig.suptitle(f'MLB {regime} · {capital}\n{basis}; point entry ≥0.3 cents net / contract; no premium cap',fontsize=12)
        availability='Pinnacle blend unavailable: missing MLB history.' if 'blend' not in by_model else 'Three-source blend evaluated on recorded historical inputs.'
        fig.text(.07,.025,'One complete day: daily Sharpe and variance unavailable. Known settlement P&L is attributed to trade time; cash releases at settlement.\n'
                 'Hypothetical public-print sells. '+availability+' No quote acceptance is inferred.',fontsize=8)
        fig.tight_layout(rect=(0,.065,1,.94))
        for ext in ('png','svg'):fig.savefig(args.out/(regime+'.'+ext),dpi=155)
        plt.close(fig)
    common=set.intersection(*({r['evaluation_id'] for r in rs} for rs in by_model.values()))
    write(args.out/'common_cohort_metrics.json',{
        model:metrics([r for r in rs if r['evaluation_id'] in common]) for model,rs in by_model.items()})
    manifest={'input_sha256':hashlib.sha256(raw).hexdigest(),'config':asdict(config),'start_at':start,'end_at':end,
       'available_models':sorted(by_model),'unavailable_models':sorted({'pinnacle','blend','stronger_pinnacle'}-set(by_model)),
       'complete_calendar_days':1,'daily_sharpe':None,'daily_return_variance':None,'statistics_reason':'one_complete_day',
       'three_source_status':'available' if 'blend' in by_model else 'missing_Pinnacle_history_not_a_zero_fill_result',
       'source_run_id':data['run_id'],'code_sha256':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in
           [Path(__file__),ROOT/'src/combos/backtest.py',ROOT/'src/combos/risk.py',ROOT/'src/combos/fees.py']}}
    manifest['cohort_basis']='common_available_model_intersection_portfolios_rerun' if args.common_only else 'source_specific_priceable_universes'
    write(args.out/'manifest.json',manifest)
    print(json.dumps(summaries,indent=2))

if __name__=='__main__':main()

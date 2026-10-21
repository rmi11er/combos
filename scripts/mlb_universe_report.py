#!/usr/bin/env python3
"""Fee-inclusive public-print seller diagnostics; no inferred RFQ fills."""
import argparse
from collections import defaultdict
from datetime import datetime
import gzip
import hashlib
import json
from pathlib import Path
import sys
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
matplotlib.rcParams['text.parse_math']=False
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
ROOT=Path(__file__).resolve().parents[1]
ZONE=ZoneInfo('America/Chicago')

def economics(q,p,fee,settlement):
 return {'known_pnl':0. if settlement is None else q*(p-settlement)-fee,
 'unknown_lower':q*(p-1)-fee if settlement is None else 0.,
 'unknown_upper':q*p-fee if settlement is None else 0.}

def load_rows(path):
 rows=[];excluded=0
 with gzip.open(path,'rt') as f:
  for line in f:
   r=json.loads(line);t=r['trade'];c=r['classification']
   if t.get('taker_side')!='yes':excluded+=1;continue
   at=datetime.fromisoformat(t['created_time'].replace('Z','+00:00'));q=float(t['count_fp']);p=float(t['yes_price_dollars']);fee=r['maker_fee_dollars'];settle=r['settlement_value'];prem=q*p
   row={'trade_id':t['trade_id'],'ticker':t['ticker'],'trade_at':at,'day':at.astimezone(ZONE).date().isoformat(),'sampling_method':r['sampling_method'],'quantity':q,'yes_price':p,'yes_premium':prem,'maker_fee':fee,'no_cash':q*(1-p)+fee,'settlement_value':settle,'settlement_at':r['settlement_at'],'nlegs':c['nlegs'],'leg_bucket':str(c['nlegs']) if c['nlegs']<5 else '5+','structure':'Distinct games' if c['distinct_fixtures'] else 'Contains same-game legs','family':'Full-game core' if c['fullgame_core'] else 'Known player prop' if c['known_player_prop'] else 'Other / unclassified family','phase':'Pregame schedule proxy' if r['pregame_scheduled_proxy'] is True else 'After scheduled start' if r['pregame_scheduled_proxy'] is False else 'Unknown start','premium_bucket':'YES premium ≤ $50' if prem<=50 else 'YES premium > $50','fixtures':sorted(set(c['fixture_tokens'])),'known':settle is not None,**economics(q,p,fee,settle)}
   rows.append(row)
 frame=pd.DataFrame(rows).sort_values(['trade_at','trade_id']).reset_index(drop=True)
 if frame.trade_id.duplicated().any():raise ValueError('Duplicate trade IDs')
 return frame,excluded

def summary(frame):
 pnl=float(frame.known_pnl.sum());unknown=frame[~frame.known]
 return {'prints':len(frame),'known_settlement_prints':int(frame.known.sum()),'unknown_settlement_prints':len(unknown),'known_net_pnl':pnl,'all_print_yes_premium':float(frame.yes_premium.sum()),'all_print_payout_face':float(frame.quantity.sum()),'all_print_maker_fees':float(frame.maker_fee.sum()),'known_print_maker_fees':float(frame.loc[frame.known,'maker_fee'].sum()),'all_print_NO_cash':float(frame.no_cash.sum()),'unknown_NO_cash':float(unknown.no_cash.sum()),'unknown_yes_premium':float(unknown.yes_premium.sum()),'unknown_payout_face':float(unknown.quantity.sum()),'full_outcome_lower_bound':pnl+float(frame.unknown_lower.sum()),'full_outcome_upper_bound':pnl+float(frame.unknown_upper.sum()),'known_pnl_over_all_committed_NO_cash':pnl/float(frame.no_cash.sum()) if len(frame) else None}

def curve(frame):
 f=frame.set_index('trade_at')[['known_pnl','unknown_lower','unknown_upper','yes_premium','quantity','maker_fee']].resample('5min',label='right',closed='right').sum().cumsum()
 f['lower_pnl']=f.known_pnl+f.unknown_lower;f['upper_pnl']=f.known_pnl+f.unknown_upper
 return f

def concentration(frame):
 known=frame[frame.known];pnl=float(known.known_pnl.sum());rows=known[['trade_id','ticker','known_pnl','yes_premium','quantity','nlegs','fixtures']]
 combo=known.groupby('ticker').agg(known_pnl=('known_pnl','sum'),prints=('trade_id','size'),yes_premium=('yes_premium','sum'),quantity=('quantity','sum')).reset_index()
 fs=defaultdict(lambda:{'known_pnl':0.,'prints':0})
 for r in known.itertuples():
  for fixture in r.fixtures:fs[fixture]['known_pnl']+=r.known_pnl;fs[fixture]['prints']+=1
 fixtures=pd.DataFrame([{'fixture':k,**v,'pnl_after_excluding_fixture':pnl-v['known_pnl']} for k,v in fs.items()])
 def top(d):return {'largest_profits':d.nlargest(15,'known_pnl').to_dict('records'),'largest_losses':d.nsmallest(15,'known_pnl').to_dict('records')}
 return {'print':top(rows),'combo':top(combo),'fixture':top(fixtures),'top_10_print_profit':float(rows.nlargest(10,'known_pnl').known_pnl.sum()),'top_10_combo_profit':float(combo.nlargest(10,'known_pnl').known_pnl.sum()),'largest_combo_removed_pnl':pnl-float(combo.known_pnl.max()),'best_fixture_removed_pnl':pnl-float(fixtures.known_pnl.max()),'fixture_warning':'Each print contributes once to every unique fixture it contains; fixture totals overlap and are not additive. Exclusion P&L removes all related prints.'}

def plot_report(frame,out,scope):
 fig,axes=plt.subplots(3,2,figsize=(15,14),layout='constrained');colors=['#147d92','#df8f25','#6458a6','#bb4b5a'];ax=axes.flat[0];c=curve(frame);x=c.index.tz_convert(ZONE)
 ax.plot(x,c.known_pnl,color=colors[0],label=f'Known settlement net P&L: ${c.known_pnl.iloc[-1]:,.0f}')
 ax.fill_between(x,c.lower_pnl,c.upper_pnl,color=colors[0],alpha=.16,label='Unknown-settlement outcome bounds')
 ax.plot([],[],color='none',label='Daily Sharpe / variance: N/A (one complete day)')
 ax.set_title('All observed YES-taker prints');ax.legend(loc='upper left',fontsize=8)
 ax2=ax.twinx();ax2.plot(x,c.yes_premium,color=colors[1],alpha=.6,label='YES premium');ax2.plot(x,c.quantity,color=colors[2],alpha=.5,label='Payout face');ax2.set_ylabel('Cumulative volume ($)');ax2.yaxis.set_major_formatter(FuncFormatter(lambda v,p:f'{v/1e6:.0f}m'));ax2.legend(loc='lower right',fontsize=8)
 for ax,(col,title) in zip(list(axes.flat)[1:],[('leg_bucket','Number of legs'),('structure','Shared-game structure'),('family','Market family'),('phase','Entry relative to native scheduled start'),('premium_bucket','Observed print YES premium')]):
  for i,(name,g) in enumerate(frame.groupby(col,sort=True)):
   cg=curve(g);ax.plot(cg.index.tz_convert(ZONE),cg.known_pnl,label=f'{name}: ${cg.known_pnl.iloc[-1]:,.0f} ({len(g):,} prints)',color=colors[i%len(colors)])
  ax.set_title(title);ax.legend(loc='best',fontsize=8)
 for ax in axes.flat:
  ax.axhline(0,color='gray',lw=.7);ax.grid(alpha=.2);ax.set_ylabel('Cumulative known net P&L ($)');ax.yaxis.set_major_formatter(FuncFormatter(lambda v,p:f'{v/1e6:.2f}m'));ax.tick_params(axis='x',rotation=25)
  if scope=='retained_week':
   ax.axvspan(pd.Timestamp('2026-09-05',tz=ZONE),pd.Timestamp('2026-09-06',tz=ZONE),color='gray',alpha=.08)
 title='MLB seller benchmark — September 5 complete day' if scope=='census_sep5' else 'MLB seller benchmark — retained Aug 31–Sep 6 observations'
 note='Public-print counterfactual • modeled maker fees • eventual settlement P&L attributed to entry • unlimited exposure diagnostic'
 detail='All other days are sampled 15-second cells at weight one; shaded Sep 5 is the only complete day.' if scope=='retained_week' else 'One complete observed day: daily Sharpe and sample variance unavailable. Unknown outcomes are bounded, not assigned zero.'
 fig.suptitle(title+'\n'+note+'\n'+detail,fontsize=12)
 for ext in ('png','svg'):fig.savefig(out/f'{scope}.{ext}',dpi=160)
 plt.close(fig)

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--cohort',type=Path,default=ROOT/'runs/mlb_historical_20260907/cohort');p.add_argument('--out',type=Path,default=ROOT/'runs/mlb_historical_20260907/universe_report');a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
 path=a.cohort/'universe_trades.jsonl.gz';frame,excluded=load_rows(path);reports={}
 for name,f in [('census_sep5',frame[frame.sampling_method=='census']),('retained_week',frame)]:
  if name=='census_sep5' and set(f.day)!={'2026-09-05'}:raise ValueError('Unexpected census dates')
  result=summary(f);result.update(concentration=concentration(f),daily_metrics={'sharpe':None,'variance_dollar_squared':None,'complete_observed_days':1,'reason':'Only September 5 is complete; no daily sample variance or Sharpe exists with one complete day. Sampled days are excluded, never filled with zero.'},cuts={})
  for col in ('leg_bucket','structure','family','phase','premium_bucket'):
   result['cuts'][col]={str(k):summary(g) for k,g in f.groupby(col)}
  reports[name]=result;curve(f).to_csv(a.out/(name+'_curves.csv'));plot_report(f,a.out,name)
 frame.drop(columns=['fixtures']).to_csv(a.out/'seller_ledger.csv.gz',index=False,compression='gzip')
 daily=[]
 for day,g in frame.groupby('day'):daily.append({'date':day,'sampling_method':g.sampling_method.iloc[0],**summary(g)})
 pd.DataFrame(daily).to_csv(a.out/'daily_observed.csv',index=False)
 report={'reports':reports,'NO_taker_prints_excluded':excluded,'source':str(path),'source_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'assumptions':['Observed-price hypothetical maker sales; no fill-rate claim.','Net fees charged using archived cohort exact cash rounding, 0.035 maker rate; no taker rebate assumed.','Known-settlement P&L omits unknown positions; separate bounds include every unknown position and fee.','Volume includes unknown settlements. Face quantity is not winnings.','Pregame designation is native scheduled-time proxy, not proof of versioned actual start.','No fair model or capital/risk selection applied in this universe benchmark.']}
 (a.out/'summary.json').write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps({name:{k:v for k,v in d.items() if k not in ('cuts','concentration')} for name,d in reports.items()},indent=2))
if __name__=='__main__':main()

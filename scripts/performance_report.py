#!/usr/bin/env python3
"""Render comparable run reports without changing pricing, fills or entry rules.

Input: performance_input.json with reporting window, run identity, evaluations
and an explicit fill/settlement ledger. Accept multiple --run arguments.
"""
import argparse,hashlib,json,sys
from pathlib import Path
from datetime import datetime,timezone
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from combos.performance import build_curves
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from zoneinfo import ZoneInfo


def render(runs,out):
 out.mkdir(parents=True,exist_ok=True);all_rows=[];sources=[];reference_rows=[];display_names={}
 for folder in runs:
  path=folder/'performance_input.json';raw=path.read_bytes();data=json.loads(raw)
  label=data['run_id']
  if label in display_names:raise ValueError('duplicate run identity')
  display_names[label]=data.get('display_name',folder.name)
  rows=build_curves(data['evaluations'],data['fills'],data['start_at'],data['end_at'])
  for row in rows:row['run_id']=label
  all_rows.extend(rows)
  if data.get('reference_fills'):
   reference_rows.extend(build_curves([],data['reference_fills'],data['start_at'],data['end_at']))
  sources.append({'run_id':label,'path':str(path.resolve()),'sha256':hashlib.sha256(raw).hexdigest(),
                  'identity':data['identity'],'reference_basis':data.get('reference_basis')})
 frame=pd.DataFrame(all_rows);frame.to_csv(out/'curves.csv',index=False)
 pd.DataFrame(reference_rows).to_csv(out/'reference_curves.csv',index=False)
 colors={'blend':'#84c9be','kalshi':'#73a0c4','pinnacle':'#e7b078','stronger_pinnacle':'#b497d6'}
 names={'blend':'Guarded blend','kalshi':'Kalshi','pinnacle':'Pinnacle','stronger_pinnacle':'Stronger Pinnacle'}
 plt.style.use('dark_background')
 def time_axis(ax):
  ax.xaxis.set_major_locator(mdates.DayLocator(tz=ZoneInfo('America/Chicago')))
  ax.set_xlim(pd.to_datetime(frame['at'].min(),unit='s',utc=True),pd.to_datetime(frame['at'].max(),unit='s',utc=True))
  ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %d\n%H:%M',tz=ZoneInfo('America/Chicago')))
  ax.set_xlabel('Chicago time');ax.grid(alpha=.23)
 def x(g):return pd.to_datetime(g['at'],unit='s',utc=True)
 def save(fig,name):
  fig.tight_layout();fig.savefig(out/(name+'.png'),dpi=170,bbox_inches='tight')
  fig.savefig(out/(name+'.svg'),bbox_inches='tight');plt.close(fig)
 def series_label(run,model):return (display_names[run]+' / ' if len(runs)>1 else '')+names.get(model,model)
 # Compare every model's edge against its observed common-cohort volume.
 fig,axes=plt.subplots(2,1,figsize=(12,8),sharex=True)
 for (run,model),g in frame.groupby(['run_id','model']):
  label=series_label(run,model);color=colors.get(model)
  axes[0].step(x(g),g.point_edge,where='post',label=label,color=color,linestyle=('-', '--', ':', '-.')[list(display_names).index(run)%4])
  axes[1].step(x(g),g.stressed_edge,where='post',label=label,color=color,linestyle=('-', '--', ':', '-.')[list(display_names).index(run)%4])
 axes[0].set_title('Cumulative model edge at observed public prices — before entry filters')
 axes[0].set_ylabel('Net edge at fair point ($)');axes[1].set_ylabel('Net edge at stressed upper ($)')
 for ax in axes:
  ax.axhline(0,color='gray',lw=.6);time_axis(ax);ax.legend(loc='upper left',fontsize=8)
 # One volume pair per run, deduplicated across its model comparisons.
 right=axes[0].twinx()
 for run,g in frame.groupby('run_id'):
  g=g[g.model==sorted(g.model.unique())[0]]
  right.step(x(g),g.observed_yes_premium,where='post',color='#527ba0',linestyle='--',label=(display_names[run]+' ' if len(runs)>1 else '')+'Observed YES premium')
  right.step(x(g),g.observed_payout_notional,where='post',color='#d6a267',linestyle=':',label=(display_names[run]+' ' if len(runs)>1 else '')+'Observed payout notional')
 right.set_ylabel('Cumulative observed volume ($)');right.legend(loc='lower right',fontsize=8)
 fig.suptitle('Historical pricing diagnostics — imputed inputs; expected edge is not realized P&L',fontsize=11)
 save(fig,'model_edge_and_volume')
 # Strategy accounting uses explicit fills only; evaluations cannot move P&L.
 fig,axes=plt.subplots(2,1,figsize=(12,7),sharex=True)
 total_fills=0
 for (run,model),g in frame.groupby(['run_id','model']):
  label=series_label(run,model);color=colors.get(model);total_fills+=int(g.fills.iloc[-1])
  axes[0].step(x(g),g.realized_pnl,where='post',label=label,color=color)
  axes[1].step(x(g),g.filled_yes_premium,where='post',label=label+' YES premium',color=color)
  axes[1].step(x(g),g.filled_payout_notional,where='post',label=label+' payout notional',color=color,linestyle=':')
 axes[0].set_ylabel('Cumulative settled P&L ($)');axes[1].set_ylabel('Cumulative filled volume ($)')
 axes[0].set_title(('Simulated' if all(s['identity'].get('historical_only') for s in sources) else 'Recorded')+' strategy fills and settlements — '+str(total_fills)+' recorded fills across model ledgers')
 if total_fills==0:axes[0].text(.5,.7,'No sampled trades cleared the entry criteria; no fills or realized P&L',transform=axes[0].transAxes,ha='center',fontsize=10)
 for ax in axes:time_axis(ax);ax.legend(fontsize=7,loc='upper left',ncol=2)
 save(fig,'strategy_performance')
 if reference_rows and len(runs)==1:
  g=pd.DataFrame(reference_rows);fig,ax=plt.subplots(figsize=(12,5));right=ax.twinx()
  ax.step(x(g),g.realized_pnl,where='post',color='#84c9be',label='Settled P&L — assumed fills')
  right.step(x(g),g.filled_yes_premium,where='post',color='#73a0c4',label='Customer YES premium')
  right.step(x(g),g.filled_payout_notional,where='post',color='#e7b078',label='Payout notional')
  ax.set_title('Unfiltered public-print reference — every matched YES-taker print assumed filled\nNo entry, risk or capital filters; not strategy performance',fontsize=11)
  ax.set_ylabel('Cumulative hypothetical settled P&L ($)');right.set_ylabel('Cumulative reference volume ($)')
  handles,labs=ax.get_legend_handles_labels();h,l=right.get_legend_handles_labels();ax.legend(handles+h,labs+l,loc='upper left',fontsize=9)
  time_axis(ax);save(fig,'unfiltered_reference')
 endings=frame.sort_values('at').groupby(['run_id','model']).tail(1).to_dict('records')
 report={'sources':sources,'endings':endings,'generated_at':datetime.now(timezone.utc).isoformat(),
  'accounting':'maker buys NO; cash spent=q*(1-YES price)+fee; settled PnL=q*(YES price-YES settlement)-fee; fees counted once',
  'volume_units':'YES premium and maker cash spent are separate dollar flows; payout notional is quantity*$1, not winnings',
  'unfiltered_reference':'separate ledger, excluded from strategy results',
  'code_sha256':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),Path(__file__).resolve().parents[1]/'src/combos/performance.py']}}
 (out/'manifest.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
 print(json.dumps({'out':str(out),'runs':len(runs),'models':len(endings),'fills_across_ledgers':total_fills}))


def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',action='append',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
 a=p.parse_args();render(a.run,a.out)
if __name__=='__main__':main()

#!/usr/bin/env python3
"""Plot completed native NFL curves without repricing or filtering any print."""
import argparse
from array import array
from datetime import datetime
from decimal import Decimal
import hashlib,json
from pathlib import Path
from statistics import variance
from zoneinfo import ZoneInfo
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.ticker import FuncFormatter
from replay_artifact_io import text_reader

RATES=('0','0.0175','0.035','0.07')
TZ=ZoneInfo('America/Chicago')
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def plot(run,out):
 run=Path(run);out=Path(out)
 if out.exists():raise FileExistsError('Use a new plots directory')
 complete=json.loads((run/'complete.json').read_text());s=json.loads((run/'summary.json').read_text())
 hashes={}
 for name in ('summary.json','full_resolution_curves.jsonl.zst'):
  hashes[str(run/name)]=sha(run/name)
  assert hashes[str(run/name)]==complete['artifacts'][name]['sha256']
 assert s['sport']=='NFL'
 times=array('d',[s['start_at']]);ys={r:array('d',[0]) for r in RATES};premium=array('d',[0]);face=array('d',[0]);daily={};last=None;count=0
 with text_reader(run/'full_resolution_curves.jsonl.zst') as f:
  for line in f:
   row=json.loads(line);at=row['at'];assert s['start_at']<=at<s['end_at'] and at>=times[-1]
   scenarios={**row['fee_sensitivity'],s['base_maker_rate']:row};times.append(at)
   for r in RATES:ys[r].append(scenarios[r]['known_net_pnl'])
   premium.append(row['yes_premium']);face.append(row['payout_notional'])
   daily[datetime.fromtimestamp(at,TZ).date().isoformat()]={r:Decimal(scenarios[r]['exact_decimal']['known_net_pnl']) for r in RATES}
   last=scenarios;count+=1
 assert count==s['curve_rows']==complete['curve_rows']
 for r in RATES:
  for key in ('known_net_pnl','yes_premium','payout_notional','maker_fees'):
   assert Decimal(last[r]['exact_decimal'][key])==Decimal(s['totals'][r]['exact_decimal'][key]),(r,key)
  assert last[r]['prints']==s['totals'][r]['prints']
 previous={r:Decimal(0) for r in RATES};increments={r:[] for r in RATES}
 for day in s['observed_dates']:
  current=daily.get(day,previous)
  for r in RATES:
   delta=current[r]-previous[r];assert delta==Decimal(s['daily'][day][r]['exact_decimal']['known_net_pnl'])
   increments[r].append(float(delta))
  previous=current
 stats={r:{'daily_pnl_sample_variance_usd_squared':variance(increments[r]) if len(increments[r])>1 else None,'observed_days':len(increments[r]),'sharpe':None,'sharpe_reason':'Unlimited exposure and few shared fixtures; no defensible capital-return series'} for r in RATES}
 out.mkdir(parents=True)
 dates=mdates.epoch2num(times) if hasattr(mdates,'epoch2num') else [mdates.date2num(datetime.fromtimestamp(t,TZ)) for t in times]
 fig,(ax,vol)=plt.subplots(2,1,figsize=(13,9),sharex=True,gridspec_kw={'height_ratios':[2,1]})
 colors=['#0072B2','#009E73','#D55E00','#CC79A7']
 for rate,color in zip(RATES,colors):
  v=stats[rate]['daily_pnl_sample_variance_usd_squared'];label=f"c={rate} | final ${ys[rate][-1]:,.0f} | daily var {v:.2e} USD² | Sharpe N/A"
  ax.step(dates,ys[rate],where='post',color=color,lw=1.2,label=label)
 ax.axhline(0,color='0.5',lw=.7);ax.set_ylabel('Cumulative realized net P&L (USD)');ax.legend(loc='lower left',fontsize=9,framealpha=.94)
 ax.yaxis.set_major_formatter(FuncFormatter(lambda x,pos:f'${x/1000:,.0f}k'))
 vol.step(dates,premium,where='post',color='#0072B2',label=f'YES premium: ${premium[-1]/1e6:.2f}m')
 vol.step(dates,face,where='post',color='#D55E00',label=f'Payout face notional: ${face[-1]/1e6:.2f}m')
 vol.set_ylabel('Cumulative volume (USD)');vol.yaxis.set_major_formatter(FuncFormatter(lambda x,pos:f'${x/1e6:,.0f}m'));vol.legend(loc='upper left',fontsize=10)
 vol.xaxis.set_major_locator(mdates.DayLocator(tz=TZ));vol.xaxis.set_major_formatter(mdates.DateFormatter('%b %d',tz=TZ));vol.set_xlabel('Trade time • America/Chicago')
 for a in (ax,vol):a.grid(alpha=.22);a.spines[['top','right']].set_visible(False)
 fig.suptitle(f"NFL native combos • {s['observed_dates'][0]} to {s['observed_dates'][-1]}\nSell all {s['totals'][s['base_maker_rate']]['prints']:,} YES-taker prints at public price and size",fontsize=15)
 fig.text(.07,.045,'All pure-NFL families, leg counts and phases; unlimited capital/exposure. Public-print counterfactual, not RFQ fills.\nEventual settlement P&L attributed to trade; January maker-fee coefficients unverified. Face notional is not customer winnings.\nDaily sample variance uses only certified observed Chicago dates (ddof=1); shared fixtures limit independent evidence.',fontsize=9)
 fig.subplots_adjust(left=.10,right=.97,top=.88,bottom=.17,hspace=.12)
 artifacts={}
 for ext in ('png','svg'):
  p=out/f'native_universe.{ext}';fig.savefig(p,dpi=160);artifacts[p.name]=sha(p)
 plt.close(fig)
 proof={'status':'verified','curve_rows':count,'endpoint_checks':'Exact Decimal P&L, premium, face, fees and print counts vs summary; daily increments vs summary','statistics':stats,'input_hashes':{**hashes,str(run/'complete.json'):sha(run/'complete.json')},'source_hashes':{str(Path(__file__)):sha(__file__),str(Path(__file__).with_name('replay_artifact_io.py')):sha(Path(__file__).with_name('replay_artifact_io.py'))},'upstream_source_hashes':s['source_hashes'],'output_hashes':artifacts,'display':'All curve timestamps retained; matplotlib rendering may simplify paths; no repricing'}
 (out/'verification.json').write_text(json.dumps(proof,indent=2)+'\n')
 return proof
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',required=True,type=Path);p.add_argument('--out',required=True,type=Path);a=p.parse_args();plot(a.run,a.out)

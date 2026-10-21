#!/usr/bin/env python3
"""Same-cohort historical fair pilot; imputation scenarios, never inferred RFQ fills."""
import argparse,bisect,gzip,hashlib,json,math,sys
from collections import Counter,defaultdict
from dataclasses import asdict
from decimal import Decimal
from pathlib import Path
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from combos.matching import norm
from combos.football_identity import provider_team_key
from combos.historical_fair import History,timestamp,historical_observations,compare_fairs
from combos.pricing import Interval,short_yes_economics
from combos.joint_pricing import price_joint
from combos.replay import complement
from combos.event_store import EventStore
from combos.risk import RiskLedger
DATA=ROOT/'runs/cfb_fair_pilot_20260907'
OUT=DATA


def gz(path):
 with gzip.open(path,'rt') as f:return json.load(f)


def canonical(fixture,kind,team,line):
 teams=sorted(provider_team_key(fixture,i) for i in (1,2))
 prefix=fixture['fixtureId']+':'+kind+':'
 if kind=='moneyline':return prefix+teams[0]
 if kind=='totals':return prefix+str(line)
 return prefix+teams[0]+':'+str(line if team==teams[0] else -line)


class Pilot:
 def __init__(self,settings,mapping_path=None,allow_unsettled=False):
  self.settings=settings
  self.maps={};self.exclusions=[];self.cache={}
  pmmap=json.load(open(mapping_path or ROOT/'data/derived/polymarket_mapping.json'))
  catalog={str(x['marketId']):x for x in json.load(open(ROOT/'runs/oddspapi_freshness_20260907/football_market_catalog.json'))}
  for selected in json.load(open(DATA/'selection.json'))['selected']:
   fixture=selected['fixture'];fid=fixture['fixtureId'];path=DATA/'history'/f'{fid}.json.gz'
   if not path.exists():
    self.exclusions.append({'fixture_id':fid,'reason':'missing_pinnacle_fixture_history'});continue
   if fixture['statusId']!=2 and not allow_unsettled:continue
   book=gz(path)['payload'].get('bookmakers',{}).get('pinnacle+30',{}).get('markets',{})
   pairs={};home,away=(provider_team_key(fixture,i) for i in (1,2))
   for mid,market in book.items():
    d=catalog.get(mid,{})
    if d.get('playerProp') is not False or d.get('period')!='result' or d.get('marketType') not in ('moneyline','spreads','totals'):continue
    typ=d['marketType'];line=Decimal(str(d['handicap']))
    if typ!='moneyline' and abs(line)%1!=Decimal('.5'):continue
    names={o['outcomeName']:str(o['outcomeId']) for o in d['outcomes']}
    labels=('Over','Under') if typ=='totals' else ('1','2')
    if set(names)!=set(labels):continue
    try:histories=[History(market['outcomes'][names[label]]['players']['0'],'createdAt') for label in labels]
    except (KeyError,ValueError) as exc:
     self.exclusions.append({'fixture_id':fid,'native_market_id':mid,'reason':str(exc)});continue
    for i,label in enumerate(labels):
     if typ=='totals' and i==1:continue
     team='over' if typ=='totals' else home if i==0 else away
     threshold=None if typ=='moneyline' else line if typ=='totals' or i==1 else -line
     key=(typ,team,threshold)
     if key in pairs:raise ValueError('ambiguous native payoff')
     pairs[key]=(histories[i],histories[1-i],mid,names[label])
   for ticker in selected['kalshi_tickers']:
    try:
     k=gz(ROOT/'data/raw/legs'/f'{ticker}.json.gz')['payload']['market'];pm=pmmap[ticker]
     kind={'KXNCAAFGAME':'moneyline','KXNCAAFSPREAD':'spreads','KXNCAAFTOTAL':'totals'}[ticker.split('-')[0]]
     team='over' if kind=='totals' else norm(k['yes_sub_title'].split(' wins by ')[0])
     line=None if kind=='moneyline' else Decimal(str(k['floor_strike']))
     yes,no,mid,oid=pairs[(kind,team,line)]
     settled_binary=k.get('result') in ('yes','no') and k.get('settlement_value_dollars') in ('0.0000','1.0000')
     if not settled_binary and not allow_unsettled:raise ValueError('nonbinary_or_unsettled')
     rows=[]
     history_end=min(timestamp(fixture['startTime']),timestamp('2026-09-07T05:00:00Z')) if allow_unsettled else timestamp(fixture['startTime'])
     expected_parts=[DATA/'kalshi_parts'/(ticker+'.part'+str(i)+'.json.gz') for i,_ in enumerate(range(int(timestamp('2026-08-31T05:00:00Z')),int(history_end),3*86400))]
     if not all(p.exists() for p in expected_parts):raise ValueError('incomplete_candle_capture')
     for part in expected_parts:
      r=gz(part)
      if r['status']!=200:raise ValueError('failed_candle_capture')
      rows.extend(r['payload']['candlesticks'])
     # Boundary sentinel candles can omit quotes; a valid completed close at
     # the same timestamp takes precedence over a quote-less sentinel.
     dedup={}
     for r in rows:
      t=r['end_period_ts'];valid=all(r.get(s,{}).get('close_dollars') is not None for s in ('yes_bid','yes_ask'))
      if valid and t in dedup and all(dedup[t].get(side,{}).get('close_dollars') is not None for side in ('yes_bid','yes_ask')):
       if any(dedup[t][side]['close_dollars']!=r[side]['close_dollars'] for side in ('yes_bid','yes_ask')):raise ValueError('conflicting_candle_close')
      if valid or t not in dedup:dedup[t]=r
     candle_rows=list(dedup.values())
     if allow_unsettled:
      candle_rows=[{key:r[key] for key in ('end_period_ts','yes_bid','yes_ask','yes_bid_size','yes_ask_size') if key in r} for r in candle_rows]
     kh=History(candle_rows,'end_period_ts');praw=gz(DATA/'polymarket'/f'{pm["token"]}.json.gz')
     if praw['status']!=200:raise ValueError('failed_PM_capture')
     ph=History(praw['payload']['history'],'t')
     self.maps[ticker]={'fixture':fixture,'kind':kind,'team':team,'line':line,'kalshi':kh,'pm':ph,
       'pin_yes':yes,'pin_no':no,'native_market_id':mid,'native_yes_outcome_id':oid,
       'start_at':timestamp(fixture['startTime']),'settlement':float(k['settlement_value_dollars']) if settled_binary else None,
       'risk_key':canonical(fixture,kind,team,line),'pm_fee':pm['fee_schedule']['rate'] if pm.get('fees_enabled') else 0,
       'payoff_basis':'normal_completed_game_only; exceptional terms not interchangeable'}
    except (KeyError,ValueError,TypeError,OSError) as exc:self.exclusions.append({'ticker':ticker,'reason':str(exc)})

 def fair(self,ticker,at,depth=1000.,delay=30.):
  key=(ticker,at,depth,delay)
  if key in self.cache:return self.cache[key]
  m=self.maps[ticker]
  if at>=m['start_at']-60:raise ValueError('pregame_cutoff')
  k=m['kalshi'].latest(at,60);pm=m['pm'].latest(at,60)
  yt,yr=m['pin_yes'].latest(at,delay);nt,nr=m['pin_no'].latest(at,delay)
  records=historical_observations(ticker,k,pm,(yt,yr,nt,nr),at,depth,delay,m['pm_fee'])
  from combos.weighted_fair import WeightPolicy
  policy=WeightPolicy(**self.settings['base_weight_policy'])
  fair,obs=compare_fairs(records,policy=policy);strong,_=compare_fairs(records,True,policy,self.settings['stronger_pinnacle_overrides'])
  models={'kalshi':asdict(obs[0].interval),'pinnacle':asdict(obs[2].interval),
          'blend':fair['fair'],'stronger_pinnacle':strong['fair']}
  ages={'kalshi':at-k[0],'polymarket':at-pm[0],'pinnacle':at-min(yt,nt)}
  result={'models':models,'blend':fair,'stronger':strong,'raw_state_ages':ages,
       'strict_current_age_gate_pass':ages['kalshi']<=15 and ages['polymarket']<=15 and ages['pinnacle']<=90,
       'historical_only':True,'shared_exchange_depth':depth,'extra_archive_delay':delay,
       'references':{'native_market_id':m['native_market_id'],'native_yes_outcome_id':m['native_yes_outcome_id'],
           'payoff_basis':m['payoff_basis'],'raw_state_timestamps':records[0]['freshness_context']}}
  self.cache[key]=result;return result


def score_legs(pilot):
 rows=[];excluded=Counter();audit=[]
 for ticker,m in pilot.maps.items():
  for horizon in (86400,21600,3600,600):
   at=m['start_at']-horizon
   for depth,delay in pilot.settings['depth_delay_scenarios']:
    try:f=pilot.fair(ticker,at,depth,delay)
    except (ValueError,KeyError,TypeError) as exc:excluded[str(exc)]+=1;continue
    if depth==1000 and delay==30:audit.append({'ticker':ticker,'at':at,**f})
    for model,interval in f['models'].items():
     probability=interval['point'];y=m['settlement'];p=min(1-1e-10,max(1e-10,probability))
     row={'ticker':ticker,'fixture_id':m['fixture']['fixtureId'],'risk_key':m['risk_key'],'kind':m['kind'],
          'at':at,'horizon_seconds':horizon,'depth':depth,'delay':delay,'model':model,'probability':probability,
          'outcome':y,'brier':(probability-y)**2,'log_loss':-(y*math.log(p)+(1-y)*math.log(1-p)),
          'quote_allowed':f['stronger' if model=='stronger_pinnacle' else 'blend']['guard']['quote_allowed'],
          **{v+'_raw_age':age for v,age in f['raw_state_ages'].items()},'strict_age_gate':f['strict_current_age_gate_pass']}
     # Independent future exchange midpoint and Pinnacle are diagnostics only.
     for benchmark in ('kalshi','pinnacle'):
      try:
       close=pilot.fair(ticker,m['start_at']-120,depth,delay)['models'][benchmark]['point']
       row['closing_'+benchmark+'_absolute_error']=abs(probability-close)
      except (ValueError,KeyError,TypeError):pass
     rows.append(row)
 frame=pd.DataFrame(rows);frame.to_csv(OUT/'leg_scores.csv',index=False)
 with gzip.open(OUT/'leg_pricing_context.jsonl.gz','wt') as f:
  for row in audit:f.write(json.dumps(row,separators=(',',':'))+'\n')
 # Deduplicate complementary team listings for each canonical payoff/time.
 unique=frame.sort_values('ticker').drop_duplicates(['risk_key','at','depth','delay','model'])
 metrics=['brier','log_loss','closing_kalshi_absolute_error','closing_pinnacle_absolute_error']
 grouped=unique.groupby(['depth','delay','model','fixture_id'])[metrics].mean()
 summary=grouped.groupby(['depth','delay','model']).mean().reset_index()
 summary.to_csv(OUT/'fixture_balanced_scores.csv',index=False)
 base=unique[(unique.depth==1000)&(unique.delay==30)]
 paired=base.groupby(['fixture_id','model']).brier.mean().unstack();rng=np.random.default_rng(20260907)
 intervals={}
 for model in ('pinnacle','blend','stronger_pinnacle'):
  diff=(paired[model]-paired.kalshi).dropna().values
  boot=np.mean(rng.choice(diff,(5000,len(diff)),replace=True),axis=1)
  intervals[model]={'delta_brier_vs_kalshi':float(diff.mean()),'fixture_bootstrap_95':np.quantile(boot,[.025,.975]).tolist(),'fixtures':len(diff)}
 return {'rows':len(frame),'base_distinct_leg_times':len(base[base.model=='kalshi']),
         'fixtures':int(base.fixture_id.nunique()),'mapping_count':len(pilot.maps),'excluded_evaluations':dict(excluded),
         'strict_current_age_gate_pass':int(base[base.model=='kalshi'].strict_age_gate.sum()),
         'fixture_balanced_scores':summary.to_dict('records'),'brier_differences':intervals}


def extract_tape(pilot):
 dest=DATA/'combo_cohort.json.gz'
 if dest.exists():return gz(dest)
 markets={};allowed=set(pilot.maps)
 for path in (ROOT/'data/raw/metadata').glob('*.json.gz'):
  for m in gz(path)['payload']['markets']:
   legs=m.get('mve_selected_legs') or []
   if not 2<=len(legs)<=4 or not all(l.get('market_ticker') in allowed for l in legs):continue
   if len({pilot.maps[l['market_ticker']]['fixture']['fixtureId'] for l in legs})!=len(legs):continue
   markets[m['ticker']]=m
 trades={}
 def ingest(rows,weight):
  for r in rows:
   if r['ticker'] in markets:
    t=timestamp(r['created_time'])
    if t>=min(pilot.maps[l['market_ticker']]['start_at'] for l in markets[r['ticker']]['mve_selected_legs'])-60:continue
    if r['trade_id'] in trades and trades[r['trade_id']]['trade']!=r:raise ValueError('conflicting public print')
    trades[r['trade_id']]={'trade':r,'sampling_weight':weight}
 for path in (ROOT/'data/derived/tape').glob('hour_*.json.gz'):ingest(gz(path)['combos'],1.)
 for path in (ROOT/'data/raw/cfb_week_20260831').glob('*/complete.json'):ingest(json.load(open(path))['combos'],60.)
 result={'markets':markets,'trades':sorted(trades.values(),key=lambda x:(x['trade']['created_time'],x['trade']['trade_id']))}
 with gzip.open(dest,'wt') as f:json.dump(result,f,separators=(',',':'))
 return result


def score_combos(pilot):
 tape=extract_tape(pilot);rows=[];exclusions=Counter()
 policy=pilot.settings['risk_limits'];ledgers={};stores={}
 for model in ('kalshi','pinnacle','blend','stronger_pinnacle'):
  path=OUT/(model+'_allocation.sqlite')
  if path.exists():path.unlink()
  store=EventStore(path);stores[model]=store;ledgers[model]=RiskLedger(store,policy)
 for item in tape['trades']:
  trade=item['trade'];at=timestamp(trade['created_time']);market=tape['markets'][trade['ticker']];legs=market['mve_selected_legs']
  if trade.get('taker_outcome_side',trade.get('taker_side'))!='yes':exclusions['no_taker']+=1;continue
  if any(l.get('yes_settlement_value_dollars') not in (None,'') for l in legs):exclusions['settled_leg']+=1;continue
  price=float(trade['yes_price_dollars']);quantity=float(trade['count_fp'])
  if not 0<price<1:continue
  try:fair=[pilot.fair(l['market_ticker'],at) for l in legs]
  except (ValueError,KeyError,TypeError) as exc:exclusions[str(exc)]+=1;continue
  # Known fee-series boundaries only; assumptions match retained week study.
  if market['event_ticker'].startswith('KXMVECROSSCATEGORY-SHARD1-'):rate=.035
  elif market['event_ticker'].startswith('KXMVECROSSCATEGORY0-SHARD1-'):rate=0.
  else:exclusions['unreviewed_combo_fee_series']+=1;continue
  fixtures=[pilot.maps[l['market_ticker']]['fixture']['fixtureId'] for l in legs]
  contracts=[pilot.maps[l['market_ticker']]['risk_key'] for l in legs]
  for model in ledgers:
   intervals=[complement(Interval(**f['models'][model]),l['side']) for f,l in zip(fair,legs)]
   try:joint=price_joint(intervals,pilot.settings['correlation_rho'])
   except ValueError:exclusions['joint_failure']+=1;continue
   economics=short_yes_economics(quantity,price,joint['stressed_upper'],rate)
   guard_key='stronger' if model=='stronger_pinnacle' else 'blend'
   allowed=all(f[guard_key]['guard']['quote_allowed'] for f in fair) if model in ('blend','stronger_pinnacle') else True
   multiplier=min(f[guard_key]['guard']['risk_multiplier'] for f in fair) if model in ('blend','stronger_pinnacle') else 1.
   reason='insufficient_edge';allocated=False
   if not allowed:reason='venue_disagreement_hard'
   elif economics['expected_edge']>=quantity*pilot.settings['minimum_net_edge_per_share']:
    with stores[model].transaction():
     risk=ledgers[model].reserve(trade['trade_id'],'historical_creator_unknown',economics['maximum_loss'],
       {'contract':contracts,'combo':[trade['ticker']],'fixture':fixtures},at+3,
       {'quantity':quantity,'yes_price':price,'scenario':'sampled_public_print_assumed_fill_no_capital_recycling'},multiplier)
     reason=risk.get('reason','allocated');allocated=risk['allowed']
     if allocated:ledgers[model].transition(trade['trade_id'],'simulated_filled',at,0)
   rows.append({'trade_id':trade['trade_id'],'at':at,'model':model,'legs':len(legs),'sampling_weight':item['sampling_weight'],
       'yes_price':price,'quantity':quantity,'yes_premium':price*quantity,'fair_point':joint['joint']['point'],
       'stressed_upper':joint['stressed_upper'],'edge_at_point':quantity*(price-joint['joint']['point'])-economics['maker_fee'],
       'stressed_edge':economics['expected_edge'],'maximum_loss':economics['maximum_loss'],'quote_allowed':allowed,
       'allocation_reason':reason,'allocated':allocated,'risk_multiplier':multiplier})
 for store in stores.values():store.close()
 frame=pd.DataFrame(rows);frame.to_csv(OUT/'combo_comparisons.csv',index=False)
 summary=[]
 if len(frame):
  for model,g in frame.groupby('model'):
   a=g[g.allocated]
   summary.append({'model':model,'observed_priced_prints':len(g),'yes_premium':float(g.yes_premium.sum()),'payout_notional':float(g.quantity.sum()),
      'stressed_edge_all_prints':float(g.stressed_edge.sum()),'positive_stressed_edge_prints':int((g.stressed_edge>=g.quantity*pilot.settings['minimum_net_edge_per_share']).sum()),
      'allocated_prints':len(a),'allocated_premium':float(a.yes_premium.sum()),'allocated_notional':float(a.quantity.sum()),
      'allocated_expected_stressed_edge':float(a.stressed_edge.sum()),'committed_maximum_loss':float(a.maximum_loss.sum()),
      'allocation_reasons':dict(Counter(g.allocation_reason))})
 return {'cohort_markets':len(tape['markets']),'cohort_pregame_public_prints':len(tape['trades']),
         'exclusions':dict(exclusions),'models':summary,'allocation_basis':'observed sample only; assumed whole-print fills; no capital recycling or extrapolated risk path; no creator simulation'}


def plot_results():
 import matplotlib;matplotlib.use('Agg')
 import matplotlib.pyplot as plt
 scores=pd.read_csv(OUT/'fixture_balanced_scores.csv');base=scores[(scores.depth==1000)&(scores.delay==30)]
 labels={'kalshi':'Kalshi','pinnacle':'Pinnacle','blend':'Guarded blend','stronger_pinnacle':'Stronger Pinnacle'}
 colors={'kalshi':'#6c7a89','pinnacle':'#d98032','blend':'#1c8c86','stronger_pinnacle':'#5659a9'}
 report=json.load(open(OUT/'summary.json'))
 fig,axes=plt.subplots(1,2,figsize=(12.5,4.8))
 for i,model in enumerate(('pinnacle','blend','stronger_pinnacle')):
  d=report['legs']['brier_differences'][model];v=d['delta_brier_vs_kalshi'];lo,hi=d['fixture_bootstrap_95']
  axes[0].errorbar(v,i,xerr=[[v-lo],[hi-v]],fmt='o',capsize=5,color=colors[model])
 axes[0].set_yticks(range(3),[labels[m] for m in ('pinnacle','blend','stronger_pinnacle')])
 axes[0].axvline(0,color='gray',lw=1);axes[0].set_xlabel('Brier difference vs Kalshi (negative is better)')
 axes[0].set_title('17 games; fixture bootstrap 95% intervals')
 for model,g in scores[scores.delay==30].groupby('model'):
  axes[1].plot(g.depth,g.brier,'o-',label=labels[model],color=colors[model])
 axes[1].set_xscale('log');axes[1].set_xlabel('Assumed equal exchange depth ($ payout)');axes[1].set_ylabel('Fixture-balanced Brier score')
 axes[1].legend(fontsize=8,loc='upper center',bbox_to_anchor=(.5,-.17),ncol=2)
 axes[1].set_title('Zoomed depth sensitivity; lower is better')
 fig.suptitle('CFB historical pricing pilot — imputed depth and spread; no live fill claims')
 fig.tight_layout();fig.savefig(OUT/'fair_validation.png',dpi=170);plt.close(fig)
 frame=pd.read_csv(OUT/'combo_comparisons.csv')
 if len(frame):
  fig,ax=plt.subplots(figsize=(11,4.5))
  for model,g in frame.groupby('model'):
   g=g.sort_values('at');ax.plot(pd.to_datetime(g['at'],unit='s',utc=True).dt.tz_convert('America/Chicago'),g.stressed_edge.cumsum(),label=labels[model])
  ax.set_ylabel('Cumulative signed stressed edge on common observed prints ($)');ax.set_xlabel('Chicago time');ax.legend();ax.axhline(0,color='gray',lw=.6)
  ax.set_title('Price comparison at public trades — no fill or deployable-opportunity inference')
  fig.autofmt_xdate();fig.tight_layout();fig.savefig(OUT/'combo_edge_comparison.png',dpi=170);plt.close(fig)


def write_performance_input(report,pilot):
 tape=extract_tape(pilot);trades={x['trade']['trade_id']:x['trade'] for x in tape['trades']}
 frame=pd.read_csv(OUT/'combo_comparisons.csv');evaluations=[];fills=[];reference=[]
 for row in frame.to_dict('records'):
  evaluations.append({'model':row['model'],'evaluation_id':row['trade_id'],'at':row['at'],'quantity':row['quantity'],
   'yes_price':row['yes_price'],'point_edge':row['edge_at_point'],'stressed_edge':row['stressed_edge']})
  market=tape['markets'][trades[row['trade_id']]['ticker']]
  rate=.035 if market['event_ticker'].startswith('KXMVECROSSCATEGORY-SHARD1-') else 0.
  fee=short_yes_economics(row['quantity'],row['yes_price'],0,rate)['maker_fee']
  settled=timestamp(market['settlement_ts']) if market.get('settlement_ts') else None
  fill={'model':row['model'],'fill_id':row['trade_id'],'filled_at':row['at'],'quantity':row['quantity'],
   'yes_price':row['yes_price'],'maker_fee':fee,'settled_at':settled,
   'yes_settlement':float(market['settlement_value_dollars']) if settled else None,'basis':'simulated_execution'}
  if row['allocated']:fills.append(fill)
  if row['model']=='blend':reference.append({**fill,'model':'unfiltered_public_print_reference','basis':'unfiltered_public_print_reference'})
 identity={'configuration':pilot.settings,'code_sha256':report['code_sha256'],'historical_only':True,
  'data_run':str(DATA.resolve()),'input_files':{}}
 paths=[DATA/'selection.json',DATA/'acquisition.json',DATA/'combo_cohort.json.gz',
        ROOT/'data/derived/polymarket_mapping.json',ROOT/'runs/oddspapi_freshness_20260907/football_market_catalog.json']
 paths.extend(ROOT/'data/raw/legs'/(ticker+'.json.gz') for ticker in sorted(pilot.maps))
 paths.extend(p for folder in ('history','kalshi_parts','polymarket') for p in sorted((DATA/folder).glob('*.gz')))
 for p in paths:identity['input_files'][str(p.resolve())]=hashlib.sha256(p.read_bytes()).hexdigest()
 raw=json.dumps(identity,sort_keys=True,separators=(',',':')).encode();run_id=OUT.name+':'+hashlib.sha256(raw).hexdigest()[:10]
 payload={'schema_version':1,'run_id':run_id,'display_name':pilot.settings.get('experiment_label',OUT.name),'identity':identity,'start_at':timestamp('2026-08-31T05:00:00Z'),
  'end_at':timestamp('2026-09-07T05:00:00Z'),'evaluations':evaluations,'fills':fills,'reference_fills':reference,
  'reference_basis':'Assume every common-cohort observed YES-taker print filled, without entry/risk/capital filters. Not strategy performance.'}
 (OUT/'performance_input.json').write_text(json.dumps(payload,indent=2,allow_nan=False)+'\n')


def main():
 global OUT,DATA
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--config',type=Path,default=ROOT/'config/cfb_fair_pilot.json')
 parser.add_argument('--data-run',type=Path,default=DATA);parser.add_argument('--out',type=Path,default=OUT)
 args=parser.parse_args();OUT=args.out;DATA=args.data_run;OUT.mkdir(parents=True,exist_ok=True)
 settings=json.load(open(args.config));(OUT/'experiment_config.json').write_text(json.dumps(settings,indent=2)+'\n')
 pilot=Pilot(settings);print('exact native mappings',len(pilot.maps),'excluded',len(pilot.exclusions),flush=True)
 report={'historical_only':True,'depth_assumption':'PM equals Kalshi; both absent in candles, shared 100/1000/10000 payout-depth scenarios',
 'spread_assumption':'PM historical price centered in contemporaneous Kalshi raw spread, symmetrically clipped at bounds; venue fees remain separate',
 'age_assumption':'state history carried until next update/inactive; last-change age retained; 30s extra archive delay and 60s exchange publication allowance; not verified live freshness',
 'scope':'20 preselected September 5 CFB fixtures, pregame prices across August 31–September 6; full-game exact payoff subset',
 'configuration':settings,'mapping_exclusions':pilot.exclusions,'legs':score_legs(pilot)}
 print('leg scoring complete',report['legs']['fixtures'],flush=True)
 report['combos']=score_combos(pilot)
 report['code_sha256']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),ROOT/'src/combos/historical_fair.py',ROOT/'src/combos/weighted_fair.py',ROOT/'src/combos/joint_pricing.py']}
 (OUT/'summary.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n');plot_results();write_performance_input(report,pilot)
 print(json.dumps({'legs':report['legs']['brier_differences'],'combos':report['combos']},indent=2))
if __name__=='__main__':main()

#!/usr/bin/env python3
"""Delay archived source information while preserving actual trade/fee clocks."""
import argparse,gzip,hashlib,json,math,sys
from collections import Counter,defaultdict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from mlb_model_replay import SourceFairs,selected,joint
from mlb_historical_fees import load_fee_scenario
from combos.historical_fair import History
from combos.backtest import BacktestConfig,run_backtest

LAGS=(0,30,60,120);MODELS=('kalshi','polymarket','exchange_blend_equal','exchange_blend_pm75')
def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def loadgz(p):
 with gzip.open(p,'rt') as f:return json.load(f)
def dump(p,v):
 p.parent.mkdir(parents=True,exist_ok=True)
 if p.suffix=='.gz':
  with gzip.open(p,'wt') as f:json.dump(v,f,separators=(',',':'),allow_nan=False)
 else:p.write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')

class DelayedHistory:
 def __init__(self,history,params,extra):self.history=history;self.params=params;self.extra=extra
 def latest(self,at,delay=0):
  cutoff=at-delay-self.extra
  if not self.params['startTs']<=cutoff<=self.params['endTs']:raise ValueError('uncovered_extra_lag_PM_timestamp')
  return self.history.latest(at,delay+self.extra)

class TimingSourceFairs(SourceFairs):
 def __init__(self,exchange,fee_scenario,extra):
  if extra not in LAGS:raise ValueError('fixed timing grid only')
  super().__init__(exchange,fee_scenario=fee_scenario)
  self.extra=extra;self.kalshi.publication_delay+=extra
  for ticker,m in self.maps.items():
   if m.get('status')!='matched':continue
   path=exchange/'polymarket'/(m['token']+'.json.gz')
   if not path.exists():continue
   env=loadgz(path)
   if env.get('status')!=200:continue
   params=env['params'];self.pm[ticker]=(DelayedHistory(History(env['payload']['history'],'t'),params,extra),params)
 def timed_fair(self,ticker,at):
  available,ctx,errors=self.fair(ticker,at)
  if 'polymarket' in ctx:
   # SourceFairs retains the baseline60s availability label; annotate the
   # actual additional experimental information delay without moving at.
   ctx['polymarket']={**ctx['polymarket'],'available_at':ctx['polymarket']['state_at']+60+self.extra,'extra_information_delay_seconds':self.extra}
  for venue in ('kalshi','polymarket'):
   if venue in ctx and ctx[venue]['available_at']>at:raise ValueError('timing adapter introduced lookahead')
  return available,ctx,errors

def replacement(base,model,leg_values):
 intervals=tuple(selected(v[0][model][0],leg['side']) for v,leg in leg_values)
 result=joint(intervals)
 return {**base,'model':model,'fair_point':result['joint']['point'],'stressed_upper':result['stressed_upper'],
  'quote_allowed':all(v[0][model][1] for v,leg in leg_values),'risk_multiplier':min(v[0][model][2] for v,leg in leg_values)}

def build_day(day,out):
 data=json.loads((day/'replay/opportunities.json').read_text());coverage=json.loads((day/'replay/coverage.json').read_text())
 for path,h in data['identity']['input_sha256'].items():
  if digest(path)!=h:raise ValueError('frozen baseline input hash mismatch')
 baseline={ (r['model'],r['evaluation_id']):r for r in data['opportunities'] if r['model'] in MODELS}
 primary=[r for r in data['opportunities'] if r['model']=='kalshi']
 if len(primary)>coverage['eligible_prints']:raise ValueError('priced cohort exceeds eligible universe')
 data['timing_universe']={'baseline_eligible_prints':coverage['eligible_prints'],'baseline_K_priced_prints':len(primary),'inherited_unpriced_K_prints':coverage['eligible_prints']-len(primary),'inherited_baseline_pricing_exclusions':coverage['pricing_exclusions'],'scope':'Sensitivity on every baseline K-priced print; inherited missing baseline K states are excluded, not repaired by lag. PM/fixed models require K in baseline.'}
 markets=loadgz(day/'cohort/combo_markets.json.gz');fees=load_fee_scenario(ROOT/'runs/mlb_historical_20260907/fee_scenarios'/(day.name+'.json'))
 all_rows={};counts={};parity=None
 for lag in LAGS:
  provider=TimingSourceFairs(day/'exchange',fees,lag);rows=[];missing=defaultdict(Counter)
  with gzip.open(out/f'context_extra{lag}.jsonl.gz','wt') as handle:
   for base in primary:
    legs=markets[base['source']['combo_ticker']]['mve_selected_legs'];fairs=[provider.timed_fair(l['market_ticker'],base['at']) for l in legs]
    for model in MODELS:
     errors=[v[2].get(model,'source_unavailable') for v in fairs if model not in v[0]]
     if errors:missing[model].update(errors);continue
     row=replacement(base,model,list(zip(fairs,legs)));rows.append(row)
    handle.write(json.dumps({'evaluation_id':base['evaluation_id'],'actual_trade_at':base['at'],'extra_source_delay_seconds':lag,'sources':[v[1] for v in fairs]},separators=(',',':'))+'\n')
  by={(r['model'],r['evaluation_id']):r for r in rows}
  if lag==0:
   if set(by)!=set(baseline):raise ValueError('zero lag coverage differs from baseline')
   for key,row in by.items():
    original=baseline[key]
    for field in ('fair_point','stressed_upper','at','maker_fee','quantity','yes_price','settled_at','yes_settlement','buckets','quote_allowed','risk_multiplier','source'):
     if row[field]!=original[field]:raise ValueError('zero lag parity failed '+field)
   parity={'model_rows':len(by),'all_fields_exactly_equal':True}
  counts[lag]={'model_rows':dict(Counter(r['model'] for r in rows)),'missing_leg_reasons':{k:dict(v) for k,v in missing.items()}}
  all_rows[lag]=rows
  dump(out/f'opportunities_extra{lag}.json', {**{k:v for k,v in data.items() if k!='opportunities'},'opportunities':rows,'extra_source_delay_seconds':lag,'actual_trade_and_fee_clocks_unchanged':True})
  print(json.dumps({'date':day.name,'lag':lag,'rows':len(rows)}),flush=True)
 return data,all_rows,counts,parity

def threshold(row):return row['quote_allowed'] and row['quantity']*(row['yes_price']-row['fair_point'])-row['maker_fee']>=row['quantity']*.003

def main():
 p=argparse.ArgumentParser();p.add_argument('--day',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
 code_files=[Path(__file__),ROOT/'scripts/mlb_model_replay.py',ROOT/'scripts/mlb_historical_fees.py',ROOT/'src/combos/kalshi_history.py',ROOT/'src/combos/historical_fair.py',ROOT/'src/combos/backtest.py',ROOT/'src/combos/joint_pricing.py']
 hashes={str(f):digest(f) for f in code_files};data,rows,coverage,parity=build_day(a.day,a.out)
 keysets=[{r['evaluation_id'] for r in rows[lag] if r['model']==model} for lag in LAGS for model in MODELS]
 common=set.intersection(*keysets);result={};drift={};baseline={(r['model'],r['evaluation_id']):r for r in rows[0]}
 for lag in LAGS:
  for cohort in ('available','all_models_all_lags_common'):
   subset=rows[lag] if cohort=='available' else [r for r in rows[lag] if r['evaluation_id'] in common]
   for constrained in (True,False):
    name=f'extra{lag}_{cohort}_'+('funded' if constrained else 'unlimited')
    output=run_backtest(subset,data['start_at'],data['end_at'],BacktestConfig(entry_basis='point'),constrained)
    dump(a.out/(name+'.json.gz'),output);result[name]=output['summaries']
   for model in MODELS:
    paired=[r for r in subset if r['model']==model and (model,r['evaluation_id']) in baseline];totalq=sum(r['quantity'] for r in paired)
    drift[f'extra{lag}_{cohort}_{model}']={'paired_prints':len(paired),'quantity_weighted_abs_fair_change_cents':sum(r['quantity']*abs(r['fair_point']-baseline[(model,r['evaluation_id'])]['fair_point'])*100 for r in paired)/totalq if totalq else None,'threshold_accept_to_reject':sum(threshold(baseline[(model,r['evaluation_id'])]) and not threshold(r) for r in paired),'threshold_reject_to_accept':sum(not threshold(baseline[(model,r['evaluation_id'])]) and threshold(r) for r in paired),'interpretation':'Edge/quote-guard threshold changes before portfolio risk allocation.'}
 for path,h in hashes.items():
  if digest(path)!=h:raise ValueError('source changed during timing run')
 summary={'date':a.day.name,'timing_universe':data['timing_universe'],'baseline_source_sha256':digest(a.day/'replay/opportunities.json'),'source_hashes':hashes,'extra_information_lags_seconds':LAGS,'baseline_publication_delay_seconds':60,'coverage':coverage,'common_prints_all_models_all_lags':len(common),'zero_extra_lag_parity':parity,'drift':drift,'results':result,'interpretation':'Simultaneous additional K+PM historical information delay; not a test of missing Pinnacle30second feed. Actual trade time, fee-effective dates, observed price/size, pregame scope and outcomes unchanged. Historical point/fee/depth/payoff limitations inherited.'}
 dump(a.out/'summary.json',summary)
 lines=['# Archived exchange timing sensitivity — '+a.day.name,'',summary['interpretation'],'',f"Zero-extra-lag parity: {parity}. Four-model/four-lag common cohort: {len(common)} prints.",'',str(data['timing_universe']),'','| Extra lag | Model | Common unlimited fills | Common unlimited P&L | Common funded P&L | Fair absolute move (cents, quantity-weighted) |','|---|---|---:|---:|---:|---:|']
 for lag in LAGS:
  unlimited=result[f'extra{lag}_all_models_all_lags_common_unlimited'];funded={r['model']:r for r in result[f'extra{lag}_all_models_all_lags_common_funded']}
  for r in unlimited:
   move=drift[f"extra{lag}_all_models_all_lags_common_{r['model']}"]['quantity_weighted_abs_fair_change_cents']
   lines.append(f"| {lag}s | {r['model']} | {r['fills']} | ${r['trade_attributed_pnl']:,.2f} | ${funded[r['model']]['trade_attributed_pnl']:,.2f} | {move:.5f} |")
 lines+=['','Summary retains per-model available coverage, missing-leg reasons, common-cohort results and accept/reject changes. Available-cohort model comparisons are not paired when source coverage differs. P&L is known settlement attributed at trade time; cash/risk release uses actual settlement. No parameters optimized; no launch inference from one-date outcome shifts.'];(a.out/'REPORT.md').write_text('\n'.join(lines)+'\n');print(json.dumps({'common':len(common),'zero_parity':parity}))
if __name__=='__main__':main()

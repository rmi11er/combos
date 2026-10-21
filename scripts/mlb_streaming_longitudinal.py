#!/usr/bin/env python3
"""Disk-backed complete-cohort longitudinal evaluation; no live/network actions."""
import argparse,gzip,hashlib,itertools,json,math,resource,sqlite3,statistics,sys,time
from collections import Counter,defaultdict
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from combos.backtest import BacktestConfig,validate_opportunity
from combos.event_store import EventStore
from combos.risk import RiskLedger
from replay_artifact_io import text_writer,zstd_identity
from mlb_entry_sweep import VARIANTS
from mlb_validation_report import bounds
from mlb_longitudinal_sweep import plot

FIELDS=('observed_yes_premium','observed_payout_notional','point_edge','stressed_edge','evaluations','filled_yes_premium','maker_cash_spent','filled_payout_notional','fills','committed_cash','realized_pnl','settled_fills')
ATTR=('accepted_point_edge','accepted_stressed_edge','accepted_selected_edge','trade_attributed_pnl','resolved_outcomes','unresolved_outcomes')
def save(path,d):
 path=Path(path);temporary=path.with_suffix(path.suffix+'.tmp');temporary.write_text(json.dumps(d,indent=2,allow_nan=False)+'\n');temporary.replace(path)
def emit(f,row):f.write(json.dumps(row,separators=(',',':'),allow_nan=False)+'\n')
def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

class Metrics:
 def __init__(self,db,key):
  self.db=db;self.key=key;self._sums={};self.n=self.known=self.unknown=self.positive=0
  self.pnl=self.cash=self.knowncash=self.fees=self.premium=self.payout=self.edge=self.posedge=self.negedge=self.unknownlo=self.unknownhi=0
  self.fixture_pnl=defaultdict(float);self.fixture_cash=defaultdict(float)
 def add_sum(self,key,x):
  hi,lo=self._sums.get(key,(0.,0.));t=hi+x
  lo+=((hi-t)+x) if abs(hi)>=abs(x) else ((x-t)+hi)
  self._sums[key]=(t,lo);setattr(self,key,t+lo if lo and math.isfinite(lo) else t)
 def add(self,r):
  q,p,fee=r['quantity'],r['yes_price'],r['maker_fee'];cost=q*(1-p)+fee;edge=q*(p-r['fair_point'])-fee
  self.n+=1;self.add_sum('cash',cost);self.add_sum('fees',fee);self.add_sum('premium',q*p);self.add_sum('payout',q);self.add_sum('edge',edge);self.add_sum('posedge',max(0.,edge));self.add_sum('negedge',min(0.,edge));self.positive+=edge>0
  if r['yes_settlement'] is None:
   self.unknown+=1;self.add_sum('unknownlo',q*(p-1.)-fee);self.add_sum('unknownhi',q*(p-0.)-fee)
  else:
   self.known+=1;self.add_sum('pnl',q*(p-r['yes_settlement'])-fee);self.add_sum('knowncash',cost)
  for fixture in set(r['buckets']['fixture']):
   self.fixture_cash[fixture]+=cost
   if r['yes_settlement'] is not None:self.fixture_pnl[fixture]+=q*(p-r['yes_settlement'])-fee
  combos=set(r['buckets']['combo'])
  if len(combos)!=1:raise ValueError('single_canonical_combo_identity_required')
  combo=next(iter(combos));old=self.db.execute('SELECT cost FROM metric_combos WHERE scope=? AND combo=?',(self.key,combo)).fetchone()
  value=(old[0] if old else 0.)+cost
  self.db.execute('INSERT OR REPLACE INTO metric_combos VALUES(?,?,?)',(self.key,combo,value))
 def finish(self):
  count,maximum=self.db.execute('SELECT COUNT(*),MAX(cost) FROM metric_combos WHERE scope=?',(self.key,)).fetchone()
  return {'prints':self.n,'known_outcomes':self.known,'unknown_outcomes':self.unknown,'known_net_pnl':self.pnl,'loose_final_pnl_bounds':[self.pnl+self.unknownlo,self.pnl+self.unknownhi], 'fees':self.fees,'yes_premium':self.premium,'payout_notional':self.payout,'cumulative_no_cash_including_fees':self.cash,'known_cumulative_no_cash_including_fees':self.knowncash,'pnl_per_known_cumulative_no_cash':self.pnl/self.knowncash if self.knowncash else None,'net_point_edge':self.edge,'positive_net_point_edge':self.posedge,'negative_net_point_edge':self.negedge,'positive_edge_prints':self.positive,'unique_fixtures':len(self.fixture_cash),'unique_combos':count,'largest_fixture_cumulative_cash_share':max(self.fixture_cash.values(),default=0.)/self.cash if self.cash else None,'largest_combo_cumulative_cash_share':maximum/self.cash if self.cash else None,'known_pnl_after_removing_one_fixture_range':[min((self.pnl-self.fixture_pnl[k] for k in self.fixture_cash),default=self.pnl),max((self.pnl-self.fixture_pnl[k] for k in self.fixture_cash),default=self.pnl)],'fixture_contributions':[{'fixture':k,'known_net_pnl':self.fixture_pnl[k],'cumulative_no_cash_including_fees':self.fixture_cash[k]} for k in sorted(self.fixture_cash)],'concentration_basis':'Any-leg fixture membership overlaps; cumulative cash is not simultaneous exposure or a funded return.'}

def sampled(day_metrics,observed,plan,fixture_dates):
 daily=[{'date':day,'fold':plan['dates'][day],**day_metrics[day].finish()} for day in observed]
 resolved=[d for d in daily if d['unknown_outcomes']==0];pnl=[d['known_net_pnl'] for d in resolved];var=statistics.variance(pnl) if len(pnl)>1 else None
 ratio=statistics.mean(pnl)/math.sqrt(var) if len(pnl)>=plan['evaluation']['minimum_complete_resolved_slates_for_descriptive_sharpe'] and len(resolved)==len(daily) and var else None
 return {'annualized_sharpe':None,'daily_return_variance':None,'sharpe_reason':'calendar trading gaps and shared outcomes; no daily IID Sharpe inferred','observed_date_pnl_variance_dollars2':var,'descriptive_observed_date_pnl_mean_sd_ratio':ratio,'observed_dates':len(daily),'fully_resolved_observed_dates':len(resolved),'fixtures_shared_across_observed_dates':sum(len(ds)>1 for ds in fixture_dates.values()),'variance_basis':'known trade-attributed PnL on fully resolved observed dates only; not independent-slate or calendar variance','daily_contributions':daily}

class Compact:
 def __init__(self,count,maximum=2400):
  self.count=count;self.maximum=maximum;self.size=max(1,math.ceil(count/max(1,maximum//8)));self.output=[];self.first=None;self.last=None;self.extrema={}
 def add(self,index,row):
  if self.count<=self.maximum:self.output.append(row);return
  pair=(index,row)
  if self.first is None:self.first=pair
  self.last=pair
  for field in ('trade_attributed_pnl','accepted_point_edge','committed_cash'):
   if field not in self.extrema:self.extrema[field]=[pair,pair]
   else:
    lo,hi=self.extrema[field]
    if row[field]<lo[1][field]:self.extrema[field][0]=pair
    if row[field]>hi[1][field]:self.extrema[field][1]=pair
  if (index+1)%self.size==0 or index==self.count-1:
   chosen=dict([self.first,self.last,*[pair for bounds in self.extrema.values() for pair in bounds]])
   self.output.extend(chosen[i] for i in sorted(chosen));self.first=None;self.last=None;self.extrema={}

def artifact_path(prefix,kind,codec="gzip"):
 if codec not in ("gzip","zstd"):raise ValueError("unsupported artifact codec")
 return prefix.with_suffix("."+kind+".jsonl."+("gz" if codec=="gzip" else "zst"))

def evaluate_one(iterator,model,variant,label,config,constrained,coverage,plan,prefix,artifact_codec="gzip",ledger_factory=RiskLedger):
 artifact_path(prefix,"decisions",artifact_codec)
 # This leaf adapter preserves the authorized no-ticket-cap experiment.
 if config.maximum_yes_premium_dollars is not None:raise ValueError('streaming_study_requires_no_ticket_cap')
 previous=None
 start=bounds(coverage['observed_dates'][0],plan['timezone'])[0];end=bounds(coverage['observed_dates'][-1],plan['timezone'])[1]
 scratch=prefix.with_suffix('.scratch.sqlite')
 if scratch.exists():raise ValueError('scratch already exists: use clean experiment output')
 store=EventStore(scratch);db=store.db;db.execute('PRAGMA cache_size=-32768');db.execute('PRAGMA temp_store=FILE');db.execute('PRAGMA mmap_size=0')
 db.executescript('CREATE TABLE seen(id TEXT PRIMARY KEY); CREATE TABLE pending(at REAL,id TEXT PRIMARY KEY,payout REAL); CREATE INDEX pending_at ON pending(at,id); CREATE TABLE deltas(at REAL,stage INTEGER,seq INTEGER,data TEXT); CREATE INDEX delta_at ON deltas(at,stage,seq); CREATE TABLE metric_combos(scope TEXT,combo TEXT,cost REAL,PRIMARY KEY(scope,combo));')
 ledger=ledger_factory(store,asdict(config));metrics=Metrics(db,'all');day_metrics={d:Metrics(db,d) for d in coverage['observed_dates']};fixture_dates=defaultdict(set);reject=Counter();n=filled=0
 def delta(at,stage,seq,values):db.execute('INSERT INTO deltas VALUES(?,?,?,?)',(at,stage,seq,json.dumps(values,separators=(',',':'))))
 try:
  with text_writer(artifact_path(prefix,'decisions',artifact_codec)) as decisions,text_writer(artifact_path(prefix,'fills',artifact_codec)) as fills:
   while True:
    batch=list(itertools.islice(iterator,1000))
    if not batch:break
    with store.transaction():
     for row in batch:
      validate_opportunity(row,start,end);at=row['at'];identifier=row['evaluation_id'];n+=1
      order=(at,identifier)
      if previous is not None and order<previous:raise ValueError('chronological_input_order_required')
      previous=order
      if row['model']!=model:raise ValueError('unexpected model')
      try:db.execute('INSERT INTO seen VALUES(?)',(identifier,))
      except sqlite3.IntegrityError:raise ValueError('duplicate model opportunity') from None
      if constrained:
       while True:
        pending=db.execute('SELECT at,id,payout FROM pending WHERE at<=? ORDER BY at,id LIMIT 512',(at,)).fetchall()
        if not pending:break
        for when,old,payout in pending:ledger.transition(old,'simulated_settled',when,0,payout);db.execute('DELETE FROM pending WHERE id=?',(old,))
      q,p,fee=row['quantity'],row['yes_price'],row['maker_fee'];pe=q*(p-row['fair_point'])-fee;se=q*(p-row['stressed_upper'])-fee;edge=pe if config.entry_basis=='point' else se
      multiplier=row['source']['nlegs'] if config.minimum_net_edge_unit=='leg_contract' else 1
      if config.minimum_net_edge_unit=='leg_contract' and (type(multiplier) is not int or not 2<=multiplier<=4):raise ValueError('verified_two_through_four_leg_count_required')
      required=q*config.minimum_net_edge_per_share*multiplier
      delta(at,0,n,{'observed_yes_premium':q*p,'observed_payout_notional':q,'point_edge':pe,'stressed_edge':se,'evaluations':1})
      decision={**row,'entry_basis':config.entry_basis,'selected_net_edge':edge,'required_net_edge':required if config.entry_filter=='minimum_edge' else None,'entry_filter':config.entry_filter,'minimum_net_edge_unit':config.minimum_net_edge_unit,'observed_yes_premium':q*p,'accepted':False,'reason':'insufficient_edge'}
      if not row['quote_allowed']:decision['reason']='quote_guard'
      elif config.entry_filter=='all_priced' or edge>=required:
       decision.update(accepted=True,reason='accepted')
       if constrained:
        risk=ledger.reserve(identifier,'historical_creator_unknown',q*(1-p)+fee,row['buckets'],at+1,{'quantity':q},row['risk_multiplier']);decision.update(accepted=risk['allowed'],reason=risk.get('reason','accepted'),risk=risk)
        if risk['allowed']:ledger.transition(identifier,'simulated_filled',at,0)
       if decision['accepted']:
        filled+=1;settled=row.get('settled_at');settled=settled+config.settlement_delay_seconds if settled is not None else None;outcome=row.get('yes_settlement')
        known=settled is not None and (config.outcome_as_of is None or settled<=config.outcome_as_of);pnl=q*(p-outcome)-fee if known else None
        fill={'model':model,'fill_id':identifier,'filled_at':at,'quantity':q,'yes_price':p,'maker_fee':fee,'settled_at':settled,'yes_settlement':outcome,'basis':'simulated_execution','point_edge':pe,'stressed_edge':se,'selected_edge':edge,'pnl_attributed_at':at if known else None,'eventual_net_pnl':pnl};emit(fills,fill)
        cost=q*(1-p)+fee
        values={'filled_yes_premium':q*p,'maker_cash_spent':cost,'filled_payout_notional':q,'fills':1,'committed_cash':cost,'accepted_point_edge':pe,'accepted_stressed_edge':se,'accepted_selected_edge':edge}
        values.update({'trade_attributed_pnl':pnl,'resolved_outcomes':1} if known else {'unresolved_outcomes':1})
        if outcome is None:values.update(unknown_lower=q*(p-1)-fee,unknown_upper=q*p-fee)
        delta(at,1,filled,values)
        if settled is not None:
         if constrained:db.execute('INSERT INTO pending VALUES(?,?,?)',(settled,identifier,q*(1-outcome)))
         if settled<=end:delta(settled,1,filled,{'realized_pnl':q*(p-outcome)-fee,'committed_cash':-cost,'settled_fills':1})
        metrics.add(decision);day=datetime.fromtimestamp(at,ZoneInfo(plan['timezone'])).date().isoformat();day_metrics[day].add(decision)
        for f in row['buckets']['fixture']:fixture_dates[f].add(day)
      if not decision['accepted']:reject[decision['reason']]+=1
      emit(decisions,decision)
    db.execute('PRAGMA wal_checkpoint(TRUNCATE)')
  db.execute('INSERT INTO deltas VALUES(?,?,?,?)',(start,-1,0,'{}'));db.execute('INSERT INTO deltas VALUES(?,?,?,?)',(end,9,0,'{}'))
  count=db.execute('SELECT COUNT(DISTINCT at) FROM deltas').fetchone()[0];compact=Compact(count);totals={k:0. for k in (*FIELDS,*ATTR)};lo=hi=0.;peak=config.capital_dollars;draw=0.;tpeak=config.capital_dollars;tdraw=0.;cashpeak=0.;funding=0.;additional=0.
  cursor=db.execute('SELECT at,data FROM deltas ORDER BY at,stage,seq')
  with text_writer(artifact_path(prefix,'curves',artifact_codec)) as curves:
   for index,(at,group) in enumerate(itertools.groupby(cursor,key=lambda r:r[0])):
    changes=defaultdict(float)
    for _,raw in group:
     for key,value in json.loads(raw).items():changes[key]+=value
    for key in totals:totals[key]+=changes.get(key,0.)
    lo+=changes.get('unknown_lower',0.);hi+=changes.get('unknown_upper',0.)
    equity=config.capital_dollars+totals['realized_pnl'];available=equity-totals['committed_cash'];tequity=config.capital_dollars+totals['trade_attributed_pnl'];peak=max(peak,equity);draw=max(draw,peak-equity);tpeak=max(tpeak,tequity);tdraw=max(tdraw,tpeak-tequity);cashpeak=max(cashpeak,totals['committed_cash']);funding=max(funding,totals['committed_cash']-totals['realized_pnl']);additional=max(additional,-available)
    curve={'model':model,'at':at,'execution_basis':'simulated_execution' if filled else 'no_executions',**{k:totals[k] for k in FIELDS},'equity':equity,'available_cash':available,**{k:totals[k] for k in ATTR},'trade_attributed_equity':tequity,'point_edge_equity':config.capital_dollars+totals['accepted_point_edge'],'selected_edge_equity':config.capital_dollars+totals['accepted_selected_edge'],'trade_pnl_lower_bound':totals['trade_attributed_pnl']+lo,'trade_pnl_upper_bound':totals['trade_attributed_pnl']+hi}
    emit(curves,curve);compact.add(index,curve)
  record={'model':model,'variant':variant,'label':label,'regime':'funded' if constrained else 'unlimited','configuration':asdict(config),'selected':metrics.finish(),'sampled_statistics':sampled(day_metrics,coverage['observed_dates'],plan,fixture_dates),'rejection_counts':dict(reject),'portfolio':{'evaluations':n,'fills':filled,'realized_pnl':totals['realized_pnl'],'ending_equity':equity,'trade_attributed_pnl':totals['trade_attributed_pnl'],'ending_trade_attributed_equity':tequity,'ending_committed_cash':totals['committed_cash'],'peak_committed_cash':cashpeak,'minimum_starting_funding_for_path':max(0.,funding),'additional_funding_above_reporting_base':max(0.,additional),'max_settled_equity_drawdown_dollars':draw,'max_trade_attributed_drawdown_dollars':tdraw}}
  return record,compact.output
 finally:
  store.close()
  for path in (scratch,Path(str(scratch)+'-wal'),Path(str(scratch)+'-shm')):
   if path.exists():path.unlink()

def main():
 from mlb_disk_index import build_index,iter_model,count_model_rows
 p=argparse.ArgumentParser();p.add_argument('--batch-root',nargs='+',type=Path,required=True);p.add_argument('--plan',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--no-plots',action='store_true');p.add_argument('--artifact-codec',choices=('gzip','zstd'),default='gzip');a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
 codec={'name':a.artifact_codec,'format_version':2,'suffix':'.jsonl.gz' if a.artifact_codec=='gzip' else '.jsonl.zst','identity':zstd_identity() if a.artifact_codec=='zstd' else {'implementation':'Python gzip','python':sys.version}}
 plan=json.loads(a.plan.read_text());dbpath=a.out/'input.sqlite';coverage=build_index(a.batch_root,plan,dbpath);records=[];curves={};began=time.time()
 for model in plan['primary_models']:
  for variant,label,overrides in VARIANTS:
   config=BacktestConfig(entry_basis=plan['entry_basis'],timezone=plan['timezone'],**plan['baseline_limits'],**overrides)
   for constrained in (True,False):
    regime='funded' if constrained else 'unlimited';print(json.dumps({'model':model,'variant':variant,'regime':regime}),flush=True)
    record,path=evaluate_one(iter_model(dbpath,model),model,variant,label,config,constrained,coverage,plan,a.out/(model+'__'+variant+'__'+regime),artifact_codec=a.artifact_codec);records.append(record);curves[model,variant,regime]=path
 result={'artifact_format_version':2,'artifact_codec':codec,'study_id':plan['study_id'],'start_at':bounds(coverage['observed_dates'][0],plan['timezone'])[0],'end_at':bounds(coverage['observed_dates'][-1],plan['timezone'])[1],'coverage':coverage,'records':records,'interpretation':['One continuous ledger per policy; no daily cash resets. Complete certified paired cohort; actual settlement cash and retrospective trade-attributed PnL remain distinct. Streaming output is a scalability change only.'],'resources':{'peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'elapsed_evaluation_seconds':time.time()-began,'model_rows':count_model_rows(dbpath)}}
 if not a.no_plots:plot(result,curves,a.out)
 result['resources']['peak_rss_bytes']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
 result['resources']['elapsed_including_plots_seconds']=time.time()-began
 if a.artifact_codec=='zstd' and zstd_identity()!=codec['identity']:raise RuntimeError('codec_changed_during_replay')
 save(a.out/'summary.json',result)
 save(a.out/'complete.json',{'summary_sha256':digest(a.out/'summary.json'),'records':len(records),'plots':not a.no_plots,'artifact_format_version':2,'artifact_codec':codec})
if __name__=='__main__':main()

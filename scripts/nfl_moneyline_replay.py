#!/usr/bin/env python3
"""Offline certified-day NFL moneyline research; no provider calls or live quotes."""
import argparse
from bisect import bisect_right
from collections import Counter,defaultdict
from dataclasses import asdict
from datetime import datetime
from decimal import Decimal
import gzip,hashlib,json,math,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from combos.backtest import BacktestConfig,run_backtest
from combos.kalshi_history import KalshiHistory
from combos.fees import kalshi_fill_fee
from combos.payoff_risk import canonical_leg_risk
from combos.pricing import Interval,fee_expanded_book
from combos.joint_pricing import price_joint
from nfl_playoffs_history_audit import audit

MODELS=('kalshi','polymarket','exchange_blend_equal','exchange_blend_pm75')
def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def stamp(s):return datetime.fromisoformat(s.replace('Z','+00:00')).timestamp()
def readgz(p):
 with gzip.open(p,'rt') as f:return json.load(f)
def dump(p,d):
 p.parent.mkdir(parents=True,exist_ok=True)
 if p.suffix=='.gz':
  with gzip.open(p,'wt') as f:json.dump(d,f,separators=(',',':'),allow_nan=False)
 else:p.write_text(json.dumps(d,indent=2,allow_nan=False)+'\n')

def mapping_identity(row):
 f=row['fixture'];codes={f['away']:f['away_code'],f['home']:f['home_code']}
 teams=sorted(codes.values());fixture='nfl:'+f['scheduled_start'][:10]+':'+ '-'.join(teams)
 return {'sport':'NFL','fixture_key':fixture,'market_key':fixture+':moneyline:'+codes[row['team']], 'market_type':'moneyline','period':'full_game'}

def risk_buckets(legs,mappings):
 identities=[canonical_leg_risk(mapping_identity(mappings[l['market_ticker']]),l['side']) for l in legs]
 fixtures=[mapping_identity(mappings[l['market_ticker']])['fixture_key'] for l in legs]
 signature=sorted((x['key'],x['selected_sign']) for x in identities)
 return {'contract':sorted({x['key'] for x in identities}),'fixture':sorted(set(fixtures)), 'combo':[hashlib.sha256(json.dumps(signature,separators=(',',':')).encode()).hexdigest()]}

def selected(v,side):
 if side not in ('yes','no'):raise ValueError('invalid selected side')
 return v if side=='yes' else Interval(1-v.upper,1-v.point,1-v.lower)

def pm_prior(times,prices,intervals,at):
 cutoff=at-60
 if not any(lo<=cutoff<=hi for lo,hi in intervals):raise ValueError('uncovered_polymarket_timestamp')
 i=bisect_right(times,cutoff)-1
 if i<0:raise ValueError('no_prior_polymarket_state')
 # Never carry a point across a hole in successful query coverage.
 lo=max(lo for lo,hi in intervals if lo<=cutoff<=hi)
 # Intervals are merged before calling, so their start is the coverage boundary.
 if times[i]<lo:raise ValueError('polymarket_state_before_coverage_interval')
 return prices[i],times[i]

def merge_intervals(items):
 result=[]
 for lo,hi in sorted(items):
  if result and lo<=result[-1][1]:result[-1][1]=max(result[-1][1],hi)
  else:result.append([lo,hi])
 return result

class Sources:
 def __init__(self,root):
  self.evidence=audit(root);plan=json.loads((root/'plan.json').read_text())
  self.maps={r['kalshi_ticker']:r for r in plan['identities']}
  if any(r['polymarket_feesEnabled'] is not False for r in self.maps.values()):raise ValueError('PM fee-disabled scenario contradicts retained metadata')
  self.k=KalshiHistory(root,fallback_dirs=[],publication_delay=60,taker_rate=.07,cache_size=32)
  points=defaultdict(dict);ranges=defaultdict(list)
  for job in plan['jobs']:
   if job['venue']!='polymarket':continue
   ranges[job['identity']].append([job['start_at'],job['end_at']])
   for r in readgz(root/job['file'])['payload']['history']:points[job['identity']][float(r['t'])]=float(r['p'])
  self.pm={token:(sorted(v),[v[t] for t in sorted(v)],merge_intervals(ranges[token])) for token,v in points.items()}
 def leg(self,ticker,at):
  if ticker not in self.maps:raise ValueError('moneyline_identity_unavailable')
  m=self.maps[ticker]
  if at>=m['capture_end_at']:raise ValueError('earliest_verified_kickoff_cutoff')
  k=self.k.at(ticker,at);point,pt=pm_prior(*self.pm[m['polymarket_token']],at)
  ki=Interval(**k['interval']);half=(k['yes_ask']-k['yes_bid'])/2
  pi=fee_expanded_book(max(0,point-half),min(1,point+half),0)
  # Historical point remains the source point even near price boundaries.
  pi=Interval(pi.lower,point,pi.upper)
  def blend(w):return Interval(*((1-w)*getattr(ki,z)+w*getattr(pi,z) for z in ('lower','point','upper')))
  return dict(zip(MODELS,(ki,pi,blend(.5),blend(.75)))),{'ticker':ticker,'kalshi':k,'polymarket':{'point':point,'source_at':pt,'available_at':pt+60,'interval':asdict(pi),'depth':'unavailable historically','spread_basis':'Kalshi raw spread historical proxy only','feesEnabled':False},'mapping':m}

def certified_days(root):
 state=json.loads((root/'days/state.json').read_text());out=[]
 for date,entry in sorted(state['days'].items()):
  if entry.get('status')!='complete':continue
  for path,h in entry['output_sha256'].items():
   if digest(path)!=h:raise ValueError('completed cohort hash mismatch')
  cohort=root/'days'/date/'cohort';s=json.loads((cohort/'summary.json').read_text())
  if not s['complete_census'] or s['sport']!='NFL':raise ValueError('complete NFL census required')
  spans=[]
  for source in s['sources']:
   if digest(source['path'])!=source['sha256']:raise ValueError('tape manifest changed')
   spans.append((source['start_at'],source['end_at']))
  spans.sort()
  if len(spans)!=24 or spans[0][0]!=s['start_at'] or spans[-1][1]!=s['end_at'] or any(b!=c for (_,b),(c,_) in zip(spans,spans[1:])):raise ValueError('incomplete hourly census')
  out.append((date,cohort,s,entry['output_sha256']))
 if not out:raise ValueError('no complete NFL days')
 if any(a[2]['end_at']!=b[2]['start_at'] for a,b in zip(out,out[1:])):raise ValueError('noncontiguous completed dates require separate reporting windows')
 return out

def build(root,out):
 source=Sources(root/'exchange_history');days=certified_days(root);rows=[];counts={};seen=set();inputs={}
 with gzip.open(out/'pricing_context.jsonl.gz','wt') as context:
  for date,cohort,summary,hashes in days:
   inputs.update(hashes);markets=readgz(cohort/'combo_markets.json.gz');stats=Counter()
   with gzip.open(cohort/'candidate_trades.jsonl.gz','rt') as f:
    for line in f:
     r=json.loads(line);t=r['trade'];c=r['classification'];stats['all_primary_candidates']+=1
     if c['series']!=['KXNFLGAME']:stats['non_moneyline']+=1;continue
     if t.get('taker_side')!='yes':stats['not_yes_taker']+=1;continue
     at=stamp(t['created_time']);legs=markets[t['ticker']]['mve_selected_legs']
     if r['sampling_method']!='census' or not summary['start_at']<=at<summary['end_at'] or not 2<=len(legs)<=4 or not c['distinct_fixtures'] or not at<c['earliest_scheduled_start']-60:raise ValueError('candidate scope inconsistent')
     if t['trade_id'] in seen:raise ValueError('duplicate trade across complete days')
     seen.add(t['trade_id']);stats['moneyline_yes_taker_candidates']+=1
     p=float(t['yes_price_dollars']);q=float(t['count_fp'])
     if not 0<p<1 or q<=0:stats['invalid_open_price_or_quantity']+=1;continue
     try:values=[source.leg(l['market_ticker'],at) for l in legs]
     except ValueError as exc:stats[str(exc)]+=1;continue
     settlement=r.get('settlement_value_dollars');settled=r.get('settlement_ts')
     if settlement is None or settled is None:settlement=settled=None
     else:settlement=float(settlement);settled=stamp(settled)
     if settled is not None and settled<=at:raise ValueError('settlement precedes print')
     fee=float(kalshi_fill_fee(Decimal(t['count_fp']),1-Decimal(t['yes_price_dollars']),'.035')['net_fee'])
     base={'evaluation_id':t['trade_id'],'at':at,'quantity':q,'yes_price':p,'maker_fee':fee,'settled_at':settled,'yes_settlement':settlement,'buckets':risk_buckets(legs,source.maps),'quote_allowed':True,'risk_multiplier':1.,'source':{'sport':'NFL','nlegs':len(legs),'sampling_method':'census','source_window':r['source_window'],'series':['KXNFLGAME'],'combo_ticker':t['ticker'],'start_at':c['earliest_scheduled_start'],'schedule_basis':c['start_basis'],'fee_basis':{'rate':.035,'verified':False,'reference':'Unverified January combo maker research scenario; direct account precision .0001'},'payoff_basis':'Ordinary completed-game binary outcome assumption; exceptional parity unverified; eligibility independent of observed outcomes'}}
     for model in MODELS:
      intervals=tuple(selected(v[0][model],leg['side']) for v,leg in zip(values,legs));joint=price_joint(intervals,.05)
      rows.append({**base,'model':model,'fair_point':joint['joint']['point'],'stressed_upper':joint['stressed_upper']})
     context.write(json.dumps({'evaluation_id':t['trade_id'],'at':at,'legs':legs,'sources':[v[1] for v in values]},separators=(',',':'))+'\n');stats['common_priced_prints']+=1
   counts[date]=dict(stats)
 return {'schema_version':1,'run_id':'nfl_moneyline_historical','start_at':days[0][2]['start_at'],'end_at':days[-1][2]['end_at'],'completed_dates':[d[0] for d in days],'opportunities':rows,'coverage':counts,'input_hashes':inputs,'history_evidence':source.evidence,'historical_only':True,'Pinnacle':'All10 delayed archive probes404; absent from all models','fee_scenario':{'combo_maker_rate':.035,'kalshi_leg_taker_rate':.07,'polymarket_leg_taker_rate':0,'effective_dates_verified':False,'sensitivity_combo_maker_rates':[0,.0175,.035,.07]},'point_policy':'Independent distinct-fixture point product; fixed per-leg blend weights. 0.3c per combo entry. No source-disagreement live guard applied: research point diagnostic, not deployable.'}

def main():
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=ROOT/'runs/nfl_playoffs_history_20260907');p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
 data=build(a.root,a.out);dump(a.out/'opportunities.json',data);results={}
 for rate in (0,.0175,.035,.07):
  rows=[{**r,'maker_fee':float(kalshi_fill_fee(str(r['quantity']),1-Decimal(str(r['yes_price'])),str(rate))['net_fee']),'source':{**r['source'],'fee_basis':{**r['source']['fee_basis'],'rate':rate,'reference':'Explicit unverified January combo maker fee sensitivity'}}} for r in data['opportunities']]
  for constrained in (True,False):
   for policy in ('selection','sell_all'):
    key=f"fee{rate}_{'funded' if constrained else 'unlimited'}_{policy}"
    cfg=BacktestConfig(entry_basis='point',entry_filter='all_priced' if policy=='sell_all' else 'minimum_edge')
    result=run_backtest(rows,data['start_at'],data['end_at'],cfg,constrained)
    for summary in result['summaries']:
     accepted=[d for d in result['decisions'] if d['model']==summary['model'] and d['accepted']]
     known=[d for d in accepted if d['yes_settlement'] is not None]
     def pnl(d):return d['quantity']*(d['yes_price']-d['yes_settlement'])-d['maker_fee']
     largest=max(known,key=pnl) if known else None
     fixtures=sorted({f for d in known for f in d['buckets']['fixture']})
     summary['concentration']={'largest_winning_print':None if largest is None else {'evaluation_id':largest['evaluation_id'],'quantity':largest['quantity'],'net_pnl':pnl(largest),'yes_price':largest['yes_price'],'fixtures':largest['buckets']['fixture']},'pnl_without_largest_print':sum(map(pnl,known))-(pnl(largest) if largest else 0),'fixture_omission_pnl':{f:sum(pnl(d) for d in known if f not in d['buckets']['fixture']) for f in fixtures},'interpretation':'Descriptive omissions of selected prints; funded portfolio is not reallocated after omission.'}
    dump(a.out/(key+'.json.gz'),result);results[key]=result['summaries']
 summary={k:v for k,v in data.items() if k not in ('opportunities','history_evidence')};summary['results']=results
 summary['source_hashes']={str(f):digest(f) for f in (Path(__file__),ROOT/'src/combos/kalshi_history.py',ROOT/'src/combos/payoff_risk.py',ROOT/'src/combos/backtest.py',ROOT/'src/combos/fees.py',ROOT/'src/combos/joint_pricing.py',ROOT/'scripts/nfl_playoffs_history_audit.py',ROOT/'scripts/nfl_playoffs_exchange_history.py')}
 dump(a.out/'summary.json',summary)
 lines=['# NFL playoff moneyline historical replay','','Dates: '+', '.join(data['completed_dates'])+'. Complete observed days only; full-game moneyline, 2–4 distinct playoff fixtures, YES-taker prints, at least 60s pregame.','', 'Four models share an identical priced cohort. Universe below means this common moneyline cohort, not every NFL combo. Pinnacle is unavailable. Cash/risk follow actual settlement; eventual known P&L is attributed to trade time.','', '| Funding | Policy | Model | Fills | Net known P&L | Model edge | Peak cash | Unknown |','|---|---|---|---:|---:|---:|---:|---:|']
 for key,sums in results.items():
  if not key.startswith('fee0.035_'):continue
  for r in sums:lines.append(f"| {key.split('_')[1]} | {'sell all' if key.endswith('sell_all') else 'selection'} | {r['model']} | {r['fills']} | ${r['trade_attributed_pnl']:,.2f} | ${r['accepted_point_edge']:,.2f} | ${r['peak_committed_cash']:,.2f} | {r['unresolved_outcomes']} |")
 lines += ['', '## Concentration check', '', '| Unlimited selected model | P&L excluding largest winning print | Largest print P&L |', '|---|---:|---:|']
 for r in results['fee0.035_unlimited_selection']:
  c=r['concentration'];largest=c['largest_winning_print']
  lines.append(f"| {r['model']} | ${c['pnl_without_largest_print']:,.2f} | ${largest['net_pnl'] if largest else 0:,.2f} |")
 lines += ['', 'Inspect the largest-print and fixture-omission results before interpreting selection profit. All trades concern a handful of the same playoff outcomes; thousands of prints are not thousands of independent trials. Fixture-omission sensitivities are retained in summary.json.','', 'January fees are unverified scenarios: combo maker .035, Kalshi taker .07, PM zero based on archived fee-disabled metadata, direct .0001 cash precision, no opening fee accumulator. Summary and retained ledgers compare maker0/.0175/.035/.07; this is a bracket, not a certified historical schedule. PM taker fee and Kalshi taker fee expand intervals but do not shift fixed-blend midpoint prices.','','Historical exchange states become available 60s after source time; carry-forward stays inside captured query coverage. PM historical spread borrows Kalshi spread; no live depth is imputed. Ordinary completed-game payoff assumption does not certify exceptional cancellations/postponements. No outcome-based eligibility selection.','','This short dated sample shares only a few games and cannot establish stable daily Sharpe; daily statistics in raw backtest output are descriptive and should not be used as launch evidence. Quote guard true here means the offline scope/data checks passed, not that all production pricing gates are satisfied. Public print participation is hypothetical; no RFQ acceptance, queue or partial-fill model. Missing source states remain exclusions rather than synthetic prices.','','Coverage and every fee-sensitivity result: summary.json. Full portfolio and universe curves: corresponding compressed JSON ledgers.']
 (a.out/'REPORT.md').write_text('\n'.join(lines)+'\n');print(json.dumps({'dates':data['completed_dates'],'coverage':data['coverage'],'rows':len(data['opportunities'])}))
if __name__=='__main__':main()

#!/usr/bin/env python3
"""Descriptive common-cohort selected/rejected forensics; no model retuning."""
import argparse,csv,gzip,hashlib,json,math,sys
from collections import Counter,defaultdict
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo
ROOT=Path(__file__).resolve().parents[1];ZONE=ZoneInfo('America/Chicago')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def quantile(xs,p):
 xs=sorted(xs)
 if not xs:return None
 a=(len(xs)-1)*p;i=int(a);return xs[i]+(xs[min(i+1,len(xs)-1)]-xs[i])*(a-i)
def band(x,edges):
 for left,right in zip(edges,edges[1:]):
  if left<=x<right:return f'{left:g}-{right:g}'
 return 'other'
def summarize(rows):
 known=[r for r in rows if r['pnl'] is not None];q=sum(r['quantity'] for r in known);premium=sum(r['premium'] for r in known);cash=sum(r['liability'] for r in known);pnl=sum(r['pnl'] for r in known)
 return {'prints':len(rows),'resolved':len(known),'unknown':len(rows)-len(known),'known_net_pnl':pnl,'known_gross_pnl':sum(r['pnl']+r['maker_fee'] for r in known),'known_fees':sum(r['maker_fee'] for r in known),'known_payout_notional':q,'known_yes_premium':premium,'known_NO_cash_including_fee':cash,'net_per_payout_dollar':pnl/q if q else None,'net_per_yes_premium_dollar':pnl/premium if premium else None,'net_per_NO_cash_dollar':pnl/cash if cash else None,'mean_per_print_NO_cash_return':sum(r['return_on_liability'] for r in known)/len(known) if known else None,'constant_100_NO_cash_pnl':sum(100*r['return_on_liability'] for r in known),'weighted_realized_YES':sum(r['quantity']*r['yes_settlement'] for r in known)/q if q else None,'weighted_predicted_YES':sum(r['quantity']*r['fair_point'] for r in known)/q if q else None,'winning_seller_prints':sum(r['pnl']>0 for r in known),'unique_combos':len(set(r['combo'] for r in rows)),'unique_fixtures':len(set(f for r in rows for f in r['fixtures']))}
def writecsv(p,rows):
 if not rows:return
 keys=sorted(set().union(*(r.keys() for r in rows)))
 with p.open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)
def main():
 pa=argparse.ArgumentParser(description=__doc__);pa.add_argument('--out',type=Path,default=ROOT/'runs/cfb_selection_research_20260907/forensics');a=pa.parse_args();out=a.out;out.mkdir(parents=True,exist_ok=True)
 source=ROOT/'runs/cfb_full_week_20260907/replay_settlement_refreshed/common_opportunities.json';data=json.loads(source.read_text());decpath=ROOT/'runs/cfb_performance_audit_20260907/common_point_no_cap/unconstrained_decisions.jsonl';dec={}
 for line in decpath.open():
  r=json.loads(line)
  if r['model']=='blend':dec[r['evaluation_id']]=r
 rows=[]
 for r in data['opportunities']:
  if r['model']!='blend':continue
  d=dec[r['evaluation_id']];q=r['quantity'];p=r['yes_price'];fee=r['maker_fee'];y=r['yes_settlement'];pnl=q*(p-y)-fee if y is not None else None;cash=q*(1-p)+fee
  expected=r['quote_allowed'] and q*(p-r['fair_point'])-fee>=q*.003
  if expected!=d['accepted']:raise ValueError('saved selection differs from declared selection')
  dt=datetime.fromtimestamp(r['at'],ZONE);legs=r['source_context']['legs'];n=len(legs)
  rows.append({**r,'trade_id':r['evaluation_id'],'combo':r['source_context']['combo_ticker'],'fixtures':r['buckets']['fixture'],'legs':legs,'selected':d['accepted'],'reason':d['reason'],'pnl':pnl,'premium':q*p,'liability':cash,'return_on_liability':pnl/cash if pnl is not None else None,'day':dt.date().isoformat(),'hour':dt.hour,'nlegs':n,'price_band':band(p,[0,.01,.05,.1,.2,.4,.6,.8,1.00001]),'premium_band':band(q*p,[0,10,50.000000001,200,1000,float('inf')]),'predicted_edge_per_share':p-r['fair_point']-fee/q})
 rows.sort(key=lambda r:(r['at'],r['trade_id']));summary={};distributions=[];breakdowns=[];leaves=[];normalizations=[];matched=[];top={};unit_groups=[]
 for scope,rs in [('all',rows),('premium_le_50',[r for r in rows if Decimal(str(r['quantity']))*Decimal(str(r['yes_price']))<=50])]:
  for selected in (True,False):
   group='selected' if selected else 'rejected';items=[r for r in rs if r['selected']==selected];summary[scope+':'+group]=summarize(items)
   for field in ['yes_price','fair_point','quantity','premium','liability','predicted_edge_per_share','hour','nlegs']:
    xs=[r[field] for r in items];distributions.append({'scope':scope,'group':group,'field':field,'mean':sum(xs)/len(xs) if xs else None,**{f'p{int(p*100)}':quantile(xs,p) for p in [0,.1,.25,.5,.75,.9,.99,1]}})
   for dim in ['day','hour','nlegs','price_band','premium_band','reason']:
    bins=defaultdict(list)
    for r in items:bins[r[dim]].append(r)
    for b,v in bins.items():breakdowns.append({'scope':scope,'group':group,'dimension':dim,'value':b,**summarize(v)})
   for dim in ['combo','fixtures']:
    bins=defaultdict(list)
    for r in items:
     for k in ([r['combo']] if dim=='combo' else r['fixtures']):bins[k].append(r)
    for key,values in bins.items():unit_groups.append({'scope':scope,'group':group,'unit':dim,'key':key,**summarize(values)})
    ranked=sorted(bins,key=lambda k:sum(r['pnl'] or 0 for r in bins[k]),reverse=not selected)[:10]
    for k in ranked:
     remain=[r for r in items if (r['combo']!=k if dim=='combo' else k not in r['fixtures'])]
     leaves.append({'scope':scope,'group':group,'unit':dim,'removed_key':k,'removed_prints':len(bins[k]),'removed_net_pnl':sum(r['pnl'] or 0 for r in bins[k]),**{'remaining_'+k:v for k,v in summarize(remain).items()}})
   first={}
   for r in items:first.setdefault(r['combo'],r)
   normalizations.append({'scope':scope,'group':group,'experiment':'earliest_print_per_combo_within_group',**summarize(list(first.values()))})
   overall_first={}
   for r in rs:overall_first.setdefault(r['combo'],r)
   normalizations.append({'scope':scope,'group':group,'experiment':'earliest_print_per_combo_in_entire_scope',**summarize([r for r in overall_first.values() if r['selected']==selected])})
   normalizations.append({'scope':scope,'group':group,'experiment':'all_prints_fixed_100_NO_cash_per_print_linear_fee_scaling',**summarize(items)})
  for dims in [('nlegs','price_band'),('nlegs','price_band','premium_band'),('nlegs','price_band','premium_band','day')]:
   cells=defaultdict(lambda:{True:[],False:[]})
   for r in rs:
    if r['pnl'] is not None:cells[tuple(r[d] for d in dims)][r['selected']].append(r)
   overlap={k:v for k,v in cells.items() if len(v[True])>=5 and len(v[False])>=5};total=sum(len(v[True])+len(v[False]) for v in overlap.values());means={}
   for sel in (True,False):means['selected' if sel else 'rejected']=sum((len(v[True])+len(v[False]))*sum(r['return_on_liability'] for r in v[sel])/len(v[sel]) for v in overlap.values())/total if total else None
   matched.append({'scope':scope,'strata':'+'.join(dims),'minimum_each_group_per_cell':5,'overlap_cells':len(overlap),'overlap_selected':sum(len(v[True]) for v in overlap.values()),'overlap_rejected':sum(len(v[False]) for v in overlap.values()),'pooled_cell_weighted_mean_NO_cash_return':means})
 for label,sel,reverse in [('accepted_losses',True,False),('rejected_profits',False,True)]:
  items=[r for r in rows if r['selected']==sel and r['pnl'] is not None]
  top[label]=sorted(items,key=lambda r:r['pnl'],reverse=reverse)[:20]
 target={r['trade_id'] for vs in top.values() for r in vs};context={};cp=ROOT/'runs/cfb_full_week_20260907/replay/pricing_context.jsonl.gz'
 with gzip.open(cp,'rt') as f:
  for line in f:
   # Avoid parsing large irrelevant price contexts.
   if any(t in line[:150] for t in target):
    c=json.loads(line)
    if c['trade_id'] in target:context[c['trade_id']]=c
 native={};checks=[]
 for vs in top.values():
  for r in vs:
   outcomes=[]
   for leg in r['legs']:
    t=leg['market_ticker'];p=ROOT/'data/raw/legs'/(t+'.json.gz')
    if t not in native:
     if p.exists():
      env=json.load(gzip.open(p,'rt'));native[t]={'market':env['payload']['market'],'source':str(p.relative_to(ROOT)),'sha256':sha(p)}
     else:native[t]={'missing_native_metadata':True}
    m=native[t].get('market',{});s=m.get('settlement_value_dollars',m.get('yes_settlement_value_dollars'))
    if s is None:outcomes.append(None)
    else:outcomes.append(float(s) if leg['side']=='yes' else 1-float(s))
   implied=math.prod(outcomes) if all(v in (0.,1.) for v in outcomes) else None
   checks.append({'trade_id':r['trade_id'],'combo':r['combo'],'leg_selected_settlements':outcomes,'binary_leg_product':implied,'official_combo_settlement':r['yes_settlement'],'binary_settlement_consistent':implied==r['yes_settlement'] if implied is not None else None,'pricing_context_found':r['trade_id'] in context})
 with gzip.open(out/'top_print_evidence.json.gz','wt') as f:json.dump({'top_prints':top,'price_contexts':context,'native_legs':native,'checks':checks},f,separators=(',',':'))
 writecsv(out/'unit_groups.csv',unit_groups);writecsv(out/'distributions.csv',distributions);writecsv(out/'strata.csv',breakdowns);writecsv(out/'leave_one_out.csv',leaves);writecsv(out/'normalizations.csv',normalizations)
 (out/'matched_strata.json').write_text(json.dumps(matched,indent=2)+'\n');(out/'summary.json').write_text(json.dumps({'summaries':summary,'selection':'Saved unlimited blend point decisions; quote guard and net edge >=0.003/share; known outcomes only for P&L; all common9,511 evaluations retained.','limitations':['Descriptive common-support reweighting is not causal and cannot separate luck from calibration error.','Fixture leave-one-out sets overlap; do not sum removed fixture P&L.','Constant-liability scaling and earliest-print experiments change exposure; neither is a tradable sizing backtest.','Settlement-based ranks are diagnostic only; they cannot define a forward selection rule.']},indent=2)+'\n')
 (out/'manifest.json').write_text(json.dumps({'script_sha256':sha(Path(__file__)),'inputs':{str(p.relative_to(ROOT)):sha(p) for p in [source,decpath,cp]},'top_native_outcome_checks':checks},indent=2)+'\n')
 print(json.dumps(summary,indent=2));print('settlement_mismatches',sum(x['binary_settlement_consistent'] is False for x in checks),'top_evidence',len(context))
if __name__=='__main__':main()

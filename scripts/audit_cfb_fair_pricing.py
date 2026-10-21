#!/usr/bin/env python3
"""Read-only arithmetic, source-age and calibration audit of the saved CFB replay."""
import argparse
from collections import Counter, defaultdict
from dataclasses import asdict
from functools import lru_cache
import gzip
import hashlib
import json
import math
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from combos.fees import kalshi_fill_fee
from combos.historical_fair import History, timestamp
from combos.matching import fixture_teams, norm
from combos.pinnacle_history import PinnacleHistory
from combos.football_identity import provider_team_key


@lru_cache(maxsize=None)
def market(ticker):
    with gzip.open(ROOT/'data/raw/legs'/f'{ticker}.json.gz', 'rt') as f:
        return json.load(f)['payload']['market']


@lru_cache(maxsize=None)
def canonical(ticker):
    k = market(ticker); event = k['event_ticker']; fixture = event.split('-', 1)[1]
    teams = sorted(fixture_teams(k) or [])
    prefix = ticker.split('-')[0]
    flip = False
    if prefix == 'KXNCAAFGAME' and len(teams) == 2:
        flip = norm(k['yes_sub_title']) != teams[0]
        key = fixture+':ML:'+teams[0]
    elif prefix == 'KXNCAAFSPREAD' and len(teams) == 2:
        flip = norm(k['yes_sub_title'].split(' wins by ')[0]) != teams[0]
        key = fixture+':spread:'+teams[0]+':'+str(float(k['floor_strike'])*(-1 if flip else 1))
    elif prefix == 'KXNCAAFTOTAL':
        key = fixture+':total:'+str(float(k['floor_strike']))
    else:
        key = ticker
    value = k.get('settlement_value_dollars')
    y = float(value) if k.get('result') in ('yes', 'no') and value is not None and float(value) in (0, 1) else None
    if y is not None and flip: y = 1-y
    return key, fixture, flip, y


def quantiles(values):
    a = np.asarray(values, dtype=float)
    if not len(a): return {'n': 0}
    return {'n': len(a), 'median': float(np.median(a)), 'p90': float(np.quantile(a,.9)),
            'p99': float(np.quantile(a,.99)), 'maximum': float(np.max(a))}


def score(df, group):
    if df.empty: return {}
    df = df.copy(); df['brier']=(df.p-df.y)**2
    df['logloss']=-(df.y*np.log(df.p.clip(1e-10,1-1e-10))+(1-df.y)*np.log((1-df.p).clip(1e-10,1-1e-10)))
    out = {}
    for model, rows in df.groupby('model'):
        grouped=rows.groupby(group)[['brier','logloss','p','y']].mean()
        out[model]={'observations':len(rows),'groups':len(grouped),'brier':float(grouped.brier.mean()),
                    'logloss':float(grouped.logloss.mean()),'mean_forecast':float(grouped.p.mean()),
                    'mean_outcome':float(grouped.y.mean())}
    return out


def native_side_checks(pin, out):
    errors=[];counts=Counter()
    for ticker,m in pin.maps.items():
        d=pin._catalog[m['native_market_id']]
        label=next(r['outcomeName'] for r in d['outcomes'] if str(r['outcomeId'])==m['native_yes_outcome_id'])
        home=provider_team_key(m['fixture'],1);kind=m['kind'];counts[kind]+=1
        expected='Over' if kind=='totals' else '1' if m['team']==home else '2'
        threshold=None if kind=='moneyline' else float(d['handicap'])*(1 if kind=='totals' or label=='2' else -1)
        if (label!=expected or (threshold is not None and threshold!=float(m['line']))
                or d['period']!='result' or d['playerProp'] is not False):errors.append(ticker)
    (out/'native_side_checks.json').write_text(json.dumps({'mapped_tickers_checked':len(pin.maps),
        'kinds':dict(counts),'mismatches':errors,'scope':'Native outcome, sign, period and player flag; exceptional settlement not certified'},indent=2)+'\n')


def reserve_breakdown(frame, out):
    records=[]
    for (model,n),g in frame.groupby(['model','leg_count']):
        marginal=g.independent_upper-g.p
        dependence=g.dependence_reserve
        records.append({'model':model,'legs':int(n),'prints':len(g),
            'median_marginal_reserve_cents':float(100*marginal.median()),
            'median_dependence_reserve_cents':float(100*dependence.median()),
            'marginal_reserve_dollars':float((g.quantity*marginal).sum()),
            'dependence_reserve_dollars':float((g.quantity*dependence).sum()),
            'point_edge_dollars':float(g.point_edge.sum()),'stressed_edge_dollars':float(g.stressed_edge.sum())})
    pd.DataFrame(records).to_csv(out/'reserve_breakdown.csv',index=False)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-run',type=Path,default=ROOT/'runs/cfb_full_week_20260907')
    parser.add_argument('--out',type=Path,default=ROOT/'runs/cfb_performance_audit_20260907/fair_audit')
    args=parser.parse_args();args.out.mkdir(parents=True,exist_ok=True)
    opportunity_path=args.data_run/'replay_settlement_refreshed/opportunities.json'
    context_path=args.data_run/'replay/pricing_context.jsonl.gz'
    payload=json.loads(opportunity_path.read_text()); rows=payload['opportunities']
    lookup={(r['evaluation_id'],r['model']):r for r in rows}
    first={}
    for r in rows: first.setdefault(r['evaluation_id'],r)
    pin=PinnacleHistory(args.data_run); mapping=json.loads((args.data_run/'polymarket_mapping.json').read_text())
    checks=Counter(); maxima=defaultdict(float); ages=defaultdict(list); widths=defaultdict(list)
    leg_rows={}; common_leg_rows={}; source_rows={}; trade_stats={}; weights=defaultdict(list)
    @lru_cache(maxsize=None)
    def pmhistory(ticker):
        token=mapping[ticker]['token']
        with gzip.open(args.data_run/'polymarket'/f'{token}.json.gz','rt') as f:
            return History(json.load(f)['payload']['history'],'t')
    def check(name, difference, tolerance=1e-10):
        checks[name+'_checked']+=1; maxima[name]=max(maxima[name],abs(float(difference)))
        if abs(difference)>tolerance:checks[name+'_mismatch']+=1
    def add_leg(store, model, ticker, at, point):
        key, fixture, flip, y=canonical(ticker)
        if y is None:return
        identity=(model,key,int(at//3600))
        if identity not in store or at<store[identity]['at']:
            store[identity]={'model':model,'payoff':key,'fixture':fixture,'at':at,'hour':int(at//3600),
                             'ticker':ticker,'p':1-point if flip else point,'y':y}
    with gzip.open(context_path,'rt') as stream:
        for index,line in enumerate(stream):
            context=json.loads(line);tid=context['trade_id'];at=context['at']
            if tid not in first:continue
            base=first[tid];legs=base['source_context']['legs'];values=context['context']
            intervals={};stats={'maximum_kalshi_age':None,'maximum_pin_age':None,'maximum_kalshi_spread':None}
            for model in ('kalshi','pinnacle'):
                if model not in values:continue
                intervals[model]=[v['interval'] for v in values[model]]
                for leg,v in zip(legs,values[model]):
                    ticker=leg['market_ticker']; age=at-v['source_at'];ages[model].append(age)
                    if model=='kalshi':
                        spread=v['yes_ask']-v['yes_bid'];widths['kalshi_raw_spread'].append(spread)
                        stats['maximum_kalshi_spread']=max(stats['maximum_kalshi_spread'] or 0,spread)
                        stats['maximum_kalshi_age']=max(stats['maximum_kalshi_age'] or 0,age)
                        check('kalshi_midpoint',v['interval']['point']-(v['yes_bid']+v['yes_ask'])/2)
                        checks['kalshi_future_availability']+=v['available_at']>at+1e-8
                    else:
                        stats['maximum_pin_age']=max(stats['maximum_pin_age'] or 0,age)
                        m=pin.maps[ticker];yt,yr=m['pin_yes'].latest(at,30);nt,nr=m['pin_no'].latest(at,30)
                        expected=(1/yr['price'])/(1/yr['price']+1/nr['price'])
                        check('pinnacle_devig',v['interval']['point']-expected)
                        checks['pinnacle_future_availability']+=max(yt,nt)+30>at+1e-8
                        checks['pinnacle_inactive_used']+=yr.get('active') is not True or nr.get('active') is not True
                        checks['pinnacle_post_cutoff']+=at>=m['start_at']-60
                    source_key=(model,ticker,v['source_at'])
                    source_rows[source_key]={'model':model,'ticker':ticker,'source_at':v['source_at'],'age':age,
                                              'point':v['interval']['point'],'width':v['interval']['upper']-v['interval']['lower']}
                    add_leg(leg_rows,model,ticker,at,v['interval']['point'])
            if 'three_venue' in values:
                for model in ('blend','stronger_pinnacle'):
                    intervals[model]=[f['models'][model] for f in values['three_venue']]
                for leg,f in zip(legs,values['three_venue']):
                    ticker=leg['market_ticker'];_,pmrow=pmhistory(ticker).latest(at,60)
                    points={'kalshi':f['models']['kalshi']['point'],'pinnacle':f['models']['pinnacle']['point'],'polymarket':pmrow['p']}
                    for model,label in (('blend','blend'),('stronger_pinnacle','stronger')):
                        details=f[label]; expected=sum(points[v]*info['weight'] for v,info in details['venues'].items())
                        check(model+'_arithmetic_blend',f['models'][model]['point']-expected)
                        check(model+'_weight_sum',sum(v['weight'] for v in details['venues'].values())-1)
                        for v,info in details['venues'].items(): weights[model+':'+v].append(info['weight'])
                        widths[model+'_envelope_above_weighted_upper'].append(details['fair']['upper']-details['unprotected_blend']['upper'])
                        add_leg(leg_rows,model,ticker,at,f['models'][model]['point'])
                    for venue,age in f['raw_state_ages'].items():ages['three_venue:'+venue].append(age)
                    checks['three_venue_leg_contexts']+=1
                    checks['three_venue_strict_live_age_pass']+=f['strict_current_age_gate_pass']
                    for venue,info in f['blend']['venues'].items():
                        ages['effective_weighting:'+venue].append(info['age_seconds'])
            all_models=set(intervals)=={'kalshi','pinnacle','blend','stronger_pinnacle'}
            for model,ints in intervals.items():
                row=lookup.get((tid,model))
                if row is None:continue
                p=math.prod(i['point'] if l['side']=='yes' else 1-i['point'] for i,l in zip(ints,legs))
                check('joint_point_product',row['fair_point']-p)
                checks['stressed_below_point']+=row['stressed_upper']+1e-10<row['fair_point']
                if all_models:
                    for leg,value in zip(legs,ints):add_leg(common_leg_rows,model,leg['market_ticker'],at,value['point'])
                upper=math.prod(i['upper'] if l['side']=='yes' else 1-i['lower'] for i,l in zip(ints,legs))
                lower=math.prod(i['lower'] if l['side']=='yes' else 1-i['upper'] for i,l in zip(ints,legs))
                row_stats={**stats,'independent_upper':upper,'independent_lower':lower,
                           'maximum_leg_interval_width':max(i['upper']-i['lower'] for i in ints),
                           'joint_band_width':upper-lower, 'dependence_reserve':row['stressed_upper']-upper}
                trade_stats[(tid,model)]=row_stats
            if index%10000==0:print(json.dumps({'contexts_processed':index}),flush=True)
    frame=pd.DataFrame(rows)
    frame['p']=frame.fair_point;frame['y']=frame.yes_settlement
    frame['point_edge']=frame.quantity*(frame.yes_price-frame.fair_point)-frame.maker_fee
    frame['stressed_edge']=frame.quantity*(frame.yes_price-frame.stressed_upper)-frame.maker_fee
    frame['print_profit']=frame.quantity*(frame.yes_price-frame.yes_settlement)-frame.maker_fee
    frame['leg_count']=[len(x['legs']) for x in frame.source_context]
    frame['combo_key']=[json.dumps(sorted((canonical(l['market_ticker'])[0],
                                         (l['side']=='yes') != canonical(l['market_ticker'])[2]) for l in x['legs'])) for x in frame.source_context]
    for name in ('maximum_kalshi_age','maximum_pin_age','maximum_kalshi_spread','independent_upper','independent_lower','maximum_leg_interval_width','joint_band_width','dependence_reserve'):
        frame[name]=[trade_stats.get((r['evaluation_id'],r['model']),{}).get(name) for r in rows]
    settled=frame[frame.y.notna()].copy()
    window_settled=frame[frame.y.notna() & (frame.settled_at<=payload['end_at'])].copy()
    paired_ids={tid for tid,group in frame.groupby('evaluation_id') if group.model.nunique()==4}
    legs=pd.DataFrame(leg_rows.values());common_legs=pd.DataFrame(common_leg_rows.values())
    legs.to_csv(args.out/'leg_hour_scores.csv',index=False);common_legs.to_csv(args.out/'common_leg_hour_scores.csv',index=False)
    # One row per canonical payoff/hour/model; balance payoff histories within fixture.
    def fixture_scores(df):
        if df.empty:return {}
        copy=df.copy();copy['brier']=(copy.p-copy.y)**2
        payoff=copy.groupby(['model','fixture','payoff']).brier.mean().reset_index()
        fixture=payoff.groupby(['model','fixture']).brier.mean().reset_index()
        return {m:{'fixtures':len(g),'payoffs':int(payoff[payoff.model==m].payoff.nunique()),
                   'brier':float(g.brier.mean())} for m,g in fixture.groupby('model')}
    summaries=[]
    for model,g in frame.groupby('model'):
        for filtername,mask in [('all',pd.Series(True,index=g.index)),('point_entry',g.quote_allowed & (g.point_edge>=.003*g.quantity)),
                               ('stressed_entry',g.quote_allowed & (g.stressed_edge>=.003*g.quantity))]:
            sub=g[mask];done=sub[sub.y.notna()]
            summaries.append({'model':model,'filter':filtername,'prints':len(sub),'settled_prints':len(done),
                              'point_edge':float(sub.point_edge.sum()),'stressed_edge':float(sub.stressed_edge.sum()),
                              'settled_print_profit':float(done.print_profit.sum()),
                              'known_settled_point_edge':float(done.point_edge.sum()),
                              'known_settled_payout_notional':float(done.quantity.sum()),
                              'mean_forecast_unweighted':float(done.p.mean()) if len(done) else None,
                              'mean_outcome_unweighted':float(done.y.mean()) if len(done) else None,
                              'outcome_minus_forecast_unweighted':float((done.y-done.p).mean()) if len(done) else None,
                              'q_weighted_forecast':float(np.average(done.p,weights=done.quantity)) if len(done) else None,
                              'q_weighted_outcome':float(np.average(done.y,weights=done.quantity)) if len(done) else None,
                              'q_weighted_outcome_minus_forecast':float(np.average(done.y-done.p,weights=done.quantity)) if len(done) else None,
                              'brier_unweighted':float(((done.p-done.y)**2).mean()) if len(done) else None,
                              'brier_q_weighted':float(np.average((done.p-done.y)**2,weights=done.quantity)) if len(done) else None,
                              'model_expected_winning_yes_contracts_settled':float((done.quantity*done.p).sum()),
                              'realized_winning_yes_contracts_settled':float((done.quantity*done.y).sum())})
    pd.DataFrame(summaries).to_csv(args.out/'entry_economics.csv',index=False)
    strat=[]
    for model,g in settled.groupby('model'):
        g=g.copy();g['spread_bucket']=pd.cut(g.maximum_kalshi_spread,[-1,.02,.05,.1,.25,1],labels=['<=2c','2–5c','5–10c','10–25c','>25c'])
        g['pin_age_bucket']=pd.cut(g.maximum_pin_age,[-1,90,600,3600,86400,float('inf')],labels=['<=90s','90s–10m','10m–1h','1–24h','>24h'])
        g['joint_band_bucket']=pd.cut(g.joint_band_width,[-1,.02,.05,.1,.25,1],labels=['<=2c','2–5c','5–10c','10–25c','>25c'])
        for dimension in ('spread_bucket','pin_age_bucket','joint_band_bucket'):
            for bucket,sub in g.groupby(dimension,observed=True):
                entry=sub[sub.quote_allowed & (sub.point_edge>=.003*sub.quantity)]
                strat.append({'model':model,'dimension':dimension,'bucket':str(bucket),'prints':len(sub),
                              'brier':float(((sub.p-sub.y)**2).mean()),'point_entries':len(entry),
                              'entry_expected_edge':float(entry.point_edge.sum()),'entry_settled_profit':float(entry.print_profit.sum()),
                              'observed_markup_unweighted_cents':float(100*(sub.yes_price-sub.p).mean()),
                              'observed_markup_q_weighted_cents':float(100*np.average(sub.yes_price-sub.p,weights=sub.quantity)),
                              'q_weighted_outcome_minus_forecast':float(np.average(sub.y-sub.p,weights=sub.quantity)),
                              'entry_q_weighted_outcome_minus_forecast':float(np.average(entry.y-entry.p,weights=entry.quantity)) if len(entry) else None})
    pd.DataFrame(strat).to_csv(args.out/'quality_strata.csv',index=False)
    frame[['evaluation_id','model','at','quantity','yes_price','p','y','leg_count','point_edge','stressed_edge',
           'print_profit','quote_allowed','maximum_kalshi_age','maximum_pin_age','maximum_kalshi_spread',
           'maximum_leg_interval_width','joint_band_width','independent_upper','independent_lower',
           'dependence_reserve']].to_csv(args.out/'per_print_diagnostics.csv.gz',index=False,compression='gzip')
    fee_errors=[]
    for row in first.values():
        fee=float(kalshi_fill_fee(row['quantity'],round(1-row['yes_price'],10),row['source_context']['maker_fee_rate'])['net_fee'])
        fee_errors.append(row['maker_fee']-fee)
    report={'arithmetic_checks':dict(checks),'maximum_absolute_error':dict(maxima),
            'maker_fee_vs_current_single_fill_adapter':{'maximum_absolute_error':max(map(abs,fee_errors)),
                                                       'total_signed_difference':sum(fee_errors),'prints':len(fee_errors)},
            'raw_age_seconds':{k:quantiles(v) for k,v in ages.items()},
            'widths_probability_units':{k:quantiles(v) for k,v in widths.items()},
            'weights':{k:quantiles(v) for k,v in weights.items()},
            'leg_fixture_balanced':fixture_scores(legs),'common_leg_fixture_balanced':fixture_scores(common_legs),
            'combo_all_print_scores':score(settled,'evaluation_id'),
            'combo_settled_by_window_end_scores':score(window_settled,'evaluation_id'),
            'combo_unique_payoff_balanced':score(settled,'combo_key'),
            'combo_common_unique_payoff_balanced':score(settled[settled.evaluation_id.isin(paired_ids)],'combo_key'),
            'limitations':['Outcome labels are used for evaluation only; source state used as of decision time.',
                'Leg sampling: earliest observed decision per canonical payoff/hour/model, then average within payoff and fixture.',
                'Common leg observations require all four sources available at the same originating decision.',
                'Repeated hourly forecasts and shared fixtures are not independent statistical samples.',
                'Trade-age and spread summaries are weighted by occurrence in retained candidate prints.',
                'Primary calibration and entry economics use every supplied known settlement, including after the trading window; this is retrospective attribution, not window-end cash equity. The separately named window-end score excludes later settlements. Native leg labels use currently resolved binary metadata.',
                'No quote acceptance, new market data or live fills are inferred.'],
            'input_hashes':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (opportunity_path,context_path)}}
    native_side_checks(pin,args.out)
    reserve_breakdown(frame,args.out)
    (args.out/'summary.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'arithmetic_checks':dict(checks),'leg_fixture_balanced':report['leg_fixture_balanced'],
                      'common_leg_fixture_balanced':report['common_leg_fixture_balanced'],
                      'combo_common_unique_payoff_balanced':report['combo_common_unique_payoff_balanced']},indent=2))


if __name__=='__main__':main()

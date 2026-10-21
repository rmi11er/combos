#!/usr/bin/env python3
"""Retrospective purged walk-forward checks on already-inspected CFB data."""
import argparse
from collections import Counter,defaultdict
from dataclasses import asdict
from datetime import datetime,timedelta
from functools import lru_cache
import gzip
import hashlib
import json
import math
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from combos.research_validation import (Forecast,Fold,CalibrationPolicy,purged_fold,
    fit_shrunk_calibration,exposure_metrics,PricePoint,score_markout)
from combos.kalshi_history import KalshiHistory
from combos.pinnacle_history import PinnacleHistory
from combos.matching import norm,fixture_teams


def write(path,value):
    path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')


@lru_cache(maxsize=None)
def payoff_leg(ticker,side):
    with gzip.open(ROOT/'data/raw/legs'/f'{ticker}.json.gz','rt') as f:k=json.load(f)['payload']['market']
    fixture=k['event_ticker'].split('-',1)[1];teams=sorted(fixture_teams(k) or [])
    typ=ticker.split('-')[0];flip=False
    if typ=='KXNCAAFGAME':
        if len(teams)!=2:raise ValueError('canonical_team_pair_missing')
        flip=norm(k['yes_sub_title'])!=teams[0];key=f'{fixture}:moneyline:{teams[0]}'
    elif typ=='KXNCAAFSPREAD':
        if len(teams)!=2:raise ValueError('canonical_team_pair_missing')
        flip=norm(k['yes_sub_title'].split(' wins by ')[0])!=teams[0]
        key=f'{fixture}:spread:{teams[0]}:'+str(float(k['floor_strike'])*(-1 if flip else 1))
    elif typ=='KXNCAAFTOTAL':key=f'{fixture}:total:'+str(float(k['floor_strike']))
    else:raise ValueError('full_game_only')
    return key,(side=='yes')!=flip


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',type=Path,default=ROOT/'runs/cfb_full_week_20260907/replay_settlement_refreshed/opportunities.json')
    p.add_argument('--data-run',type=Path,default=ROOT/'runs/cfb_full_week_20260907')
    p.add_argument('--out',type=Path,default=ROOT/'runs/cfb_selection_research_20260907/validation')
    p.add_argument('--maximum-yes-premium',type=float,default=50.,help='Fixed research cohort cap; not a live-policy change')
    p.add_argument('--skip-markouts',action='store_true')
    args=p.parse_args();args.out.mkdir(parents=True,exist_ok=True)
    payload=json.loads(args.input.read_text());source=payload['opportunities']
    if not math.isfinite(args.maximum_yes_premium) or args.maximum_yes_premium<=0:raise ValueError('positive research premium cap required')
    models=('kalshi','pinnacle','blend','stronger_pinnacle')
    groups=defaultdict(list)
    for r in source:groups[r['evaluation_id']].append(r)
    records=[];native={};exclusions=Counter()
    for identifier,rows in groups.items():
        if len(rows)!=4 or {r['model'] for r in rows}!=set(models):exclusions['not_common_four_model']+=1;continue
        r=rows[0];legs=r['source_context']['legs']
        if not 2<=len(legs)<=4 or len(r['buckets']['fixture'])!=len(legs):exclusions['not_distinct_two_through_four']+=1;continue
        if any(l['market_ticker'].split('-')[0] not in ('KXNCAAFGAME','KXNCAAFSPREAD','KXNCAAFTOTAL') for l in legs):
            exclusions['not_full_game']+=1;continue
        if r['quantity']*r['yes_price']>args.maximum_yes_premium+1e-9:exclusions['research_yes_premium_above_cap']+=1;continue
        identity=json.dumps(sorted(payoff_leg(l['market_ticker'],l['side']) for l in legs))
        native[identifier]=r
        for row in rows:
            records.append(Forecast(identifier,row['model'],row['at'],row['fair_point'],
                tuple(sorted(row['buckets']['fixture'])),identity,row['quantity'],row['yes_price'],row['maker_fee'],
                row['yes_settlement'],row['settled_at'],row['quote_allowed'],row['at']))
    timezone=ZoneInfo('America/Chicago');policy=CalibrationPolicy();fits=[];predictions=[];fold_metrics=[]
    day=datetime.fromtimestamp(payload['start_at'],timezone)
    folds=[]
    while day.timestamp()<payload['end_at']:
        following=day+timedelta(days=1)
        folds.append(Fold(day.date().isoformat(),day.timestamp(),min(following.timestamp(),payload['end_at'])))
        day=following
    corrected={};fold_for={}
    for model in models:
        model_records=[r for r in records if r.model==model]
        for fold in folds:
            train,test,counts=purged_fold(model_records,fold)
            fit=fit_shrunk_calibration(train,fold.fit_at,policy,
                day_key=lambda t:datetime.fromtimestamp(t,timezone).date().isoformat())
            fits.append({'model':model,'fold':fold.name,**counts,**asdict(fit)})
            pmap={r.identifier:fit.predict(r.probability) for r in test}
            for r in test:
                corrected[(model,r.identifier)]=pmap[r.identifier];fold_for[r.identifier]=fold.name
                predictions.append({'model':model,'identifier':r.identifier,'fold':fold.name,'at':r.decision_at,
                    'base_probability':r.probability,'calibrated_probability':pmap[r.identifier],
                    'training_adjustment':fit.adjustment,'identity_fallback':bool(fit.fallback_reasons)})
            for candidate,values in [('static',None),('shrunk_calibration',pmap)]:
                for selected in (False,True):fold_metrics.append({'model':model,'fold':fold.name,'candidate':candidate,
                    'selection':'point_edge' if selected else 'all',
                    **exposure_metrics(test,values,selected_only=selected)})
    total=[]
    for model in models:
        model_records=[r for r in records if r.model==model]
        pmap={r.identifier:corrected[(model,r.identifier)] for r in model_records}
        for candidate,values in [('static',None),('shrunk_calibration',pmap)]:
            for selected in (False,True):total.append({'model':model,'candidate':candidate,
                'selection':'point_edge' if selected else 'all',
                **exposure_metrics(model_records,values,selected_only=selected)})
    write(args.out/'fold_fits.json',fits);write(args.out/'fold_metrics.json',fold_metrics)
    write(args.out/'aggregate_metrics.json',total)
    with gzip.open(args.out/'predictions.jsonl.gz','wt') as f:
        for row in predictions:f.write(json.dumps(row)+'\n')
    print(json.dumps({'common_capped_prints':len(native),'fold_fits':len(fits),
                      'fits_without_fallback':sum(not f['fallback_reasons'] for f in fits)}),flush=True)
    markout_counts=Counter();markout_groups=defaultdict(list);markout_path=args.out/'markouts.jsonl.gz'
    if not args.skip_markouts:
        kalshi=KalshiHistory(args.data_run);pinnacle=PinnacleHistory(args.data_run)
        selected={(r.model,r.identifier):r.quote_allowed and
                  r.quantity*(r.yes_price-r.probability)-r.maker_fee>=.003*r.quantity for r in records}
        def joint_point(venue,legs,at):
            adapter=kalshi if venue=='kalshi' else pinnacle
            values=[adapter.at(l['market_ticker'],at) for l in legs]
            probability=math.prod(v['interval']['point'] if l['side']=='yes' else 1-v['interval']['point'] for l,v in zip(legs,values))
            if venue=='kalshi':
                source_at=max(v['source_at'] for v in values);available=max(v['available_at'] for v in values)
            else:
                provenance=[v['source_provenance'] for v in values]
                source_at=max(max(v['yes_state_at'],v['no_state_at']) for v in provenance)
                available=max(v['available_at_assumption'] for v in provenance)
            return PricePoint(probability,source_at,available,reference=venue+':historical_joint_product')
        with gzip.open(markout_path,'wt') as stream:
            for index,(identifier,r) in enumerate(native.items()):
                legs=r['source_context']['legs'];at=r['at']
                # Common-cohort Pinnacle metadata supplies an exact kickoff for every leg.
                earliest=min(pinnacle.maps[l['market_ticker']]['start_at'] for l in legs)
                for venue in ('kalshi','pinnacle'):
                    for horizon in (60,300):
                        prefix=venue+':'+str(horizon);markout_counts[prefix+':attempted']+=1
                        try:
                            if at+horizon>=earliest-60:raise ValueError('target_crosses_pregame_cutoff')
                            entry=joint_point(venue,legs,at);target=joint_point(venue,legs,at+horizon)
                            result=score_markout(entry,target,at,horizon,r['yes_price'],r['quantity'],r['maker_fee'])
                            markout_counts[prefix+':scored']+=1
                            record={'identifier':identifier,'fold':fold_for[identifier],'venue':venue,'quantity':r['quantity'],**result}
                            record['selected_by_venue_point']=selected[(venue,identifier)]
                            record['selected_by_blend_point']=selected[('blend',identifier)]
                            stream.write(json.dumps(record)+'\n')
                            markout_groups[prefix+':all'].append(record)
                            if record['selected_by_venue_point']:markout_groups[prefix+':selected_venue_point'].append(record)
                            if record['selected_by_blend_point']:markout_groups[prefix+':selected_blend_point'].append(record)
                        except (ValueError,KeyError,OSError) as exc:
                            reason=str(exc) if isinstance(exc,ValueError) else type(exc).__name__
                            markout_counts[prefix+':'+reason]+=1
                if index%2000==0:print(json.dumps({'markout_decisions':index,'total':len(native)}),flush=True)
    markout_summary={key:{'scored':len(rows),
        'mean_probability_change':sum(r['probability_change'] for r in rows)/len(rows),
        'quantity_weighted_probability_change':sum(r['quantity']*r['probability_change'] for r in rows)/sum(r['quantity'] for r in rows),
        'maker_NO_mark_change':sum(r['maker_NO_mark_change'] for r in rows),
        'net_value_at_target':sum(r['net_value_at_target'] for r in rows),
        'minimum_effective_source_horizon':min(r['effective_source_horizon'] for r in rows),
        'maximum_effective_source_horizon':max(r['effective_source_horizon'] for r in rows)} for key,rows in markout_groups.items()}
    report={'study_type':'retrospective_walk_forward_on_already_inspected_data_not_untouched_holdout',
        'models':models,'candidate':'fixed_fixture_shrunk_additive_calibration','policy':asdict(policy),
        'common_prints':len(native),'model_forecasts':len(records),'scope_exclusions':dict(exclusions),
        'maximum_yes_premium_dollars':args.maximum_yes_premium,'timezone':'America/Chicago',
        'folds':[asdict(f) for f in folds], 'fits_without_fallback':sum(not f['fallback_reasons'] for f in fits),
        'fallback_fit_count':sum(bool(f['fallback_reasons']) for f in fits),
        'markout_counts':dict(markout_counts),'markout_summary':markout_summary,
        'input_sha256':hashlib.sha256(args.input.read_bytes()).hexdigest(),
        'code_sha256':{str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest() for f in
            [Path(__file__),ROOT/'src/combos/research_validation.py',ROOT/'src/combos/kalshi_history.py',ROOT/'src/combos/pinnacle_history.py']},
        'limitations':['All CFB outcomes/charts were already inspected. No model is promoted by these results.',
            'Fixture purging uses future test-fold identities only as an offline exclusion boundary; a deployable fit needs its exclusion universe predeclared.',
            'Forecast availability is the audited replay decision time, with zero compute/response latency assumed. Raw feed health remains unverified.',
            'Training uses only settlement labels available strictly before fitting. Evaluation may use later supplied settlements.',
            'Exposure is gross loss and fixture concentration; no capital allocation, executable fills or Sharpe is inferred.',
            'Historical markouts require genuinely post-decision source information available by the horizon. Missing/unchanged states are exclusions, not zero returns.',
            'Unavailable historical markouts do not test or refute a delayed-anchor innovation model; publication/heartbeat/actual spread/depth evidence is missing.',
            'Markout horizons stay pregame; partial source changes can update a joint mark while other components are carried active states.',
            '60-second Kalshi markouts cannot supply post-decision source information under the existing 60-second publication allowance.',
            'Future Kalshi/Pinnacle marks are venue-dependent benchmarks, not true fair or executed liquidation prices.',
            'PM historical spreads/depth are absent, preventing realistic 30-second three-venue innovation validation.']}
    write(args.out/'summary.json',report)
    print(json.dumps({'markout_counts':dict(markout_counts),'markout_summary':markout_summary},indent=2))


if __name__=='__main__':main()

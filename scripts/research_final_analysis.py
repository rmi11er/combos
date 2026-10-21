"""Final weighting, forecast validation and data for the research chart atlas."""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import numpy as np


def clock_curve(clocks,window):
    lead=[1/60,.25,1,3,6] if window==6 else [1/60,.25,1,3,6,12,24,48,72,120]
    curves=[]
    for period in ['train','test']:
        group=[c for c in clocks if c['period']==period]
        for cutoff in lead:
            byday=defaultdict(list);remaining=0;total=0
            for c in group:
                denominator=sum(b['contracts'] for b in c['bins'] if b['hi_hours']<=window)
                if not denominator:continue
                numerator=sum(b['contracts'] for b in c['bins'] if b['hi_hours']<=cutoff)
                byday[c['date']].append(numerator/denominator)
                remaining+=numerator;total+=denominator
            curves.append({'period':period,'lead_hours':cutoff,'groups':sum(map(len,byday.values())),'dates':len(byday),
                'remaining_fraction_equal_day':float(np.mean([np.mean(v) for v in byday.values()])),
                'remaining_fraction_volume_weighted':remaining/total})
    return curves


def forecast_scores(rows):
    results=[]
    for lead in sorted({r['lead_hours'] for r in rows}):
        group=[r for r in rows if r['lead_hours']==lead]
        y=np.array([r['actual_remaining'] for r in group]);p=np.array([r['forecast_remaining'] for r in group]);b=np.array([r['constant_pace_remaining'] for r in group])
        daily=defaultdict(list)
        for r,e1,e2 in zip(group,abs(p-y),abs(b-y)):daily[r['date']].append((e1,e2,r['actual_remaining']))
        date_diff=np.array([(sum(v[0] for v in vs)-sum(v[1] for v in vs))/sum(v[2] for v in vs) for vs in daily.values() if sum(v[2] for v in vs)>0])
        rng=np.random.default_rng(20260910)
        ci=np.quantile(np.mean(rng.choice(date_diff,size=(5000,len(date_diff)),replace=True),axis=1),[.025,.975])
        results.append({'lead_hours':lead,'groups':len(group),'dates':len(daily),'clock_wape':float(abs(p-y).sum()/y.sum()),
            'constant_wape':float(abs(b-y).sum()/y.sum()),'clock_bias_fraction':float((p-y).sum()/y.sum()),
            'clock_beats_constant_groups':int(np.sum(abs(p-y)<abs(b-y))),
            'zero_observed_groups':sum(r['observed_contracts']==0 for r in group),
            'equal_date_wape_difference':float(np.mean(date_diff)),'date_bootstrap_95_difference':ci.tolist()})
    return results


def intensity(clocks):
    results=[]
    for period in ['train','test']:
        for lo,hi in [(3,6),(1,3),(.25,1),(1/60,.25)]:
            dates=defaultdict(list)
            for c in clocks:
                if c['period']!=period:continue
                selected=[b for b in c['bins'] if b['lo_hours']>=lo and b['hi_hours']<=hi]
                dates[c['date']].append([sum(b[k] for b in selected)/((hi-lo)*60) for k in ['contracts','principal','prints']])
            average=np.mean([np.mean(v,axis=0) for v in dates.values()],axis=0)
            results.append({'period':period,'lo_hours':lo,'hi_hours':hi,'contracts_per_minute':float(average[0]),
                'principal_dollars_per_minute':float(average[1]),'prints_per_minute':float(average[2])})
    return results


def run(out):
    load=lambda name:json.loads((out/(name+'.json')).read_text())
    nfl=load('volume_markouts');mlb=load('mlb_volume_clock');hedge=load('hedge_followup');same=load('samegame_history')
    inv=load('inventory_relief_conditioned')
    cohorts=[r for r in same['portfolio_bounds'] if r['scenario']=='chronological' and r['print_fraction']==1]
    early=[r for r in same['portfolio_bounds'] if r['scenario']=='chronological' and r['print_fraction']==.25]
    all_yes=[r for r in same['portfolio_bounds'] if r['scenario']=='all_legs_yes_selection']
    same_count=sum(d['counts'].get('same_game_containing',0) for d in same['daily']);distinct=sum(d['counts'].get('distinct',0) for d in same['daily'])
    result={'nfl_clock_120h':clock_curve(nfl['clocks'],120),'nfl_clock_6h':clock_curve(nfl['clocks'],6),
        'mlb_clock_6h':clock_curve(mlb['clocks'],6),
        'nfl_intensity_6h':intensity(nfl['clocks']),'mlb_intensity_6h':intensity(mlb['clocks']),
        'nfl_forecast_scores':forecast_scores(nfl['remaining_volume_forecasts']),
        'mlb_forecast_scores':forecast_scores(mlb['forecasts']),
        'samegame_summary':{'same_game_prints':same_count,'distinct_prints':distinct,'same_game_share':same_count/(same_count+distinct),
            'single_game_portfolio_prints':sum(r['prints'] for r in cohorts),
            'payout_reduction_fraction':sum(r['guaranteed_reduction_units'] for r in cohorts)/sum(r['gross_payout_units'] for r in cohorts),
            'early_payout_reduction_fraction':sum(r['guaranteed_reduction_units'] for r in early)/sum(r['gross_payout_units'] for r in early),
            'fixtures_improving_vs_first_quarter':sum(r['guaranteed_reduction_fraction']>next(e for e in early if e['fixture']==r['fixture'])['guaranteed_reduction_fraction'] for r in cohorts),
            'all_yes_reduction_fraction':sum(r['guaranteed_reduction_units'] for r in all_yes)/sum(r['gross_payout_units'] for r in all_yes)},
        'inventory':inv['results'],'balanced_markouts':hedge['balanced_markouts'],
        'hedges':hedge['hedge_sensitivities'],'predictive_checks':nfl['predictive_checks'],
        'markout_cuts':[r for r in nfl['markouts'] if r['selection']=='edge03' and r['max_age']==180],
        'samegame_bounds':same['portfolio_bounds'],'samegame_daily':same['daily'],
        'limitations':['Forecast WAPE aggregates absolute error divided by actual remaining contracts.',
            'Date bootstrap uncertainty is descriptive; NFL playoff fixtures also overlap across dates.',
            'Remaining fractions are within the stated observation window, not lifetime traded volume.',
            'Same-game pooled bound weights actual hypothetical seller contracts; not requested budgets or fill probabilities.']}
    (out/'final_analysis.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k in ['samegame_summary','nfl_forecast_scores','mlb_forecast_scores']},indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);run(p.parse_args().out)

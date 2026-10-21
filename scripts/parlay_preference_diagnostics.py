"""Bounded robustness checks on the saved preference-study feature tables."""
import argparse
import itertools
import json
from pathlib import Path

import numpy as np
import pandas as pd

from parlay_preference_study import ROOT, features, design


def matched_alternatives(probabilities,tolerance):
    observed=features(probabilities)
    alternatives=[features(p) for p in itertools.product(*[(p,1-p) for p in probabilities])]
    matched=[f for f in alternatives if abs(f['fair']-observed['fair'])<=tolerance]
    return dict(matches=len(matched),observed_favorite_share=observed['favorite_share'],
                uniform_matched_favorite_share=float(np.mean([f['favorite_share'] for f in matched])),
                observed_dispersion=observed['dispersion'],
                uniform_matched_dispersion=float(np.mean([f['dispersion'] for f in matched])))


def main():
    p=argparse.ArgumentParser();p.add_argument('--folder',type=Path,required=True);a=p.parse_args()
    d=pd.read_json(a.folder/'raw_rfq_features.jsonl.gz',lines=True)
    raw=d[d.nfl_only].copy();raw['leg_band']=pd.cut(raw.nlegs,[1,5,10,np.inf],labels=['2-5','6-10','11+']).astype(str)
    result={'nfl_request_robustness':{},'matched_alternatives':[],'forward_checks':{}}
    player_rows=raw[['creator','signature','players']].explode('players').dropna(subset=['players'])
    result['top_nfl_only_player_tokens']=[dict(token=k,rfqs=len(g),creators=int(g.creator.nunique()),
        unique_tickets=int(g.signature.nunique()),share_of_nfl_rfqs=len(g)/len(raw))
        for k,g in sorted(player_rows.groupby('players'),key=lambda kv:-len(kv[1]))[:10]]
    result['nfl_only_ne_sea_fixture_request_share']=float(raw.signature.str.contains('-26SEP09NESEA-',regex=False).mean())
    for label,f in [('requests',raw),('creator_ticket_once',raw.drop_duplicates(['creator','signature']))]:
        spend=f[f.target_cost>0].copy()
        x=np.log(spend.nlegs);y=np.log(spend.target_cost)
        rx=x-x.groupby(spend.creator).transform('mean');ry=y-y.groupby(spend.creator).transform('mean')
        slope=float((rx*ry).sum()/(rx*rx).sum())
        result['nfl_request_robustness'][label]={'rfqs':len(f),
            'leg_bands':f.leg_band.value_counts(normalize=True).to_dict(),
            'spend_positive_rfqs':len(spend),'ten_dollar_share':float((spend.target_cost==10).mean()),
            'within_creator_log_spend_log_legs_slope':slope,
            'median_requested_spend_by_legs':{str(k):float(g.target_cost.median()) for k,g in spend.groupby('leg_band')},
            'nfl_prop_same_game_intersection':float((f.has_nfl_prop & f.same_nfl_game).mean()),
            'prop_or_same_game':float((f.has_nfl_prop | f.same_nfl_game).mean())}
    result['nfl_request_robustness']['equal_creator_leg_bands']=raw.groupby('creator').leg_band.value_counts(normalize=True).unstack(fill_value=0).mean().to_dict()
    source=json.loads((ROOT/'runs/nfl_both_demand_scenarios_20260909/decisions.json').read_text())
    creator=dict(zip(d.id,d.creator))
    primary=[]
    for r in source:
        if r['status']!='scenario_priced':continue
        s=next(s for s in r['scenarios'] if s['assumed_usd_per_native_unit']==1)
        if all(l['family']=='full_game:moneyline' for l in s['legs']):
            primary.append(features([l['selected_point'] for l in s['legs']]))
    primary=pd.DataFrame(primary)
    result['priced_moneyline_only']={'rfqs':len(primary),
        'favorite_leg_share':float(np.average(primary.favorite_share,weights=primary.nlegs)),
        'all_favorite_ticket_share':float(primary.all_favorites.mean()),
        'median_implied_gross_multiple':float(primary.implied_gross_multiple.median())}
    for tolerance,cohort in itertools.product([.01,.025,.05],['all_supported','moneyline_only']):
        rows=[]
        for r in source:
            if r['status']!='scenario_priced':continue
            s=next(s for s in r['scenarios'] if s['assumed_usd_per_native_unit']==1)
            if cohort=='moneyline_only' and any(l['family']!='full_game:moneyline' for l in s['legs']):continue
            row=matched_alternatives([l['selected_point'] for l in s['legs']],tolerance)
            row['creator']=creator[r['rfq_id']];rows.append(row)
        f=pd.DataFrame(rows);g=f[f.matches>1]
        delta=g.observed_favorite_share-g.uniform_matched_favorite_share
        result['matched_alternatives'].append(dict(cohort=cohort,fair_tolerance=tolerance,rfqs=len(f),
             rfqs_with_alternatives=len(g),creators_with_alternatives=int(g.creator.nunique()),
             observed_favorite_share=float(g.observed_favorite_share.mean()),
             uniform_matched_favorite_share=float(g.uniform_matched_favorite_share.mean()),
             equal_creator_favorite_share_delta=float(delta.groupby(g.creator).mean().mean()),
             dispersion_delta=float((g.observed_dispersion-g.uniform_matched_dispersion).mean())))
    h=pd.read_csv(a.folder/'historical_features.csv.gz')
    for sport,f in h.groupby('sport'):
        days=sorted(f.day.unique());split=max(1,int(len(days)*2/3));train=f[f.day.isin(days[:split])];test=f[f.day.isin(days[split:])]
        trained_fixtures=set('|'.join(train.fixtures).split('|'))
        purged=test[~test.fixtures.map(lambda x:bool(set(x.split('|')) & trained_fixtures))]
        r={'later_prints':len(test),'fixture_disjoint_later_prints':len(purged),'scores':[]}
        for weighted in [False,True]:
            w=train.quantity.to_numpy() if weighted else np.ones(len(train));sw=np.sqrt(w)
            for model in ['learned_constant','base','composition']:
                coef=None if model=='learned_constant' else np.linalg.lstsq(design(train,model=='composition')*sw[:,None],train.edge.to_numpy()*sw,rcond=None)[0]
                for name,t in [('later',test),('fixture_disjoint_later',purged)]:
                    if not len(t):continue
                    pred=np.full(len(t),np.average(train.edge,weights=w)) if coef is None else design(t,model=='composition')@coef
                    error=t.edge.to_numpy()-pred;weights=t.quantity if weighted else None
                    r['scores'].append(dict(weighting='contracts' if weighted else 'prints',model=model,test=name,prints=len(t),
                         mse=float(np.average(error**2,weights=weights)),mae=float(np.average(abs(error),weights=weights))))
        result['forward_checks'][sport]=r
    result['interpretation']=['Matched alternatives are hypothetical complementary sides on the same fixtures, not an observed platform choice set.',
       'Uniform matched alternatives are a diagnostic null, not an economic model of customer utility.',
       'Same combo fair and leg count impose strong mathematical constraints on favorite share; report overlap.',
       'Within-creator spending regression describes requested budgets, not filled quantities or willingness to pay.',
       'Fixture-disjoint later sample removes every test ticket containing any training fixture; no NFL sample may remain.']
    (a.folder/'diagnostics.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()

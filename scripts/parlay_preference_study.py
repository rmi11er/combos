"""Bounded offline tests of parlay preference hypotheses; no execution transport.

Raw RFQ requests, priceable RFQs, and historical prints are separate populations.
Run from repo root. Output contains descriptive estimates, not IID significance.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import gzip
import hashlib
import itertools
import json
import math
from pathlib import Path
import re

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROP_FAMILIES = {'KXNFLPASSTDS','KXNFLPASSYDS','KXNFLRUSHYDS','KXNFLRSHYDS','KXNFLRECYDS',
                 'KXNFLREC','KXNFLTD','KXNFLPASSATT','KXNFLPASSCMP','KXNFLINT',
                 'KXNFLRUSHATT','KXNFLRUSHRECYDS'}


def features(probabilities):
    p=np.asarray(probabilities,dtype=float)
    if len(p)<2 or not np.isfinite(p).all() or ((p<=0)|(p>=1)).any():
        raise ValueError('invalid_leg_probabilities')
    return dict(fair=float(np.prod(p)),nlegs=len(p),favorite_share=float(np.mean(p>.5)),
                all_favorites=bool(np.all(p>.5)),weakest=float(p.min()),
                dispersion=float(p.std()),implied_gross_multiple=float(1/np.prod(p)))


def fixture(leg):
    family,_,suffix=leg['event_ticker'].partition('-')
    # Only a verified date+matchup-shaped NFL event key; futures remain unknown.
    return suffix if family.startswith('KXNFL') and re.fullmatch(r'\d{2}[A-Z]{3}\d{2}[A-Z]{4,6}',suffix) else None


def raw_features(msg):
    legs=msg.get('mve_selected_legs',[])
    nfl=[l for l in legs if l['event_ticker'].startswith('KXNFL')]
    fs=[fixture(l) for l in nfl]; known=[x for x in fs if x]
    families=[l['event_ticker'].split('-')[0] for l in nfl]
    # For negative selections retain the complement label, never silently flip a prop.
    players=sorted({l['market_ticker'].split('-')[2]+(' [NO]' if l['side']=='no' else '')
                    for l in nfl if l['event_ticker'].split('-')[0] in PROP_FAMILIES
                    and len(l['market_ticker'].split('-'))>=4})
    signature='|'.join(sorted(l['market_ticker']+':'+l['side'] for l in legs))
    creator=msg.get('creator_id')
    return dict(id=msg['id'],creator=creator,signature=signature,nlegs=len(legs),
                nfl_legs=len(nfl),nfl_only=bool(nfl) and len(nfl)==len(legs),
                has_nfl=bool(nfl),has_nfl_prop=any(f in PROP_FAMILIES for f in families),
                known_nfl_fixtures=len(set(known)),fixture_unknown_legs=len(fs)-len(known),
                same_nfl_game=len(known)>len(set(known)),
                target_cost=float(msg['target_cost_dollars']) if msg.get('target_cost_dollars') is not None else None,
                players=players,families=sorted(set(families)))


def distribution(values):
    c=Counter(values);total=sum(c.values())
    return [{'value':k,'count':v,'share':v/total} for k,v in c.most_common()]


def mix(d):
    if not len(d):return {'rfqs':0}
    creators=d.creator.dropna().value_counts()
    result={'rfqs':len(d),'creators':len(creators),'missing_creator':int(d.creator.isna().sum()),
            'unique_tickets':int(d.signature.nunique()),
            'top_creator_share':float(creators.iloc[0]/len(d)) if len(creators) else None,
            'top5_creator_share':float(creators.iloc[:5].sum()/len(d)),
            'creator_hhi':float(((creators/creators.sum())**2).sum()),
            'leg_counts':distribution(d.nlegs.astype(int)),
            'leg_bands':distribution(['2-5' if 2<=n<=5 else '6-10' if 6<=n<=10 else '11+' if n>=11 else '<2' for n in d.nlegs]),
            'spend_sized_share':float(d.target_cost.notna().mean()),
            'common_requested_spend':distribution(d.target_cost.dropna())[:12]}
    # Creator-balanced and unique creator-ticket views damp repeated RFQ traffic.
    views={'requests':d,'creator_ticket_once':d.drop_duplicates(['creator','signature'])}
    result['mix']={}
    for label,f in views.items():
        result['mix'][label]={k:float(f[k].mean()) for k in ['has_nfl_prop','same_nfl_game']}
        result['mix'][label]['n']=len(f)
    result['mix']['equal_creator']={k:float(d.dropna(subset=['creator']).groupby('creator')[k].mean().mean()) for k in ['has_nfl_prop','same_nfl_game']}
    result['top_player_tokens']=distribution(itertools.chain.from_iterable(d.players))[:15]
    result['top_family_inclusions']=distribution(itertools.chain.from_iterable(d.families))[:15]
    result['fixture_unknown_rfqs']=int((d.fixture_unknown_legs>0).sum())
    return result


def capture(hashes,out):
    folder=ROOT/'runs/nfl_both_demand_full_capture_20260909/archive'
    rows={};duplicates=0
    for p in sorted(folder.glob('*.jsonl.gz')):
        hashes[str(p.relative_to(ROOT))]=hashlib.file_digest(p.open('rb'),'sha256').hexdigest()
        with gzip.open(p,'rt') as stream:
            for line in stream:
                r=json.loads(line)
                if r['kind']!='kalshi' or r['payload'].get('type')!='rfq_created':continue
                msg=r['payload']['msg'];row=raw_features(msg);row['at']=r['received_at']
                if row['id'] in rows:duplicates+=1;continue
                rows[row['id']]=row
    d=pd.DataFrame(rows.values())
    d.to_json(out/'raw_rfq_features.jsonl.gz',orient='records',lines=True,compression='gzip')
    return d,{'all':mix(d),'nfl_containing':mix(d[d.has_nfl]),'nfl_only':mix(d[d.nfl_only]),
              'duplicate_ids_removed':duplicates,'start_utc':datetime.fromtimestamp(d['at'].min(),timezone.utc).isoformat(),
              'end_utc':datetime.fromtimestamp(d['at'].max(),timezone.utc).isoformat(),
              'duration_seconds':float(d['at'].max()-d['at'].min())}


def priced(raw,hashes,out):
    p=ROOT/'runs/nfl_both_demand_scenarios_20260909/decisions.json'
    hashes[str(p.relative_to(ROOT))]=hashlib.file_digest(p.open('rb'),'sha256').hexdigest()
    source=json.loads(p.read_text());rows=[];counts=Counter()
    for r in source:
        if r['status']!='scenario_priced':counts[r.get('reason','unknown')]+=1;continue
        for s in r['scenarios']:
            probs=[l['selected_point'] for l in s['legs']]
            f=features(probs)
            if not math.isclose(f['fair'],s['independent_combo_point'],abs_tol=1e-10):raise ValueError('fair_mismatch')
            rows.append(dict(id=r['rfq_id'],conversion=s['assumed_usd_per_native_unit'],**f))
    d=pd.DataFrame(rows).merge(raw[['id','creator','signature','target_cost']],on='id',validate='many_to_one')
    assert len(d)==len(rows),'missing raw RFQs'
    d.to_json(out/'priced_rfq_features.jsonl.gz',orient='records',lines=True,compression='gzip')
    result={'exclusions':dict(counts),'scenario_sensitivity':[]}
    for conversion,f in d.groupby('conversion'):
        result['scenario_sensitivity'].append(dict(conversion=float(conversion),rfqs=len(f),
              favorite_leg_share=float(np.average(f.favorite_share,weights=f.nlegs)),
              all_favorite_ticket_share=float(f.all_favorites.mean()),
              median_implied_gross_multiple=float(f.implied_gross_multiple.median()),
              median_fair=float(f.fair.median())))
    f=d[d.conversion==1].copy();f['band']=pd.cut(f.fair,[0,.1,.25,.4,1]).astype(str)
    result['primary_bands']=[]
    for (n,b),g in f.groupby(['nlegs','band']):
        result['primary_bands'].append(dict(nlegs=int(n),fair_band=b,rfqs=len(g),creators=int(g.creator.nunique()),
             all_favorites_share=float(g.all_favorites.mean()),favorite_share=float(g.favorite_share.mean()),
             weakest_median=float(g.weakest.median()),dispersion_median=float(g.dispersion.median())))
    result['primary_creator_balanced_favorite_share']=float(f.groupby('creator').favorite_share.mean().mean())
    result['primary_unique_creator_ticket_all_favorites']=float(f.drop_duplicates(['creator','signature']).all_favorites.mean())
    return result


def design(f,augmented=False):
    p=f.mid.to_numpy()
    cols=[np.ones(len(f)),p,p*p,p*p*p,f.sum_width.to_numpy(),np.log1p(f.hours),
          np.log1p(f.max_age),np.log1p(f.quantity),(f.nlegs==3).astype(float),(f.nlegs==4).astype(float)]
    if augmented:cols += [f.favorite_share.to_numpy(),f.weakest.to_numpy(),f.dispersion.to_numpy()]
    return np.column_stack(cols)


def fit(f,weights,day_controls=True):
    base=design(f);extra=f[['favorite_share','weakest','dispersion']].to_numpy()
    if day_controls:
        base=np.column_stack([base,pd.get_dummies(f.day,drop_first=True,dtype=float).to_numpy()])
    sw=np.sqrt(weights/np.mean(weights));y=f.edge.to_numpy();x=np.column_stack([base,extra])
    b=np.linalg.lstsq(base*sw[:,None],y*sw,rcond=None)[0]
    coef=np.linalg.lstsq(x*sw[:,None],y*sw,rcond=None)[0]
    before=np.sum(weights*(y-base@b)**2);after=np.sum(weights*(y-x@coef)**2)
    return dict(incremental_partial_r2=float(1-after/before),
                coefficients=dict(zip(['favorite_share','weakest','dispersion'],map(float,coef[-3:]))))


def historical(hashes,out):
    p=ROOT/'runs/combo_mid_spread_association_20260909/observations.csv.gz'
    hashes[str(p.relative_to(ROOT))]=hashlib.file_digest(p.open('rb'),'sha256').hexdigest()
    hist=pd.read_csv(p);wanted=set(hist.id);rows=[]
    paths=[ROOT/'runs/nfl_moneyline_replay_20260907/jan5_18/pricing_context.jsonl.gz']
    paths+=sorted((ROOT/'runs/mlb_historical_20260907/dated_fee_primary').glob('2026-07-*/replay/pricing_context.jsonl.gz'))
    for p in paths:
        hashes[str(p.relative_to(ROOT))]=hashlib.file_digest(p.open('rb'),'sha256').hexdigest()
        with gzip.open(p,'rt') as stream:
            for line in stream:
                r=json.loads(line)
                if r['evaluation_id'] not in wanted:continue
                ps=[];selections=[]
                for l,s in zip(r['legs'],r.get('sources',r.get('context'))):
                    k=s['kalshi'];v=(float(k['yes_bid'])+float(k['yes_ask']))/2
                    assert k['available_at']<=r['at']
                    ps.append(v if l['side']=='yes' else 1-v)
                    selections.append(l['market_ticker']+':'+l['side'])
                rows.append(dict(id=r['evaluation_id'],ticket='|'.join(sorted(selections)),**features(ps)))
        print('context',p.parent.parent.name,flush=True)
    d=hist.merge(pd.DataFrame(rows).drop(columns='nlegs'),on='id',validate='one_to_one')
    assert len(d)==len(hist) and np.allclose(d.mid,d.fair,atol=1e-10,rtol=0)
    d.to_csv(out/'historical_features.csv.gz',index=False,compression='gzip')
    results={}
    for sport,f in d.groupby('sport'):
        w=f.quantity.to_numpy();days=sorted(f.day.unique());split=max(1,int(len(days)*2/3))
        train=f[f.day.isin(days[:split])];test=f[f.day.isin(days[split:])]
        r=dict(prints=len(f),days=len(days),unique_tickets=int(f.ticket.nunique()),
             all_favorite_print_share=float(f.all_favorites.mean()),
             all_favorite_contract_share=float(np.average(f.all_favorites,weights=w)),
             all_favorite_unique_ticket_share=float(f.drop_duplicates('ticket').all_favorites.mean()),
             favorite_leg_share=float(np.average(f.favorite_share,weights=f.nlegs)),
             median_traded_gross_multiple=float((1/f.price).median()),
             composition_models=[],forward=[],bands=[])
        r['top_selected_markets']=distribution(itertools.chain.from_iterable(t.split('|') for t in f.ticket))[:15]
        r['top_unique_ticket_selected_markets']=distribution(itertools.chain.from_iterable(t.split('|') for t in f.ticket.unique()))[:15]
        for weighted in [False,True]:
            weights=w if weighted else np.ones(len(f))
            model=fit(f,weights);model['weighting']='contracts' if weighted else 'prints'
            # Day omission is a stability check, not an IID confidence interval.
            sensitivities=[fit(g,g.quantity.to_numpy() if weighted else np.ones(len(g)))['incremental_partial_r2']
                           for day in days for g in [f[f.day!=day]]]
            model['leave_day_out_partial_r2_range']=[min(sensitivities),max(sensitivities)]
            r['composition_models'].append(model)
            sw=np.sqrt(train.quantity.to_numpy() if weighted else np.ones(len(train)))
            for augmented in [False,True]:
                x=design(train,augmented);xt=design(test,augmented)
                coef=np.linalg.lstsq(x*sw[:,None],train.edge.to_numpy()*sw,rcond=None)[0]
                error=test.edge.to_numpy()-xt@coef
                r['forward'].append(dict(weighting=model['weighting'],model='composition' if augmented else 'base',
                     mse=float(np.average(error**2,weights=test.quantity if weighted else None)),
                     mae=float(np.average(abs(error),weights=test.quantity if weighted else None))))
        r['train_days']=days[:split];r['test_days']=days[split:]
        r['shared_fixtures']=sorted(set('|'.join(train.fixtures).split('|')) & set('|'.join(test.fixtures).split('|')))
        r['fixture_count']=len(set('|'.join(f.fixtures).split('|')))
        f=f.copy();f['band']=pd.cut(f.mid,[0,.1,.25,.4,1]).astype(str)
        for (n,b),g in f.groupby(['nlegs','band']):
            r['bands'].append(dict(nlegs=int(n),fair_band=b,prints=len(g),all_favorites_share=float(g.all_favorites.mean()),
                                 mean_gross_edge=float(np.average(g.edge,weights=g.quantity))))
        results[sport]=r
        print(sport,'models done',flush=True)
    return results


def main():
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    a.out.mkdir(parents=True,exist_ok=True);hashes={}
    raw,raw_result=capture(hashes,a.out)
    results={'raw_capture':raw_result,'priced_rfqs':priced(raw,hashes,a.out)}
    (a.out/'request_results.json').write_text(json.dumps(results,indent=2,allow_nan=False)+'\n')
    print('RFQ analysis done',flush=True)
    results['historical']=historical(hashes,a.out)
    results['input_sha256']=hashes
    results['limitations']=['No verified retail identity; RFQs are requests, not purchases.',
      'One short September capture; creator-ticket balancing does not establish independent customers.',
      'No full available-choice or outright-popularity denominator for demand preference tests.',
      'Historical YES-taker pregame distinct-game 2-4-leg moneylines; product-mid independence assumption and lagged candle books.',
      'Composition models predict gross observed premiums, not acceptance or fee-adjusted markouts.',
      'Chronological validation shares fixtures; day omission ranges are not confidence intervals.',
      'Implied multiple 1/fair is not a requested or offered payout; no round-target causal test.',
      'NFL fixture regex is restricted; unknown fixtures and unrecognized prop families are retained explicitly.']
    (a.out/'results.json').write_text(json.dumps(results,indent=2,allow_nan=False)+'\n')


if __name__=='__main__':main()

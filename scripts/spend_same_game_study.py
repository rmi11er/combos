"""Exact-spend cohorts and scalar-safe structural offset screen, archived RFQs."""
import argparse
from collections import Counter
from datetime import datetime,timezone
from decimal import Decimal
import gzip
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from combos.research_spend_risk import payout_upper,target_size
from parlay_preference_study import raw_features

DEFAULTS=['nfl_both_demand_full_capture_20260909','nfl_five_minute_capture_20260909',
          'nfl_live_markout_capture_20260909','nfl_demand_three_source_capture_20260909',
          'nfl_verified_candidate_shadow_recommended_capture_20260910b']


def cohort(amount):
    if amount is None or pd.isna(amount):return 'fixed_or_missing'
    d=Decimal(str(amount))
    return '$'+str(int(d)) if d in [Decimal(5),Decimal(10),Decimal(20),Decimal(50)] else 'other_spend'


def summarize(d):
    rows=[]
    for name,f in d.groupby('spend_cohort'):
        spend=f.target_cost.dropna()
        rows.append(dict(cohort=name,rfqs=len(f),share=len(f)/len(d),creators=int(f.creator.nunique()),
            requested_budget_sum=float(spend.sum()),median_legs=float(f.nlegs.median()),
            same_game_share=float(f.same_nfl_game.mean()),prop_share=float(f.has_nfl_prop.mean()),
            two_through_four_legs_share=float(f.nlegs.between(2,4).mean()),
            top_creator_share=float(f.creator.value_counts().iloc[0]/len(f))))
    return rows


def parse_signature(signature):
    return [tuple(s.rsplit(':',1)) for s in signature.split('|')]


def score_portfolio(f,label):
    # First creator-ticket removes repeated submissions, not independent people.
    g=f.sort_values('at').drop_duplicates(['creator','signature'])
    outputs=[]
    for fraction in [.25,.5,1.]:
        sub=g.iloc[:max(1,int(len(g)*fraction))]
        for weighting in ['unit_contract','requested_budget_weight']:
            chosen=sub if weighting=='unit_contract' else sub[sub.target_cost>0]
            if len(chosen)==0:continue
            weights=np.ones(len(chosen)) if weighting=='unit_contract' else chosen.target_cost.to_numpy()
            outputs.append(dict(cohort=label,prefix_fraction=fraction,weighting=weighting,
                **payout_upper([parse_signature(s) for s in chosen.signature],weights)))
    return outputs


def main():
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True)
    p.add_argument('--captures',nargs='+',default=DEFAULTS);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    rows=[];coverage=[];hashes={};seen=set();duplicates=0;quote_events=Counter();missing_counter=Counter()
    for name in a.captures:
        folder=ROOT/'runs'/name/'archive';paths=sorted(folder.rglob('*.jsonl.gz'));local=[]
        if not paths:raise ValueError('missing_capture:'+name)
        for path in paths:
            with path.open('rb') as f:hashes[str(path.relative_to(ROOT))]=hashlib.file_digest(f,'sha256').hexdigest()
            with gzip.open(path,'rt') as stream:
                for line in stream:
                    e=json.loads(line)
                    if e.get('kind')!='kalshi':continue
                    payload=e['payload'];kind=payload.get('type')
                    if kind in ('quote_created','quote_accepted','quote_executed'):quote_events[kind]+=1
                    if kind!='rfq_created':continue
                    m=payload['msg'];r=raw_features(m)
                    if not r['has_nfl']:continue
                    local.append(e['received_at'])
                    if r['id'] in seen:duplicates+=1;continue
                    seen.add(r['id'])
                    r.update(at=e['received_at'],capture=name,spend_cohort=cohort(m.get('target_cost_dollars')),
                             contracts=m.get('contracts_fp'),target_cost_excludes_fees=m.get('target_cost_excludes_fees'),
                             research_route='same_game_joint_review' if r['same_nfl_game'] else 'distinct_fixture_review',
                             quote_eligible=False)
                    r['score_only']=bool(r['families']) and set(r['families'])<= {'KXNFLGAME','KXNFLSPREAD','KXNFLTOTAL'}
                    if r['same_nfl_game'] and r['known_nfl_fixtures']==1:r['structure']='single_game'
                    elif r['same_nfl_game']:r['structure']='same_game_plus_other_games'
                    else:r['structure']='distinct_games'
                    missing_counter['explicit_target_fee_mode' if 'target_cost_excludes_fees' in m else 'missing_target_fee_mode']+=1
                    rows.append(r)
        coverage.append(dict(capture=name,nfl_rfqs_before_cross_capture_dedup=len(local),
            first_utc=datetime.fromtimestamp(min(local),timezone.utc).isoformat() if local else None,
            last_utc=datetime.fromtimestamp(max(local),timezone.utc).isoformat() if local else None,
            seconds=max(local)-min(local) if local else None))
        print(name,'NFL requests',len(local),flush=True)
    d=pd.DataFrame(rows).sort_values('at');d.to_json(a.out/'rfq_features.jsonl.gz',orient='records',lines=True,compression='gzip')
    pure=d[d.nfl_only].copy();sg=pure[pure.same_nfl_game]
    results=dict(coverage=coverage,input_sha256=hashes,cross_capture_duplicates=duplicates,
                 nfl_containing=len(d),nfl_only=len(pure),same_game_nfl_only=len(sg),
                 cohorts=summarize(pure),deduplicated_cohorts=summarize(pure.drop_duplicates(['creator','signature'])),
                 creator_ticket_spend_cohorts=summarize(pure.drop_duplicates(['creator','signature','spend_cohort','target_cost','contracts'])),
                 same_game_cohorts=summarize(sg),same_game_structures=sg.structure.value_counts().to_dict(),
                 by_capture={},quote_event_counts=dict(quote_events),sizing_field_coverage=dict(missing_counter))
    for capture,f in pure.groupby('capture'):
        results['by_capture'][capture]=dict(rfqs=len(f),same_game_share=float(f.same_nfl_game.mean()),cohorts=summarize(f))
    # Same-market direction measures are constraints, not a delta hedge estimate.
    signs=Counter(s for t in sg.signature for _,s in parse_signature(t))
    atoms={}
    for t in sg.signature:
        for ticker,side in parse_signature(t):atoms.setdefault(ticker,set()).add(side)
    results['same_game_directions']=dict(leg_side_counts=dict(signs),market_atoms=len(atoms),
        atoms_requested_both_sides=sum(len(v)==2 for v in atoms.values()))
    results['risk_screen']=score_portfolio(sg,'all_same_game')
    results['risk_screen']+=score_portfolio(sg[sg.spend_cohort.isin(['$5','$10','$20','$50'])],'exact_spend_same_game')
    results['same_game_routes']={}
    for name,f in [('all',sg),('exact_spend',sg[sg.spend_cohort.isin(['$5','$10','$20','$50'])])]:
        results['same_game_routes'][name]=dict(rfqs=len(f),
            two_to_four_no_recognized_props=int((f.nlegs.between(2,4)&~f.has_nfl_prop).sum()),
            two_to_four_score_only=int((f.nlegs.between(2,4)&f.score_only).sum()),
            two_to_four_with_props=int((f.nlegs.between(2,4)&f.has_nfl_prop).sum()),
            over_four=int((f.nlegs>4).sum()))
    # Explicit stress scenarios, not estimated acceptance probabilities.
    g=sg.drop_duplicates(['creator','signature']);rng=np.random.default_rng(20260909)
    results['fill_selection_stress']=[]
    for label,sub in [('uniform_10pct',g[rng.random(len(g))<.1]),
                      ('uniform_50pct',g[rng.random(len(g))<.5]),
                      ('only_all_yes_tickets',g[~g.signature.str.contains(':no',regex=False)])]:
        if len(sub):results['fill_selection_stress'].append(dict(scenario=label,
            **payout_upper([parse_signature(s) for s in sub.signature],np.ones(len(sub)))))
    results['limitations']=['RFQ requests, not observed accepted/funded inventory; no retail identity labels.',
        'Five short windows on one day, not a representative daily sample; archive names are not event timestamps.',
        'Budget weighting is hypothetical q proportional to spend at a common price, not observed contract sizing.',
        'Payout bound is a conservative relaxation; residual bound is not proven achievable loss.',
        'Matching same-market YES/NO exploits exact scalar complement semantics only; cross-market and score relationships omitted.',
        'No cash collateral relief, hedge liquidity, markouts, acceptance elasticity or quote profitability established.',
        'Research route accepts same-game structures for analysis; production quote eligibility stays false.',
        'Chronological creator-ticket dedup retains first budget; creator-ticket-spend view preserves budget changes.']
    (a.out/'results.json').write_text(json.dumps(results,indent=2,allow_nan=False)+'\n')
    sizing=[]
    for budget in [5,10,20,50]:
        for price in ['.05','.1','.25','.5']:
            for rate in ['0','.07']:
                sizing.append(dict(budget=budget,yes_ask=price,taker_rate=rate,
                    **target_size(budget,price,rate)))
    (a.out/'sizing_scenarios.json').write_text(json.dumps(sizing,indent=2,default=str)+'\n')
    print('done',len(pure),'NFL-only;',len(sg),'same-game;',a.out,flush=True)


if __name__=='__main__':main()

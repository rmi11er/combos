"""Isolated, capture-only research extension. Never edits launch configuration."""
import argparse
from dataclasses import asdict
from functools import lru_cache
from itertools import combinations, product
import json
import math
from pathlib import Path
import numpy as np
from scipy.optimize import linprog
import review_football_week_20260914 as source
import analyze_football_week_20260914 as analysis
from combos.pricing import Interval, stressed_joint_upper
from combos.joint_pricing import price_joint

BASE=source.OUT
DEST=BASE.parent/'football_unlimited_legs_20260915'


@lru_cache(maxsize=32768)
def long_bound(bounds,rho):
    """Certified upper bound; exact moment LP for <=15 legs if needed.

    Intersection of all events is contained in each pair and every subset.
    Thus subset upper bounds can certify passing without exponential states.
    An unresolved upper bound is NOT evidence that the exact statistic fails.
    """
    iv=[Interval(lo,(lo+hi)/2,hi) for lo,hi in bounds]
    independent=math.prod(v.upper for v in iv)
    upper=min(v.upper for v in iv)
    for i,j in combinations(range(len(iv)),2):
        upper=min(upper,stressed_joint_upper(iv[i],iv[j],rho))
    if 100*(upper-independent)<23.9065:
        return max(independent,upper),'pairwise_certificate',False
    subset=sorted(iv,key=lambda v:v.upper)[:4]
    upper=min(upper,price_joint(subset,rho)['stressed_upper'])
    if 100*(upper-independent)<23.9065:
        return max(independent,upper),'four_leg_subset_certificate',False
    if len(iv)>15:
        return max(independent,upper),'unresolved_conservative_subset_bound',False
    n=len(iv);states=np.array(list(product((0.,1.),repeat=n))).T
    rows=[];rhs=[]
    for i,v in enumerate(iv):
        rows.extend((states[i],-states[i]));rhs.extend((v.upper,-v.lower))
    for i,j in combinations(range(n),2):
        rows.append(states[i]*states[j]);rhs.append(stressed_joint_upper(iv[i],iv[j],rho))
    a=np.array(rows);b=np.array(rhs);c=np.zeros(2**n);c[-1]=-1
    sol=linprog(c,A_ub=a,b_ub=b,A_eq=np.ones((1,2**n)),b_eq=[1.],bounds=(0,None),method='highs',options={'time_limit':2})
    if not sol.success:return max(independent,upper),'unresolved_solver_bound',False
    y=np.minimum(sol.ineqlin.marginals,0.);z=float(sol.eqlin.marginals[0])
    correction=max(0.,float(np.max(a.T@y+z-c)))
    certified=float(-b@y-z+correction+1e-10)
    return max(independent,min(upper,certified)),'extended_exact_moment_lp',True


def research_joint(iv,rho):
    if len(iv)==1:
        return {'joint':asdict(iv[0]),'stressed_upper':iv[0].upper,
                'dependence':{'model':'single_leg_no_dependence','exact':True,'reserve_cents':0.}}
    if len(iv)<=4:return price_joint(iv,rho)
    base=Interval(*(math.prod(getattr(v,k) for v in iv) for k in ('lower','point','upper')))
    upper,method,exact=long_bound(tuple(sorted((v.lower,v.upper) for v in iv)),rho)
    return {'joint':asdict(base),'stressed_upper':upper,
            'dependence':{'model':method,'exact':exact,'reserve_cents':100*(upper-base.upper)}}


def setup():
    DEST.mkdir(parents=True,exist_ok=True)
    inputs=['traded_market_requests.json.gz','combo_metadata.json.gz','leg_metadata.json.gz',
            'fixture_starts.json','production_request_policy.json.gz','request_audit.json',
            'capture_audit.json','metadata_audit.json']
    inputs += [p.name for p in BASE.glob('tape_*.json.gz')]
    for name in inputs:
        target=DEST/name
        if not target.exists():target.symlink_to(Path('..')/BASE.name/name)
    source.OUT=DEST;analysis.OUT=DEST


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['candles','features','performance','diagnostics'])
    args=p.parse_args();setup()
    if args.stage=='candles':source.candles(max_legs=None)
    elif args.stage=='features':analysis.features(max_legs=None,joint_pricer=research_joint)
    else:getattr(analysis,args.stage)()

"""Offline spend sizing and conservative same-market payout-netting research.

No order transport or live scope override. Quote sizing is a single-fill model,
not an exchange reconciliation. Portfolio weights must be externally supplied.
"""
from decimal import Decimal, ROUND_FLOOR
import math

import numpy as np
from scipy.optimize import linprog
from scipy.sparse import coo_matrix

from .fees import kalshi_fill_fee


def target_size(budget, yes_ask, taker_rate, *, precision='.0001', excludes_fees=False):
    """Maximum .01-contract quantity under explicit requester fee assumptions."""
    b,p,r=map(lambda x:Decimal(str(x)),(budget,yes_ask,taker_rate))
    if not all(x.is_finite() for x in (b,p,r)) or b<=0 or not 0<p<1 or not 0<=r<1:
        raise ValueError('invalid_spend_inputs')
    if p % Decimal('.0001') or not isinstance(excludes_fees,bool):
        raise ValueError('invalid_price_precision_or_fee_mode')
    def debit(cents):
        if not cents:return Decimal(0)
        q=Decimal(cents)/100
        fee=kalshi_fill_fee(q,p,r,'buy',precision)['net_fee']
        return q*p+(Decimal(0) if excludes_fees else fee)
    low,high=0,int((b/p*100).to_integral_value(rounding=ROUND_FLOOR))
    while low<high:
        mid=(low+high+1)//2
        if debit(mid)<=b:low=mid
        else:high=mid-1
    q=Decimal(low)/100
    fee=kalshi_fill_fee(q,p,r,'buy',precision)['net_fee'] if q else Decimal(0)
    return {'quantity':q,'principal':q*p,'modeled_requester_fee':fee,'total_debit':q*p+fee,
            'budget_charge':debit(low),'next_quantity_budget_charge':debit(low+1),
            'target_cost_excludes_fees':excludes_fees,
            'basis':'single_full_fill; supplied requester fee/precision; no prior accumulator; exchange count must be reconciled',
            'orders_enabled':False}


def payout_upper(tickets,weights,time_limit=10):
    """Certified relaxation of sum q_i*product(selected leg settlements).

    For market settlement x in [0,1], YES=x and NO=1-x. A product of [0,1]
    numbers is <= each factor, including repeated/scalar factors. Introduce
    y_ticket <= each selected factor and maximize sum q*y. No cross-ticker
    parity, score relationships, marginal probabilities or future fills assumed.
    A repaired nonnegative dual gives an upper bound even with solver error.
    """
    if len(tickets)!=len(weights) or not tickets:raise ValueError('empty_or_mismatched_portfolio')
    w=np.asarray(weights,dtype=float)
    if not np.isfinite(w).all() or (w<=0).any():raise ValueError('invalid_weights')
    atoms=sorted({ticker for t in tickets for ticker,side in t})
    if any(not t for t in tickets) or any(s not in ('yes','no') for t in tickets for _,s in t):
        raise ValueError('invalid_ticket')
    index={v:i for i,v in enumerate(atoms)};n=len(atoms);rows=[];cols=[];data=[];b=[]
    for j,t in enumerate(tickets):
        for ticker,side in set(t):
            k=len(b);rows.extend([k,k]);cols.extend([index[ticker],n+j])
            data.extend([-1 if side=='yes' else 1,1]);b.append(0 if side=='yes' else 1)
    matrix=coo_matrix((data,(rows,cols)),shape=(len(b),n+len(tickets))).tocsr()
    objective=np.r_[np.zeros(n),w];gross=float(w.sum())
    solution=linprog(-objective,A_ub=matrix,b_ub=b,bounds=(0,1),method='highs',options={'time_limit':time_limit})
    result={'tickets':len(tickets),'market_atoms':n,'gross_payout_units':gross,
            'solver_success':bool(solution.success),'solver_message':solution.message}
    if not solution.success:
        upper=gross
    else:
        lam=np.maximum(0,-solution.ineqlin.marginals)
        residual=objective-matrix.T@lam
        upper=min(gross,float(np.dot(lam,b)+np.maximum(residual,0).sum())+1e-8*max(1,gross))
    result.update(payout_upper_units=upper,guaranteed_reduction_units=max(0,gross-upper),
                  guaranteed_reduction_fraction=max(0,1-upper/gross),
                  cash_collateral_credit=0,
                  basis='scalar-safe product upper relaxation; hypothetical requested portfolio, not observed inventory')
    return result

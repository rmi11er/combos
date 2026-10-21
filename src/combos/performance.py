"""Comparable performance curves from explicit evaluations and fill ledgers.

NO-side accounting: maker spends quantity*(1-YES price)+fee and receives
quantity*(1-YES settlement). P&L includes fees once, at settlement recognition.
An evaluation, RFQ or public print is never implicitly an execution.
"""
from collections import defaultdict
import math


def _number(value, name, minimum=None, maximum=None):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):
        raise ValueError('invalid '+name)
    if minimum is not None and value<minimum or maximum is not None and value>maximum:
        raise ValueError('out of bounds '+name)
    return value


def build_curves(evaluations, fills, start_at, end_at):
    _number(start_at,'start');_number(end_at,'end')
    if end_at<=start_at:raise ValueError('invalid reporting window')
    changes=defaultdict(lambda:defaultdict(lambda:defaultdict(float)))
    models=set();seen=set();basis=defaultdict(set)
    for row in evaluations:
        model=row['model'];key=(model,row['evaluation_id'])
        if key in seen:raise ValueError('duplicate evaluation')
        seen.add(key);models.add(model)
        at=_number(row['at'],'evaluation time');quantity=_number(row['quantity'],'quantity',0)
        price=_number(row['yes_price'],'price',0,1)
        if not start_at<=at<=end_at:raise ValueError('evaluation outside reporting window')
        d=changes[model][at]
        d['observed_yes_premium']+=quantity*price;d['observed_payout_notional']+=quantity
        d['point_edge']+=_number(row['point_edge'],'point edge')
        d['stressed_edge']+=_number(row['stressed_edge'],'stressed edge')
        d['evaluations']+=1
    seen=set()
    for row in fills:
        model=row['model'];key=(model,row['fill_id'])
        if key in seen:raise ValueError('duplicate fill')
        seen.add(key);models.add(model)
        if row['basis'] not in ('actual_execution','simulated_execution','unfiltered_public_print_reference'):
            raise ValueError('explicit execution basis required')
        basis[model].add(row['basis'])
        if len(basis[model])!=1:raise ValueError('cannot mix execution bases within a model')
        at=_number(row['filled_at'],'fill time');q=_number(row['quantity'],'quantity',0)
        p=_number(row['yes_price'],'YES price',0,1);fee=_number(row['maker_fee'],'maker fee',0)
        if q<=0 or not start_at<=at<=end_at:raise ValueError('invalid fill quantity/time')
        d=changes[model][at];cost=q*(1-p)+fee
        d['filled_yes_premium']+=q*p;d['maker_cash_spent']+=cost
        d['filled_payout_notional']+=q;d['fills']+=1;d['committed_cash']+=cost
        settled=row.get('settled_at');payoff=row.get('yes_settlement')
        if (settled is None)!=(payoff is None):raise ValueError('settlement time and payoff must be paired')
        if settled is not None:
            _number(settled,'settlement time');_number(payoff,'YES settlement',0,1)
            if settled<at:raise ValueError('settlement precedes fill')
            if settled<=end_at:
                d=changes[model][settled]
                d['realized_pnl']+=q*(p-payoff)-fee
                d['committed_cash']-=cost;d['settled_fills']+=1
    fields=('observed_yes_premium','observed_payout_notional','point_edge','stressed_edge','evaluations',
            'filled_yes_premium','maker_cash_spent','filled_payout_notional','fills','committed_cash','realized_pnl','settled_fills')
    result=[]
    for model in sorted(models):
        totals={field:0. for field in fields}
        for at in sorted({start_at,end_at,*changes[model]}):
            for field,delta in changes[model][at].items():totals[field]+=delta
            result.append({'model':model,'at':at,'execution_basis':next(iter(basis[model]),'no_executions'),**totals})
    return result

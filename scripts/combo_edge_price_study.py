"""Price dependence and robustness follow-up using the audited mid/spread join."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from combo_mid_spread_association import regression


def fit_price(d, price, weighted, adjusted):
    w = d.quantity.to_numpy() if weighted else np.ones(len(d))
    x, y = 100*d[price].to_numpy(), d.edge.to_numpy()
    cols = [np.ones(len(d))]
    if adjusted:
        cols += [d.sum_width.to_numpy(), np.log1p(d.hours), np.log1p(d.max_age), np.log1p(d.quantity)]
        for name in ('day','nlegs'):
            cols += [(d[name] == v).astype(float).to_numpy() for v in sorted(d[name].unique())[1:]]
    c=np.column_stack(cols); sw=np.sqrt(w/w.mean())
    xy=np.column_stack([x,y])
    r=xy-c@np.linalg.lstsq(c*sw[:,None],xy*sw[:,None],rcond=None)[0]
    xx,yy,xy=(np.sum(w*r[:,0]**2),np.sum(w*r[:,1]**2),np.sum(w*r[:,0]*r[:,1]))
    return {'slope_cents_per_1c_price':float(xy/xx), 'correlation':float(xy/np.sqrt(xx*yy)),
            'r2_or_partial_r2':float(xy**2/xx/yy)}


def price_bins(d, key):
    result=[]
    groups=pd.cut(100*d[key], [0,5,10,20,30,40,50,60,70,80,90,100],include_lowest=True)
    for bucket,f in d.groupby(groups,observed=True):
        w=f.quantity.to_numpy()
        order=np.argsort(f.edge.to_numpy()); v=f.edge.to_numpy()[order]; cw=np.cumsum(w[order])
        result.append({'bin':str(bucket),'x':float(np.average(100*f[key],weights=w)),
                       'mean':float(np.average(f.edge,weights=w)), 'median':float(v[np.searchsorted(cw,cw[-1]/2)]),
                       'print_median':float(f.edge.median()), 'prints':len(f),'contracts':float(w.sum()),
                       'max_single_print_weight':float(w.max()/w.sum()),
                       'mean_age':float(np.average(f.max_age,weights=w))})
    return result


def forward(d):
    days=sorted(d.day.unique()); split=max(1,int(len(days)*2/3))
    train=d[d.day.isin(days[:split])]; test=d[d.day.isin(days[split:])]
    names=['constant_0.3c','training_mean','price_cubic','mid_cubic','width_legs','mid_width_legs']
    result={'train_days':days[:split],'test_days':days[split:],'train_prints':len(train),'test_prints':len(test),'models':[]}
    result['shared_fixtures'] = sorted(set('|'.join(train.fixtures).split('|')) & set('|'.join(test.fixtures).split('|')))
    def matrix(f,name):
        cols=[np.ones(len(f))]
        if name in ['price_cubic','mid_cubic','mid_width_legs']:
            x=f.price.to_numpy() if name=='price_cubic' else f.mid.to_numpy()
            cols += [x,x*x,x*x*x]
        if name in ['width_legs','mid_width_legs']:
            cols += [f.sum_width.to_numpy(), (f.nlegs==3).to_numpy(), (f.nlegs==4).to_numpy()]
        return np.column_stack(cols)
    for weighted in [False,True]:
        wt=train.quantity.to_numpy() if weighted else np.ones(len(train))
        w=test.quantity.to_numpy() if weighted else np.ones(len(test))
        for name in names:
            if name=='constant_0.3c':
                prediction=np.full(len(test),.3)
            else:
                x=matrix(train,name); xt=matrix(test,name); sw=np.sqrt(wt/wt.mean())
                coef=np.linalg.lstsq(x*sw[:,None],train.edge.to_numpy()*sw,rcond=None)[0]
                prediction=xt@coef
            error=test.edge.to_numpy()-prediction
            result['models'].append({'model':name,'weighting':'contracts' if weighted else 'prints',
                'mse_cents_squared':float(np.average(error**2,weights=w)),
                'mae_cents':float(np.average(abs(error),weights=w))})
    return result


def main():
    p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    d=pd.read_csv(a.input)
    result={'input':str(a.input),'input_sha256':hashlib.sha256(a.input.read_bytes()).hexdigest(),
        'edge':'Gross YES seller premium in cents: 100*(trade price - product of selected leg mids).',
        'price_control_warning':'Trade price is part of edge; contemporaneous association can be mechanical. Midpoint price is the pre-quote alternative.',
        'forward_warning':'Chronological internal holdout predicts observed premiums only. Does not estimate acceptance, adverse selection or an optimal quote; no new August validation data used.',
        'results':{}}
    fig, axes=plt.subplots(2,3,figsize=(15,8),layout='constrained')
    for i,(sport,f) in enumerate(d.groupby('sport')):
        r={'prints':len(f),'price_bins':price_bins(f,'price'),'mid_bins':price_bins(f,'mid'),
           'regressions':[],'spread_sensitivity':[],'forward':forward(f)}
        for key in ['price','mid']:
            for weighted in [False,True]:
                for adjusted in [False,True]:
                    entry=dict(price_basis=key,weighting='contracts' if weighted else 'prints',adjusted=adjusted,
                               **fit_price(f,key,weighted,adjusted))
                    slopes=[fit_price(f[f.day!=day],key,weighted,adjusted)['slope_cents_per_1c_price'] for day in f.day.unique()]
                    entry['leave_day_out_slope_range']=[min(slopes),max(slopes)]
                    r['regressions'].append(entry)
        for label,sub in [('all',f),('age_le_120s',f[f.max_age<=120]),('age_le_180s',f[f.max_age<=180]),
                          ('price_le_50c',f[f.price<=.5]),('width_le_5c',f[f.sum_width<=5+1e-8])]:
            r['spread_sensitivity'].append({'cohort':label,'prints':len(sub),
                'raw':regression(sub,'sum_width',True,False)[0],
                'adjusted':regression(sub,'sum_width',True,True)[0],
                'price_raw':fit_price(sub,'price',True,False),
                'mid_raw':fit_price(sub,'mid',True,False)})
        # All bins are visible; sparse tails are labeled with sample size.
        for j,key in enumerate(['price_bins','mid_bins']):
            bins=r[key];ax=axes[i,j]
            ax.plot([b['x'] for b in bins],[b['mean'] for b in bins],'o-',label='Contract-weighted mean')
            ax.plot([b['x'] for b in bins],[b['median'] for b in bins],'s--',label='Contract-weighted median')
            for b in bins:
                if b['prints']<500: ax.annotate(f"n={b['prints']}",(b['x'],b['mean']),xytext=(-35,7),textcoords='offset points')
            ax.axhline(.3,color='gray',linestyle=':',label='0.3¢ gross reference')
            ax.set_title(sport+' · '+('traded price' if j==0 else 'midpoint-implied price'))
            ax.set_xlabel('Combo price (¢)');ax.set_ylabel('Gross premium above mid (¢)');ax.legend(fontsize=8)
            if sport=='MLB' and key=='price_bins':
                inset=ax.inset_axes([.12,.35,.61,.30])
                body=[b for b in bins if b['x']<=50]
                inset.plot([b['x'] for b in body],[b['mean'] for b in body],'o-')
                inset.plot([b['x'] for b in body],[b['median'] for b in body],'s--')
                inset.set_title('Detail: traded-price bins ≤50¢',fontsize=8)
                inset.tick_params(labelsize=7)
        ax=axes[i,2]
        # Round discrete native widths before binning to avoid floating-point splits.
        groups=pd.cut(f.sum_width.round(6),[0,2,3,4,5,10,100],include_lowest=True)
        bins=[]
        for bucket,sub in f.groupby(groups,observed=True):
            bins.append({'width_bin':str(bucket),'mean':float(np.average(sub.edge,weights=sub.quantity)), 'prints':len(sub)})
        ax.bar(range(len(bins)),[b['mean'] for b in bins],color='#397ba5')
        ax.set_xticks(range(len(bins)),[b['width_bin'] for b in bins],rotation=35,ha='right')
        ax.set_title(sport+' · native spread bins');ax.set_xlabel('Sum of leg bid/ask widths (¢)');ax.set_ylabel('Contract-weighted gross premium (¢)')
        r['spread_bins']=bins
        result['results'][sport]=r
        print(sport,'done',flush=True)
    fig.suptitle('Historical combo premiums: price and underlying spreads\nRetained pregame moneylines · gross premium before fees · prior candle books')
    fig.savefig(a.out/'price_and_spread.png',dpi=160)
    (a.out/'results.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')


if __name__=='__main__':main()

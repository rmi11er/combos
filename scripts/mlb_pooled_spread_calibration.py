#!/usr/bin/env python3
"""Pooled quantity-WLS from daily sufficient statistics, with frozen-date folds."""
import argparse
from collections import defaultdict
from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
from zoneinfo import ZoneInfo
import numpy as np
from spread_calibration_study import COMPONENTS, load_dataset, bucket, LABELS

MEASURES = ('raw', 'fee_expanded')
SPECS = ('spread_only', 'price_and_leg_count')
ZONE = ZoneInfo('America/Chicago')


def load(path):
    return json.loads(Path(path).read_text())


def digest(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()


class Moments:
    """Exact additive WLS moments (up to float summation), never daily averages."""
    def __init__(self):
        self.xx=np.zeros((6,6));self.xy=np.zeros((6,3));self.yy=np.zeros(3);self.ys=np.zeros(3)
        self.weight=0.;self.weight2=0.;self.n=0

    @classmethod
    def from_arrays(cls,x,y,w):
        s=cls();s.xx=x.T@(w[:,None]*x);s.xy=x.T@(w[:,None]*y)
        s.yy=np.sum(w[:,None]*y*y,axis=0);s.ys=np.sum(w[:,None]*y,axis=0)
        s.weight=float(w.sum());s.weight2=float(w@w);s.n=len(w);return s

    def combine(self, other, sign=1):
        result=Moments()
        for k in ('xx','xy','yy','ys','weight','weight2','n'):setattr(result,k,getattr(self,k)+sign*getattr(other,k))
        return result

    def fit(self, indices):
        if self.n == 0 or self.weight <= 0:return {'status':'no_known_outcomes'}
        a=self.xx[np.ix_(indices,indices)];b=self.xy[indices]
        scale=np.sqrt(np.maximum(np.diag(a),0))
        if np.any(scale<=0):return {'status':'rank_deficient'}
        normalized=a/np.outer(scale,scale)
        eig=np.linalg.eigvalsh(normalized)
        # Normal equations square the design condition; decline unstable fits.
        if eig[0] <= max(eig[-1]*1e-12,0):return {'status':'rank_deficient_or_ill_conditioned','scaled_gram_eigenvalues':eig.tolist()}
        beta=np.linalg.solve(normalized,b/scale[:,None])/scale[:,None]
        if not np.allclose(beta[:,0]+beta[:,1],beta[:,2],atol=1e-7):raise ValueError('coefficient_identity_failed')
        sse=self.yy-2*np.sum(beta*b,axis=0)+np.sum(beta*(a@beta),axis=0)
        sst=self.yy-self.ys*self.ys/self.weight
        r2=[float(1-max(0.,v)/t) if t>1e-20 else None for v,t in zip(sse,sst)]
        return {'status':'descriptive_only','coefficients':beta,'r_squared':r2}


class Bin:
    def __init__(self):
        self.n=0;self.known=0;self.q=0.;self.kq=0.;self.sums=np.zeros(3);self.all_comp=0.

    def add(self, row):
        q=row['quantity'];self.n+=1;self.q+=q;self.all_comp+=q*row['values']['compensation']
        if row['values']['realized'] is not None:
            self.known+=1;self.kq+=q;self.sums+=q*np.array([row['values'][c] for c in COMPONENTS])

    def report(self):
        return {'prints':self.n,'known_prints':self.known,'quantity':self.q,'known_quantity':self.kq,
                'unknown_quantity':self.q-self.kq,'components_cents':dict(zip(COMPONENTS,(self.sums/self.kq).tolist() if self.kq else [None]*3)),
                'all_priced_compensation_cents':self.all_comp/self.q if self.q else None,
                'known_net_pnl':float(self.sums[2]/100),'weighted_component_sums_cents':dict(zip(COMPONENTS,self.sums.tolist()))}


class Study:
    def __init__(self):
        self.overall=Bin();self.bins=[Bin() for _ in LABELS];self.moments=Moments();self.fixtures={};self.leg_counts=set()

    def add_day(self, rows, measure):
        for r in rows:
            if not np.isfinite(r[measure]) or r[measure]<0:raise ValueError('invalid_spread')
            self.overall.add(r);self.bins[bucket(r[measure])].add(r)
        known=[r for r in rows if r['values']['realized'] is not None]
        if not known:return
        x=np.array([[1.,r[measure],10*r['yes_price'],float(r['nlegs']==2),float(r['nlegs']==3),float(r['nlegs']==4)] for r in known])
        y=np.array([[r['values'][c] for c in COMPONENTS] for r in known]);w=np.array([r['quantity'] for r in known])
        self.leg_counts.update(r['nlegs'] for r in known)
        self.moments=self.moments.combine(Moments.from_arrays(x,y,w))
        members=defaultdict(list)
        for i,r in enumerate(known):
            for fixture in set(r['buckets']['fixture']):members[fixture].append(i)
        for f,indices in members.items():
            part=Moments.from_arrays(x[indices],y[indices],w[indices])
            self.fixtures[f]=self.fixtures.get(f,Moments()).combine(part)

    def regression(self,spec):
        terms=['intercept','spread_cents'];indices=[0,1]
        if spec=='price_and_leg_count':
            terms.append('yes_price_per_10c');indices.append(2);counts=sorted(self.leg_counts)
            for n in counts[1:]:terms.append(f'legs_{n}_vs_{counts[0]}');indices.append(n+1)
        fit=self.moments.fit(indices)
        if fit['status']!='descriptive_only':return {'terms':terms,**fit}
        slopes=[];failures={}
        for f,part in self.fixtures.items():
            remaining=self.moments.combine(part,-1)
            result=remaining.fit(indices) if remaining.n>len(indices) else {'status':'too_few_remaining_prints'}
            if result['status']!='descriptive_only':failures[f]=result['status']
            else:slopes.append(result['coefficients'][1])
        return {'status':'descriptive_only','known_prints':self.moments.n,'unique_fixtures':len(self.fixtures),'terms':terms,
                'effective_weighted_print_count_not_independent':self.moments.weight**2/self.moments.weight2,
                'leave_one_fixture_out_refits':len(slopes),'leave_one_fixture_out_failures':len(failures),'fixture_deletion_failure_reasons':failures,
                'standard_errors':None,'p_values':None,'inference':'Overlapping-fixture deletion ranges are influence diagnostics, not confidence intervals.',
                'components':{c:{'coefficients':dict(zip(terms,map(float,fit['coefficients'][:,j]))),'weighted_r_squared':fit['r_squared'][j],
                                  'spread_slope_fixture_deletion_range':[float(min(s[j] for s in slopes)),float(max(s[j] for s in slopes))] if slopes else None} for j,c in enumerate(COMPONENTS)}}

    def report(self,fold,model,measure):
        return {'dataset':fold,'cohort':'common','model':model,'measure':measure,'overall':self.overall.report(),
                'bins':[{'label':label,**b.report()} for label,b in zip(LABELS,self.bins)],
                'regressions':{s:self.regression(s) for s in SPECS}}


def certified_inputs(roots,feature_root,plan):
    """Require terminal batch day + replay hash and complete feature certificate."""
    replays={};empty=set();hashes={}
    for root in map(Path,roots):
        state_path=root/'batch_status.json'
        if not state_path.exists():continue
        state=load(state_path)
        for date,day in state.get('days',{}).items():
            if plan['dates'].get(date) not in ('development','validation'):continue
            if day.get('status')=='complete_empty_eligible_scope':
                certificate=load(root/date/'cohort/summary.json')
                if not certificate.get('complete_census') or certificate['date']!=date:raise ValueError('invalid_empty_certificate')
                empty.add(date);continue
            if day.get('status')!='complete':continue
            replay=(root/date/'replay/opportunities.json').resolve();stage=state.get('stages',{}).get(date+'/replay',{})
            expected=stage.get('output_sha256',{}).get(str(replay))
            if stage.get('status')!='complete' or not expected or digest(replay)!=expected:raise ValueError('replay_certificate_mismatch:'+date)
            if date in replays and digest(replays[date])!=expected:raise ValueError('conflicting_date')
            replays[date]=replay;hashes[str(replay)]=expected
    if empty.intersection(replays):raise ValueError('conflicting_empty_date')
    inputs={};pending={}
    for date,replay in sorted(replays.items()):
        fm=Path(feature_root)/date/'feature_manifest.json';fp=fm.parent/'features.jsonl.gz'
        if not fm.exists():pending[date]='awaiting_features';continue
        feature=load(fm)
        if feature.get('complete') is not True:pending[date]='features_incomplete';continue
        if Path(feature['replay']).resolve()!=replay or digest(fp)!=feature['features_sha256'] or feature.get('source_sha256',{}).get(str(replay))!=hashes[str(replay)]:raise ValueError('feature_certificate_mismatch:'+date)
        inputs[date]={'opportunities':str(replay),'features':str(fp.resolve())};hashes[str(fm.resolve())]=digest(fm);hashes[str(fp.resolve())]=feature['features_sha256']
    return replays,inputs,empty,pending,hashes


def retained_rows(rows,models,fold,dev_fixtures):
    by=defaultdict(set)
    for r in rows:
        if r['model'] in models:by[r['model']].add(r['evaluation_id'])
    if set(by)!=set(models):return [],0,{'missing_models':sorted(set(models)-set(by))}
    common=set.intersection(*(by[m] for m in models));purge=set()
    for r in rows:
        if r['evaluation_id'] in common and fold=='validation' and dev_fixtures.intersection(r['buckets']['fixture']):purge.add(r['evaluation_id'])
    retained=[r for r in rows if r['model'] in models and r['evaluation_id'] in common-purge]
    return retained,len(purge),{'common_before_purge':len(common),'common_after_purge':len(common-purge),'model_feature_rows':{m:len(by[m]) for m in models}}


def run(roots,feature_root,plan,include_pooled=False,only_dates=None):
    replays,inputs,empty,pending,hashes=certified_inputs(roots,feature_root,plan)
    if only_dates is not None:
        if set(only_dates)-set(plan['dates']):raise ValueError('date_not_in_frozen_plan')
        inputs={d:v for d,v in inputs.items() if d in only_dates}
    dev_fixtures=set();dev_ready=set()
    for date,path in sorted(replays.items()):
        if plan['dates'][date]!='development':continue
        data=load(path);dev_ready.add(date)
        # Purge against all replay development fixtures, including missing features.
        dev_fixtures.update(f for r in data['opportunities'] for f in r['buckets']['fixture'])
        del data
    dev_ready.update(d for d in empty if plan['dates'][d]=='development')
    required_dev={d for d,f in plan['dates'].items() if f=='development'}
    studies={};coverage={};models=plan['primary_models'];used_dates=set()
    with tempfile.TemporaryDirectory(prefix='pooled-spread-') as temp:
        db=sqlite3.connect(str(Path(temp)/'ids.sqlite'));db.execute('CREATE TABLE seen (id TEXT PRIMARY KEY, date TEXT)')
        try:
            for date,dataset in sorted(inputs.items()):
                rows,_,counts=load_dataset(dataset,hashes);fold=plan['dates'][date]
                rows,purged,cover=retained_rows(rows,models,fold,dev_fixtures)
                coverage[date]={**cover,'purged_validation_prints':purged,'fold':fold}
                if 'missing_models' in cover:continue
                used_dates.add(date);start=datetime.fromisoformat(date).replace(tzinfo=ZONE);end=start+timedelta(days=1)
                ids=set()
                for r in rows:
                    if not start.timestamp()<=r['at']<end.timestamp() or r['nlegs'] not in (2,3,4):raise ValueError('row_outside_frozen_scope')
                    ids.add(r['evaluation_id'])
                for key in ids:
                    try:db.execute('INSERT INTO seen VALUES (?,?)',(key,date))
                    except sqlite3.IntegrityError as exc:raise ValueError('duplicate_print_across_dates') from exc
                db.commit()
                for model in models:
                    selected=[r for r in rows if r['model']==model]
                    for measure in MEASURES:
                        for label in ([fold,'pooled_descriptive'] if include_pooled else [fold]):
                            key=(label,model,measure);studies.setdefault(key,Study()).add_day(selected,measure)
                del rows
        finally:db.close()
    records=[s.report(*key) for key,s in sorted(studies.items())]
    return {'records':records,'explicit_date_subset':sorted(only_dates) if only_dates else None,'coverage':coverage,'pending_features':pending,'empty_scope_dates':sorted(empty),
            'requested_dates':{d:f for d,f in plan['dates'].items() if f in ('development','validation')},
            'used_dates':sorted(used_dates),'missing_dates':sorted(d for d,f in plan['dates'].items() if f in ('development','validation') and d not in used_dates|empty),
            'validation_fixture_purge_provisional':dev_ready!=required_dev,'development_fixture_dates_ready':sorted(dev_ready),
            'development_fixture_count':len(dev_fixtures),'input_hashes':hashes,'orders_enabled':False,
            'method':'Exact pooled quantity-weighted sufficient statistics; no average of per-date regressions or bin means. All common covered prints retained, except validation fixture purge. No edge/capital/premium/outcome selection.',
            'inference':'Regression coefficients and fixture deletion ranges are descriptive, not causal effects or confidence intervals. Calendar gaps are absent observations, not zero returns. Price-control associations can be mechanical. Missing depth is not estimated by regression.',
            'fee_and_scope':'Inherited dated fee scenarios and opposite-moneyline historical feature coverage; not a full-market-universe study. Unverified historical fees remain unverified.'}


def plot(records, out, dataset, cohort, measure):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FuncFormatter
    rs = [r for r in records if r['dataset']==dataset and r['cohort']==cohort and r['measure']==measure]
    if not rs:
        return
    fig, axes = plt.subplots(2, len(rs), figsize=(6*len(rs), 7), squeeze=False, sharex=True)
    colors = {'compensation': '#0072B2', 'residual': '#D55E00', 'realized': '#222222'}
    labels = {'compensation': 'Price − fair − maker fee', 'residual': 'Fair − outcome', 'realized': 'Realized net P&L (sum)'}
    for col, r in enumerate(rs):
        bins = r['bins']; x = list(range(len(bins)))
        for c in COMPONENTS:
            y = [b['components_cents'][c] if b['known_prints']>=30 else float('nan') for b in bins]
            axes[0, col].plot(x, y, marker='o', color=colors[c], label=labels[c])
            for i, b in enumerate(bins):
                if 0 < b['known_prints'] < 30:
                    axes[0, col].scatter(i, b['components_cents'][c], facecolors='none', edgecolors=colors[c])
        axes[0, col].axhline(0, color='#888888', lw=.7)
        axes[0, col].set_title(f"{r['model']} · {r['overall']['prints']:,} prints")
        axes[0, col].set_ylabel('Quantity-weighted cents / contract')
        axes[0, col].legend(fontsize=8)
        axes[1, col].bar(x, [b['known_quantity'] for b in bins], color='#7EA7BE', label='Known outcomes')
        axes[1, col].bar(x, [b['unknown_quantity'] for b in bins], bottom=[b['known_quantity'] for b in bins], color='#BBBBBB', hatch='//', label='Unknown outcomes')
        axes[1, col].set_ylabel('Payout notional ($)')
        axes[1, col].yaxis.set_major_formatter(FuncFormatter(lambda v, _: f'${v/1e6:.1f}m' if abs(v)>=1e6 else f'${v/1000:.0f}k'))
        axes[1, col].set_xticks(x, LABELS)
        axes[1, col].set_xlabel('Sum of leg spreads (cents) · unequal buckets')
        axes[1, col].legend(fontsize=8)
        for ax in axes[:, col]:
            ax.grid(axis='y', alpha=.2)
    fig.suptitle(f'{dataset} · {cohort} · {measure.replace("_", " ")} spread decomposition', fontsize=13)
    fig.text(.04, .025, 'No edge, quote or capital filter. All three top components use identical known-outcome prints and quantity weights. Hollow points: <30 known prints.\n'
             'Negative fair − outcome hurts sellers; it does not establish toxicity. Realized P&L = compensation + residual. No spread reserve is charged.\n'
             'Pooled observed dates only; shared fixtures and dated fee assumptions limit inference. Validation purge and missing dates: see report.', fontsize=9)
    fig.tight_layout(rect=(0, .13, 1, .94))
    for ext in ('png', 'svg'):
        fig.savefig(out/f'{dataset}_{cohort}_{measure}.{ext}', dpi=150)
    plt.close(fig)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--batch-root',action='append',type=Path,required=True);p.add_argument('--feature-root',type=Path,required=True);p.add_argument('--plan',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--include-pooled',action='store_true');p.add_argument('--date',action='append',help='Optional explicit smoke-test dates; plan and coverage remain unchanged.');p.add_argument('--once',action='store_true',help='Single run (the only execution mode).');a=p.parse_args()
    result=run(a.batch_root,a.feature_root,load(a.plan),a.include_pooled,a.date);result['input_hashes'][str(a.plan.resolve())]=digest(a.plan);result['script_sha256']=digest(Path(__file__));result['dependency_hashes']={str(Path(__file__).with_name(name).resolve()):digest(Path(__file__).with_name(name)) for name in ('spread_calibration_study.py','spread_profitability.py')}
    a.out.mkdir(parents=True,exist_ok=True);(a.out/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    for fold in sorted({r['dataset'] for r in result['records']}):
        for measure in MEASURES:plot(result['records'],a.out,fold,'common',measure)
    lines=['# Pooled MLB spread calibration','',result['method'],'',result['inference'],'',result['fee_and_scope'],'',f"Used dates: {', '.join(result['used_dates']) or 'none'}. Missing planned dates: {len(result['missing_dates'])}. Validation fixture purge provisional: {result['validation_fixture_purge_provisional']}.",'','| Fold / model | Prints | Compensation (c) | Residual (c) | Realized (c) |','|---|---:|---:|---:|---:|']
    for r in result['records']:
        if r['measure']!='raw':continue
        s=r['overall'];v=s['components_cents'];fmt=lambda x:'N/A' if x is None else f'{x:+.4f}'
        lines.append(f"| {r['dataset']} / {r['model']} | {s['known_prints']:,} | {fmt(v['compensation'])} | {fmt(v['residual'])} | {fmt(v['realized'])} |")
    lines+=['','All coefficients, bin quantity sums, rank failures and per-fixture deletion slope ranges are in results.json. Sufficient-statistic fits decline ill-conditioned designs rather than regularizing them. The validation purge removes any combo touching a fixture present anywhere in a certified development replay, even when that fixture lacks spread features. Results remain provisional until all development dates are certified; overall study coverage remains incomplete until all planned dates are ready.']
    (a.out/'REPORT.md').write_text('\n'.join(lines)+'\n');print(json.dumps({'used_dates':result['used_dates'],'records':len(result['records']),'missing_dates':len(result['missing_dates']),'purge_provisional':result['validation_fixture_purge_provisional']}))


if __name__=='__main__':main()

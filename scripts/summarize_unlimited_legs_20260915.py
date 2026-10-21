"""Comparison, feature cohorts, and independent checks for unlimited-leg research."""
from collections import Counter
import gzip
import hashlib
import json
import math
from pathlib import Path
import review_unlimited_legs_20260915 as run
import analyze_football_week_20260914 as a
from combos.pricing import short_yes_economics


def load(path):
    if str(path).endswith('.gz'):
        with gzip.open(path,'rt') as f:return json.load(f)
    return json.loads(path.read_text())


def metrics(rows, allocated=False):
    q=sum(r['q'] for r in rows);cost=sum(r['cost'] for r in rows)
    result={'n':len(rows),'contracts':q,'collateral':cost,'pnl':sum(r['pnl'] for r in rows),
            'fixtures':len({f for r in rows for f in r['fixtures']}),
            'net_edge_cents':sum(r['model_ev'] if allocated else r['q']*r['net_edge_cents']/100 for r in rows)*100/q if q else None,
            'realized_cents':100*sum(r['pnl'] for r in rows)/q if q else None}
    for h in (60,300):
        marked=[r for r in rows if 'fair_move_'+str(h)+'_cents' in r];mq=sum(r['q'] for r in marked)
        result['mark_'+str(h)]={'n':len(marked),'cents':sum((100*r['model_ev'] if allocated else r['q']*r['net_edge_cents'])-r['q']*r['fair_move_'+str(h)+'_cents'] for r in marked)/mq if mq else None}
    return result


def timeline(rows):
    events=sorted([(r['at'],1,r['cost'],0) for r in rows]+[(r['settled_at'],0,-r['cost'],r['pnl']) for r in rows])
    cash=0.;pnl=0.;points=[]
    for t,kind,delta,gain in events:
        cash+=delta;pnl+=gain;points.append([t,round(cash,4),round(pnl,4)])
    return points


def main():
    run.setup();out=run.DEST;rows=a.read('priced_trades.json.gz');observed=a.read('observed_football_trades.json.gz')
    native=a.read('leg_metadata.json.gz');history=a.Candles()
    maps={m['kalshi_ticker']:m for m in load(a.ROOT/'config/runtime_nfl_authorized_shadow_20260910.json')['mappings']}
    for r in rows:r['risk_legs'],r['moneyline_eligible']=a.risk_identity(r,native,maps)
    starts=load(out/'fixture_starts.json')['starts']
    for r in rows:r['hours_to_first_kickoff']=(min(starts[f] for f in r['fixtures'])-r['quote_forecast_at'])/3600
    original={r['id']:r for r in load(run.BASE/'priced_trades.json.gz')}
    short={r['id']:r for r in rows if 2<=r['leg_count']<=4}
    assert set(short)==set(original),'Historical short-leg input coverage changed'
    for k,r in short.items():
        for field in ['fair','quote_proxy_eligible','tail_pass','mean_width_cents','max_width_cents','net_edge_cents']:
            assert r[field]==original[k][field],(k,field)
    comparison={};chart={};verification={'short_leg_input_parity':len(short),'portfolios':{}}
    allfills={}
    dimensions={
        'legs':('leg_count',[(1,3,'2'),(3,4,'3'),(4,5,'4'),(5,7,'5–6'),(7,11,'7–10'),(11,1000,'11+')]),
        'width':('mean_width_cents',[(0,1,'<1c'),(1,3,'1–3c'),(3,5,'3–5c'),(5,101,'5c+')]),
        'fair':('fair',[(0,.01,'<1%'),(.01,.05,'1–5%'),(.05,.2,'5–20%'),(.2,.5,'20–50%'),(.5,1.01,'50%+')]),
        'volume':('mean_candle_volume',[(0,1e-12,'Zero'),(1e-12,10,'0–10'),(10,100,'10–100'),(100,float('inf'),'100+')]),
        'lead_time':('hours_to_first_kickoff',[(0,6,'<6h'),(6,24,'6–24h'),(24,72,'1–3d'),(72,float('inf'),'3d+')])}
    for sport in ('CFB','NFL'):
        cohort=sorted([r for r in rows if r['sport']==sport],key=lambda r:(r['at'],r['id']))
        oldrows=[r for r in cohort if 2<=r['leg_count']<=4]
        scenarios={'limited':oldrows,'unlimited':cohort}
        unresolved=[r for r in cohort if 'unresolved' in r['tail_bound_method']]
        if unresolved:
            scenarios['unresolved_pass_sensitivity']=[dict(r,tail_pass=True) if 'unresolved' in r['tail_bound_method'] else r for r in cohort]
        results={};fillsets={}
        for name,xs in scenarios.items():
            result,fills,curve=a.simulate(xs,history,name,net=True)
            results[name]=result;fillsets[name]=fills;allfills[sport+'_'+name]=fills
            a.write(sport+'_'+name+'_fills.json.gz',fills)
            a.write(sport+'_'+name+'_timeline.json',timeline(fills))
            assert len({r['id'] for r in fills})==len(fills)
            assert result['peak_committed_dollars']<=10000+1e-7 and result['peak_fixture_conditional_risk_dollars']<=1000+1e-7
            for r in fills:
                e=short_yes_economics(r['q'],r['price'],r['fair'],r['rate'])
                assert e['maximum_loss']<=250+1e-9
                assert e['expected_edge']/r['q']>=.003-1e-12
                assert r['price']<=r['public_price']+1e-12 and .25<=r['request_lag']<=3
                assert abs(r['q']*(1-r['settlement'])-r['cost']-r['pnl'])<1e-7
            verification['portfolios'][sport+'_'+name]=len(fills)
        previous=load(run.BASE/(sport+'_payoff_current_filters_fills.json.gz'))
        assert {r['id'] for r in previous}=={r['id'] for r in fillsets['limited']}
        oldids={r['id'] for r in fillsets['limited']};newids={r['id'] for r in fillsets['unlimited']}
        added=[r for r in fillsets['unlimited'] if r['id'] not in oldids];removed=[r for r in fillsets['limited'] if r['id'] not in newids]
        near=[r for r in cohort if r['quote_proxy_eligible']]
        obs=[r for r in observed if r['sport']==sport and r['side']=='yes']
        ex=Counter(r.get('replay_exclusion','priced') for r in obs)
        wide_stats={'priced':len(cohort),'recent_rfq':len(near),'methods':dict(Counter(r['tail_bound_method'] for r in cohort)),
                    'unresolved_priced':len(unresolved),'unresolved_recent':sum(r['quote_proxy_eligible'] for r in unresolved)}
        feature={}
        for dimension,(field,bins) in dimensions.items():
            feature[dimension]=[{'label':label,'public':metrics([r for r in near if lo<=r[field]<hi]),
                                 'allocated':metrics([r for r in fillsets['unlimited'] if lo<=r[field]<hi],True)} for lo,hi,label in bins]
        groups=sorted({f for r in fillsets['unlimited'] for f in r['fixtures']})
        concentration=[{'fixture':f,'pnl_without':sum(r['pnl'] for r in fillsets['unlimited'] if f not in r['fixtures']),
                        'involved':sum(f in r['fixtures'] for r in fillsets['unlimited'])} for f in groups]
        comparison[sport]={'scenarios':results,'exclusions':dict(ex),'tail_audit':wide_stats,
            'added_allocations':metrics(added,True),'removed_allocations':metrics(removed,True),
            'allocation_leg_counts':dict(Counter(r['leg_count'] for r in fillsets['unlimited'])),
            'features':feature,'fixture_exclusions':concentration,
            'quote_markouts':metrics(fillsets['unlimited'],True)}
        # Common chronology for both curves, including settlement releases.
        chart[sport]={'features':feature,'timelines':{k:timeline(v) for k,v in fillsets.items()},
                      'summary':{k:{field:v[field] for field in ['prints','peak_committed_dollars','model_ev_dollars','settled_seller_pnl_dollars']} for k,v in results.items()}}
    for r in rows:
        assert r['distinct_fixtures']
        assert all(t+60<=r['quote_forecast_at'] and r['quote_forecast_at']-t<=180 for t in r['candle_ends'])
        assert all(starts[f]>r['at']+60 for f in r['fixtures'])
        assert not any('-26SEP14' in t and t.startswith('KXNFL') for t,side,*_ in r['legs'])
    verification['priced_forecasts']=len(rows);verification['passed']=True
    paths=[Path(__file__),Path(run.__file__),Path(a.__file__),Path(run.source.__file__),a.ROOT/'config/runtime_nfl_authorized_shadow_20260910.json',a.ROOT/'src/combos/joint_pricing.py']
    verification['source_sha256']={str(p.relative_to(a.ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    inputs=[p for p in out.iterdir() if p.is_symlink() or p.name.startswith('candles_')]
    verification['input_sha256']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
    for key,result in load(out/'performance_summary.json').items():
        fills=a.read(key+'_fills.json.gz')
        assert len({r['id'] for r in fills})==len(fills)==result['prints']
        assert abs(sum(r['pnl'] for r in fills)-result['settled_seller_pnl_dollars'])<1e-7
        assert result['peak_committed_dollars']<=10000+1e-7
        assert result['peak_fixture_conditional_risk_dollars']<=1000+1e-7
        for r in fills:
            e=short_yes_economics(r['q'],r['price'],r['fair'],r['rate'])
            assert e['maximum_loss']<=250+1e-9
            assert e['expected_edge']/r['q']+1e-12>=r['required_edge_cents']/100
            assert r['price']<=r['public_price']+1e-12
        verification['portfolios'][key]=len(fills)
    a.write('comparison.json',comparison);a.write('chart_data.json',chart);a.write('verification.json',verification)
    print(json.dumps({sp:{k:{f:v[f] for f in ['prints','no_collateral_dollars','peak_committed_dollars','model_ev_dollars','settled_seller_pnl_dollars','maximum_settled_equity_drawdown','rejects']} for k,v in comparison[sp]['scenarios'].items()} for sp in comparison},indent=2))


if __name__=='__main__':main()

#!/usr/bin/env python3
"""Historical MLB model opportunities with explicit three-source prerequisites.

The optional Pinnacle bundle contains exact native leg mappings and both raw
outcome histories. Missing Pinnacle produces unavailable models, never a blend
silently renormalized onto the exchanges. Public prints are capacity scenarios.
"""
import argparse
from collections import Counter
from dataclasses import asdict
from decimal import Decimal
from functools import lru_cache
import gzip
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from combos.kalshi_history import KalshiHistory
from combos.historical_fair import History,historical_observations,compare_fairs
from combos.pricing import Interval,fee_expanded_book,pinnacle_fair
from combos.joint_pricing import price_joint
from combos.weighted_fair import WeightPolicy
from combos.fees import kalshi_fill_fee
from mlb_exchange_acquire import stamp,loadgz,identity,unsupported_identity_legs,IDENTITY_POLICY_VERSION
from mlb_historical_fees import load_fee_scenario, require_coverage, kalshi_rate


def selected(interval,side):
    if side=='yes':return interval
    if side=='no':return Interval(1-interval.upper,1-interval.point,1-interval.lower)
    raise ValueError('invalid_selected_side')


def risk_buckets(legs,native):
    """Conservative gross exposure; opposite ML contracts share one bucket.

    No cross-ticket hedge credit is inferred. Opposing spread contracts share
    a score-difference threshold only where their binary partitions coincide.
    """
    keys=[];fixtures=[]
    for leg in legs:
        ticker=leg['market_ticker'];m=native[ticker];series,token=ticker.split('-')[:2]
        _,teams=identity(ticker);fixture='mlb:'+token;fixtures.append(fixture)
        if series=='KXMLBGAME':key=fixture+':winner'
        elif series=='KXMLBTOTAL':key=fixture+':total:'+str(m['floor_strike'])
        elif series=='KXMLBSPREAD':
            import re
            team=re.match('[A-Z]+',ticker.split('-')[2]).group()
            threshold=float(m['floor_strike'])*(1 if team==teams[0] else -1)
            key=fixture+':away_minus_home:'+str(threshold)
        else:raise ValueError('unsupported_risk_family')
        keys.append(key)
    combo=hashlib.sha256(json.dumps(sorted((l['market_ticker'],l['side']) for l in legs)).encode()).hexdigest()
    return {'contract':sorted(set(keys)),'fixture':sorted(set(fixtures)),'combo':[combo]}


class SourceFairs:
    def __init__(self,exchange,pinnacle_bundle=None,depth=1000.,delay=30.,fee_scenario=None):
        self.exchange=exchange;self.kalshi=KalshiHistory(exchange,fallback_dirs=[],taker_rate=.035)
        self.fee_scenario=fee_scenario
        mapping=exchange/'polymarket_mapping_reviewed.json'
        if not mapping.exists():raise ValueError('reviewed_polymarket_mapping_required')
        self.maps=json.loads(mapping.read_text());self.pm={};self.pin={};self.depth=depth;self.delay=delay
        if pinnacle_bundle:
            bundle=json.loads(pinnacle_bundle.read_text())
            if bundle.get('schema_version')!=1 or bundle.get('sport')!='mlb':raise ValueError('invalid_Pinnacle_bundle')
            for row in bundle['mappings']:
                if row.get('mapping_scope')!='ordinary_completed_game_only' or not row.get('mapping_reference'):
                    raise ValueError('explicit_historical_Pinnacle_mapping_required')
                if row['kalshi_ticker'] in self.pin:raise ValueError('duplicate_Pinnacle_mapping')
                coverage=row.get('coverage',{})
                if (coverage.get('complete') is not True or not coverage.get('source_reference') or
                    not isinstance(coverage.get('start_at'),(int,float)) or not isinstance(coverage.get('end_at'),(int,float)) or
                    not math.isfinite(coverage['start_at']) or not math.isfinite(coverage['end_at']) or
                    coverage['start_at']>=coverage['end_at']):
                    raise ValueError('verified_Pinnacle_history_request_coverage_required')
                self.pin[row['kalshi_ticker']]=(row,History(row['yes_history'],'createdAt'),History(row['no_history'],'createdAt'))

    @lru_cache(maxsize=20000)
    def fair(self,ticker,at):
        available={};context={};errors={}
        if self.fee_scenario:
            krate,kbasis=kalshi_rate(self.fee_scenario,ticker,at,'leg_taker')
        else:
            krate=.035;kbasis={'reference':'Legacy September MLB .035 assumption; historical effective date unverified','verified':False}
        try:
            k=self.kalshi.at(ticker,at);ki=fee_expanded_book(k['yes_bid'],k['yes_ask'],krate)
            k['interval']=asdict(ki);k['fee_basis']={'taker_rate':krate,**kbasis}
            available['kalshi']=(ki,True,1.);context['kalshi']=k
        except ValueError as exc:errors['kalshi']=str(exc);k=None
        m=self.maps.get(ticker,{})
        try:
            if m.get('status')!='matched':raise ValueError('exact_PM_mapping_missing')
            if ticker not in self.pm:
                env=loadgz(self.exchange/'polymarket'/(m['token']+'.json.gz'))
                if env.get('status')!=200:raise ValueError('PM_history_http_error')
                self.pm[ticker]=(History(env['payload']['history'],'t'),env['params'])
            history,params=self.pm[ticker]
            if not params['startTs']<=at-60<=params['endTs']:raise ValueError('uncovered_PM_timestamp')
            pt,pr=history.latest(at,60)
            if k is None:raise ValueError('K_spread_required_for_historical_PM_proxy')
            point=float(pr['p']);half=min((k['yes_ask']-k['yes_bid'])/2,point,1-point)
            pmrate=(self.fee_scenario['polymarket_taker_rate'] if self.fee_scenario and
                    self.fee_scenario['polymarket_rate_policy']=='fixed_scenario' else m['fee_rate'])
            pi=fee_expanded_book(point-half,point+half,pmrate)
            available['polymarket']=(pi,True,1.)
            context['polymarket']={'state_at':pt,'available_at':pt+60,'interval':asdict(pi),'fee_rate':pmrate,
                 'fee_scenario':self.fee_scenario,
                 'depth_basis':'historical_equal_K_assumed','spread_basis':'historical_K_raw_spread_proxy',
                 'mapping':m,'price_semantics':'archived_price_point_not_verified_book_midpoint'}
        except (ValueError,FileNotFoundError,KeyError) as exc:errors['polymarket']=str(exc)
        # Fixed validation variants blend leg probabilities before joint pricing.
        # They require both sources and are never represented as three-way fairs.
        for model,pmweight in (('exchange_blend_equal',.5),('exchange_blend_pm75',.75)):
            if 'kalshi' not in available or 'polymarket' not in available:
                errors[model]='two_exchange_intersection_missing'
                continue
            left,right=available['kalshi'][0],available['polymarket'][0]
            interval=Interval(*(getattr(left,key)*(1-pmweight)+getattr(right,key)*pmweight
                                for key in ('lower','point','upper')))
            available[model]=(interval,True,1.)
            context[model]={'interval':asdict(interval),'weights':{'kalshi':1-pmweight,'polymarket':pmweight},
                            'weight_basis':'fixed_preregistered_research_variant_not_measured_liquidity',
                            'required_sources':['kalshi','polymarket']}
        try:
            if ticker not in self.pin:raise ValueError('Pinnacle_MLB_history_unavailable')
            spec,yes,no=self.pin[ticker]
            if not spec['coverage']['start_at']<=at-self.delay<=spec['coverage']['end_at']:
                raise ValueError('uncovered_Pinnacle_timestamp')
            yt,yr=yes.latest(at,self.delay);nt,nr=no.latest(at,self.delay)
            pin=pinnacle_fair(yr['price'],nr['price']);available['pinnacle']=(pin,True,1.)
            context['pinnacle']={'mapping_reference':spec['mapping_reference'],'side_times':[yt,nt],'interval':asdict(pin)}
            if k is None or 'polymarket' not in available:raise ValueError('three_venue_intersection_missing')
            kr={'yes_bid':{'close_dollars':k['yes_bid']},'yes_ask':{'close_dollars':k['yes_ask']}}
            records=historical_observations(ticker,(k['source_at'],kr),(pt,pr),(yt,yr,nt,nr),at,
                                            depth=self.depth,delay=self.delay,pm_fee=pmrate)
            records[0].update(taker_rate=krate,fee_reference=kbasis['reference'])
            for model,strong in [('blend',False),('stronger_pinnacle',True)]:
                result,_=compare_fairs(records,stronger=strong)
                available[model]=(Interval(**result['fair']),result['guard']['quote_allowed'],result['guard']['risk_multiplier'])
                context[model]=result
        except (ValueError,KeyError) as exc:
            for model in ('pinnacle','blend','stronger_pinnacle'):
                if model not in available:errors[model]=str(exc)
        return available,context,errors


@lru_cache(maxsize=20000)
def joint(intervals):return price_joint(list(intervals),.05)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--cohort',type=Path,default=ROOT/'runs/mlb_historical_20260907/cohort')
    p.add_argument('--exchange',type=Path,default=ROOT/'runs/mlb_historical_20260907/exchange')
    p.add_argument('--out',type=Path,default=ROOT/'runs/mlb_historical_20260907/replay')
    p.add_argument('--pinnacle-bundle',type=Path)
    p.add_argument('--fee-scenario',type=Path,help='Dated fee policy; defaults to cohort/fee_scenario.json when present')
    args=p.parse_args();args.out.mkdir(parents=True,exist_ok=True)
    native=loadgz(args.cohort/'underlying_markets.json.gz');markets=loadgz(args.cohort/'combo_markets.json.gz')
    fee_path=args.fee_scenario or (args.cohort/'fee_scenario.json' if (args.cohort/'fee_scenario.json').exists() else None)
    fee_scenario=load_fee_scenario(fee_path) if fee_path else None
    cohort_summary=json.loads((args.cohort/'summary.json').read_text()) if (args.cohort/'summary.json').exists() else {}
    if cohort_summary.get('complete_census') and fee_scenario is None:
        raise ValueError('dated_daily_cohort_requires_explicit_fee_scenario')
    provider=SourceFairs(args.exchange,args.pinnacle_bundle,1000.,30.,fee_scenario)
    models=('kalshi','polymarket','exchange_blend_equal','exchange_blend_pm75','pinnacle','blend','stronger_pinnacle')
    exclusions={m:Counter() for m in models};scope=Counter();rows=[];eligible=0
    source_windows=set()
    with gzip.open(args.cohort/'candidate_trades.jsonl.gz','rt') as f, gzip.open(args.out/'pricing_context.jsonl.gz','wt') as ctx:
        for line in f:
            r=json.loads(line);c=r['classification'];t=r['trade'];at=stamp(t['created_time'])
            source_windows.add(tuple(r['source_window']))
            if fee_scenario:require_coverage(fee_scenario,at)
            if t.get('taker_outcome_side',t.get('taker_side'))!='yes':scope['opposite_print_direction']+=1;continue
            if not 2<=c['nlegs']<=4:scope['outside_2_to_4_model_scope']+=1;continue
            if not c['distinct_fixtures']:scope['same_fixture_joint_model_required']+=1;continue
            if c['earliest_scheduled_start'] is None or at>=c['earliest_scheduled_start']-60:
                scope['pregame_60_second_cutoff']+=1;continue
            legs=markets[t['ticker']]['mve_selected_legs']
            if any(native[l['market_ticker']].get('strike_type') not in ('structured','greater') for l in legs):
                scope['unreviewed_strike_type']+=1;continue
            if any(l['market_ticker'].startswith(('KXMLBSPREAD','KXMLBTOTAL')) and
                   float(native[l['market_ticker']]['floor_strike'])%1!=.5 for l in legs):
                scope['non_binary_integer_threshold']+=1;continue
            if any(native[l['market_ticker']].get('close_time') and stamp(native[l['market_ticker']]['close_time'])<=at for l in legs):
                scope['native_already_closed']+=1;continue
            eligible+=1
            unsupported=unsupported_identity_legs(legs)
            if unsupported:
                scope['unsupported_exhibition_identity']+=1
                for model in models:exclusions[model]['unsupported_exhibition_identity']+=1
                ctx.write(json.dumps({'evaluation_id':t['trade_id'],'at':at,'legs':legs,'context':[],'pricing_block_reason':'unsupported_exhibition_identity','unsupported_legs':unsupported,'identity_policy_version':IDENTITY_POLICY_VERSION},separators=(',',':'))+'\n')
                continue
            fairs=[provider.fair(l['market_ticker'],at) for l in legs]
            q=float(t['count_fp']);price=float(t['yes_price_dollars'])
            if not 0<price<1:scope['boundary_price']+=1;continue
            settlement_at=r['settlement_at'];settlement=r['settlement_value']
            if settlement_at is not None and settlement_at<=at:scope['settlement_before_print']+=1;continue
            maker_fee=r['maker_fee_dollars'];maker_fee_basis=r['fee_basis']
            if fee_scenario:
                rate,basis=kalshi_rate(fee_scenario,t['ticker'],at,'combo_maker')
                maker_fee=float(kalshi_fill_fee(Decimal(t['count_fp']),1-Decimal(t['yes_price_dollars']),str(rate))['net_fee'])
                maker_fee_basis={'rate':rate,**basis}
            base={'evaluation_id':t['trade_id'],'at':at,'quantity':q,'yes_price':price,'maker_fee':maker_fee,
                 'settled_at':settlement_at,'yes_settlement':settlement,'buckets':risk_buckets(legs,native),
                 'source':{'nlegs':c['nlegs'],'sampling_method':r['sampling_method'],'source_window':r['source_window'],
                           'series':c['series'],'combo_ticker':t['ticker'],'start_at':c['earliest_scheduled_start'],
                           'schedule_basis':c['start_basis'],'fee_basis':maker_fee_basis}}
            for model in models:
                missing=[entry[2].get(model,'source_unavailable') for entry in fairs if model not in entry[0]]
                if missing:exclusions[model].update(missing);continue
                values=[selected(entry[0][model][0],leg['side']) for entry,leg in zip(fairs,legs)]
                result=joint(tuple(values))
                rows.append({**base,'model':model,'fair_point':result['joint']['point'],'stressed_upper':result['stressed_upper'],
                     'quote_allowed':all(entry[0][model][1] for entry in fairs),
                     'risk_multiplier':min(entry[0][model][2] for entry in fairs)})
            ctx.write(json.dumps({'evaluation_id':t['trade_id'],'at':at,'legs':legs,'context':[f[1] for f in fairs]},separators=(',',':'))+'\n')
            if eligible%1000==0:print(json.dumps({'evaluated':eligible,'model_rows':len(rows)}),flush=True)
    identity_paths=[args.cohort/'candidate_trades.jsonl.gz',args.cohort/'underlying_markets.json.gz',args.cohort/'combo_markets.json.gz',
                    args.exchange/'polymarket_mapping_reviewed.json',Path(__file__)]
    identity_paths += [ROOT/'src/combos'/name for name in ('kalshi_history.py','historical_fair.py','pricing.py',
        'joint_pricing.py','weighted_fair.py','observations.py','fees.py')]
    identity_paths += [ROOT/'scripts/mlb_exchange_acquire.py']
    identity_paths += sorted((args.exchange/'kalshi_parts').glob('*.gz'))+sorted((args.exchange/'polymarket').glob('*.gz'))
    if args.pinnacle_bundle:identity_paths.append(args.pinnacle_bundle)
    if fee_path:identity_paths.append(fee_path)
    identity_paths.append(ROOT/'scripts/mlb_historical_fees.py')
    manifest={'identity_policy_version':IDENTITY_POLICY_VERSION,'input_sha256':{str(x):hashlib.sha256(x.read_bytes()).hexdigest() for x in identity_paths},
              'historical_only':True,'Pinnacle_bundle_provided':args.pinnacle_bundle is not None,
              'delay_seconds':30,'shared_historical_depth':1000,'exception_rules_verified':False,
              'fee_scenario':fee_scenario,
              'fixed_exchange_blends':{'exchange_blend_equal':{'kalshi':.5,'polymarket':.5},
                                       'exchange_blend_pm75':{'kalshi':.25,'polymarket':.75}}}
    start_at=min((w[0] for w in source_windows),default=cohort_summary.get('start_at'))
    end_at=max((w[1] for w in source_windows),default=cohort_summary.get('end_at'))
    if start_at is None or end_at is None:raise ValueError('cohort_source_interval_required')
    output={'schema_version':1,'run_id':'mlb:'+hashlib.sha256(json.dumps(manifest,sort_keys=True).encode()).hexdigest()[:12],
            'display_name':'MLB historical research — source coverage explicit','start_at':start_at,
            'end_at':end_at,'candidate_prints':eligible,'identity':manifest,'opportunities':rows,
            'cohort_description':'Complete daily census' if cohort_summary.get('complete_census') else 'Retained census and sampled-cell source windows; weight one. Ordinary full-game outcomes and original scheduled pregame proxy.'}
    (args.out/'opportunities.json').write_text(json.dumps(output,separators=(',',':'))+'\n')
    coverage={'eligible_prints':eligible,'priced_by_model':dict(Counter(r['model'] for r in rows)),
              'scope_exclusions':dict(scope),'pricing_exclusions':{m:dict(v) for m,v in exclusions.items()},
              'missing_model_status':'unavailable_data_not_zero_fills','manifest':manifest}
    (args.out/'coverage.json').write_text(json.dumps(coverage,indent=2)+'\n')
    print(json.dumps({k:v for k,v in coverage.items() if k!='manifest'},indent=2))

if __name__=='__main__':main()

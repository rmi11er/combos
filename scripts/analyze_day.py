"""Reproducible completed-print opportunity envelope, never a fill backtest."""
import bisect
from collections import Counter,defaultdict
import datetime as dt
import gzip,hashlib,heapq,json,math,sys
from pathlib import Path
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.combos.pricing import fee_expanded_book,selected_book,joint_independence,stressed_joint_upper,customer_quantity,short_yes_economics,fee_per_share,affordable_short_yes_quantity
from src.combos.creators import CreatorWatchlist
from src.combos.external_blend import HistoricalBlend
from build_catalog import ingest
START=1788584400;END=START+86400

def timestamp(s):
    return dt.datetime.fromisoformat(s.replace('Z','+00:00')).timestamp()

def load_gz(path):
    with gzip.open(path,'rt') as f:return json.load(f)

def quote_floor(fair,margin,ranges):
    if fair+margin>=1:return None
    lo,hi=fair,1.
    for _ in range(50):
        q=(lo+hi)/2
        if q-fee_per_share(q,.035)<fair+margin:lo=q
        else:hi=q
    # Include a per-contract reserve for centicent rounding at >= one share.
    raw=hi+.0001
    for r in ranges:
        a,b,step=map(float,[r['start'],r['end'],r['step']])
        if raw<=b:
            q=a+math.ceil((max(a,raw)-a-1e-12)/step)*step
            if q<b or (q==b and b==1):return q if 0<q<1 else None
    return None

class Prices:
    def __init__(self):
        self.external=HistoricalBlend(ROOT/'data/external/historical_venue_books.jsonl')
        self.candles={};self.legs={};self.mapping=json.loads((ROOT/'data/derived/polymarket_mapping.json').read_text()) if (ROOT/'data/derived/polymarket_mapping.json').exists() else {};self.pm={}
        self.diagnostics=Counter()
        for f in (ROOT/'data/raw/legs').glob('*.gz'):
            m=load_gz(f)['payload'].get('market')
            if m:self.legs[m['ticker']]=m
        for f in list((ROOT/'data/raw/candles').glob('*.gz'))+list((ROOT/'data/raw/candles_retry').glob('*.gz')):
            rows=load_gz(f)['payload'].get('candlesticks',[])
            ticks={}
            for r in rows:
                t=r['end_period_ts']
                if t in ticks and ticks[t]!=r:raise ValueError('conflicting candle timestamp')
                ticks[t]=r
            times=sorted(ticks);self.candles[f.name[:-8]]=(times,[ticks[t] for t in times])
        for f in (ROOT/'data/raw/polymarket_history').glob('*.gz'):
            rows=load_gz(f)['payload'].get('history',[]);rows=sorted(rows,key=lambda r:r['t'])
            self.pm[f.name[:-8]]=([r['t'] for r in rows],[r['p'] for r in rows])

    def leg(self,leg,at,latency=60,max_age=120):
        ticker=leg['market_ticker'];data=self.candles.get(ticker)
        if not data:return None,'no_candles'
        times,rows=data;i=bisect.bisect_right(times,at-latency)-1
        if i<0:return None,'no_prior_candle'
        age=at-times[i]
        if age>latency+max_age:return None,'stale_candle'
        r=rows[i]
        try:bid=float(r['yes_bid']['close_dollars']);ask=float(r['yes_ask']['close_dollars'])
        except (KeyError,TypeError,ValueError):return None,'missing_bid_ask'
        try:b,a=selected_book(bid,ask,leg['side']);interval=fee_expanded_book(b,a,.07)
        except ValueError:return None,'crossed_or_invalid_book'
        if interval.point in (0,1):return None,'degenerate_leg_price'
        m=self.mapping.get(ticker,{})
        pm=None;gap=None
        if m.get('status')=='matched' and m['token'] in self.pm:
            pts,ps=self.pm[m['token']];j=bisect.bisect_right(pts,at-latency)-1
            if j>=0 and at-pts[j]<=latency+max_age:
                pm=ps[j] if leg['side']=='yes' else 1-ps[j]
                gap=abs(pm-interval.point)
        return {'interval':interval,'age':age,'pm_point':pm,'venue_gap':gap,'start':timestamp(m['start_time']) if m.get('start_time') else None},None

    def combo(self,m,at,latency=60):
        ls=m['mve_selected_legs'];values=[]
        for l in ls:
            v,error=self.leg(l,at,latency)
            if error:return None,error
            values.append(v)
        a,b=values
        fair=joint_independence(a['interval'],b['interval'])
        try:three=joint_independence(*(self.external.leg(l['market_ticker'],l['side'],at) for l in ls))
        except ValueError:three=None
        starts=[v['start'] for v in values]
        phase='unknown' if any(t is None for t in starts) else 'in_play' if min(starts)<=at else 'pregame'
        pm_points=[v['pm_point'] for v in values]
        return {'fair':fair,'three_venue':three,'rho_002':stressed_joint_upper(a['interval'],b['interval'],.02),'rho_005':stressed_joint_upper(a['interval'],b['interval'],.05),'phase':phase,'max_age':max(v['age'] for v in values),'pm_point':math.prod(pm_points) if all(x is not None for x in pm_points) else None,'equal_weight_point':math.prod((v['interval'].point+v['pm_point'])/2 for v in values) if all(x is not None for x in pm_points) else None,'max_venue_gap':max(v['venue_gap'] for v in values) if all(v['venue_gap'] is not None for v in values) else None},None

def same_fixture(m):
    return len({l['event_ticker'].split('-',1)[1] for l in m['mve_selected_legs']})<2

def analyze():
    prices=Prices();markets={m['ticker']:m for m in load_gz(ROOT/'data/derived/cfb_two_leg_markets.json.gz')}
    if any(not m['event_ticker'].startswith('KXMVECROSSCATEGORY-SHARD1-') for m in markets.values()):
        raise ValueError('CFB shard changed: verify historical maker fee before pricing')
    total=Counter();hourly=[defaultdict(float) for _ in range(24)];trades=[];ids=set();duplicate_ids=0
    for h in range(24):
        tape=ingest(h)
        for r in tape['combos']:
            if r['trade_id'] in ids:duplicate_ids+=1;continue
            ids.add(r['trade_id']);q=float(r['yes_price_dollars']);n=float(r['count_fp']);at=timestamp(r['created_time'])
            if abs(q+float(r['no_price_dollars'])-1)>1e-8:raise ValueError('noncomplementary public prices')
            side=r.get('taker_outcome_side',r.get('taker_side'))
            if side not in ('yes','no'):raise ValueError('unknown taker direction')
            if r.get('taker_side') and side!=r['taker_side']:raise ValueError('direction mismatch')
            volume=n*(q if side=='yes' else 1-q)
            total['all_combo_trades']+=1;total['all_combo_contracts']+=n;total['all_combo_taker_premium']+=volume
            hourly[h]['all_combo_premium']+=volume;hourly[h]['all_combo_trades']+=1;hourly[h]['all_combo_contracts']+=n
            m=markets.get(r['ticker'])
            if not m:continue
            same=same_fixture(m);total['cfb_two_leg_trades']+=1;total['cfb_two_leg_premium']+=volume
            hourly[h]['cfb_premium']+=volume;hourly[h]['cfb_trades']+=1;hourly[h]['same_game_premium' if same else 'cross_game_premium']+=volume
            record={'trade_id':r['trade_id'],'ticker':r['ticker'],'at':at,'hour':h,'quantity':n,'yes_price':q,'taker_side':side,'premium':volume,'same_game':same,'settlement_at':timestamp(m['settlement_ts']) if m.get('settlement_ts') else None,'settlement_value':float(m['settlement_value_dollars']) if m.get('settlement_value_dollars') is not None else None}
            if same:record['exclusion']='same_game_joint_model_missing'
            elif side!='yes':record['exclusion']='no_taker_not_short_yes'
            elif not 0<q<1:record['exclusion']='boundary_execution_price'
            else:
                v,error=prices.combo(m,at)
                if error:record['exclusion']=error
                else:
                    fair=v['fair'];record.update({'exclusion':'','fair_mid':fair.point,'fair_upper':fair.upper,'fair_lower':fair.lower,'fair_rho002':v['rho_002'],'fair_rho005':v['rho_005'],'phase':v['phase'],'maximum_leg_age_seconds':v['max_age'],'pm_joint_point':v['pm_point'],'two_venue_equal_point':v['equal_weight_point'],'max_venue_gap':v['max_venue_gap']})
                    three=v['three_venue']
                    record['three_venue_point']=three.point if three else None
                    record['three_venue_upper']=three.upper if three else None
                    record['three_venue_edge']=short_yes_economics(n,q,three.upper)['expected_edge'] if three else None
                    record['near_10_dollar_print']=5<=volume<=20
                    for name,p in [('mid',fair.point),('upper',fair.upper),('rho002',v['rho_002']),('rho005',v['rho_005'])]:
                        record[f'edge_{name}']=short_yes_economics(n,q,p)['expected_edge']
                    if v['equal_weight_point'] is not None:record['edge_equal_weight_diagnostic']=short_yes_economics(n,q,v['equal_weight_point'])['expected_edge']
                    for margin in [0,.001,.003,.005]:
                        floor=quote_floor(fair.upper,margin,m['price_ranges'])
                        record[f'competitive_{margin:.3f}']=floor is not None and floor<=q+1e-10
                    for latency in [0,30,120]:
                        alt,err=prices.combo(m,at,latency)
                        record[f'edge_upper_latency_{latency}']=None if err else short_yes_economics(n,q,alt['fair'].upper)['expected_edge']
            trades.append(record)
    if duplicate_ids:raise ValueError('cross-partition duplicate IDs after half-open filtering')
    frame=pd.DataFrame(trades).sort_values(['at','trade_id'])
    frame.to_csv(ROOT/'output/cfb_trade_opportunities.csv',index=False)
    eligible=frame[frame.exclusion==''].copy()
    # Completed-print allocation scenario: one allocation per market per second,
    # observed print quantity clipped to cash for principal + fee; no ticket cap.
    # Release at observed settlement + 60s; this is ex-post accounting only.
    capital_paths={}
    trade_fixtures={r['trade_id']:tuple(l['event_ticker'].split('-',1)[1] for l in markets[r['ticker']]['mve_selected_legs']) for r in eligible.to_dict('records')}
    for variant in ['mid','upper','rho002','rho005','upper_small_prints']:
        pricing_variant='upper' if variant=='upper_small_prints' else variant
        pending=[];free=10000.;seen_ticket=set();cumedge=0.;realized=0.;maxlocked=0.;allocs=[];reject=Counter();fixture_exposure=defaultdict(float);max_fixture_loss=0.;max_fixture=None
        for row in eligible.to_dict('records'):
            at=row['at']
            while pending and pending[0][0]<=at:
                _,tid,n,q,payout,loss=heapq.heappop(pending)
                free+=n*(1-payout);realized+=n*(q-payout)
                for fixture in trade_fixtures[tid]:fixture_exposure[fixture]-=loss
            if variant=='upper_small_prints' and not row['near_10_dollar_print']:continue
            key=(row['ticker'],math.floor(at))
            if key in seen_ticket:reject['repeat_market_second']+=1;continue
            if row[f'edge_{pricing_variant}']<=0:continue
            if row[f'edge_{pricing_variant}']/row['quantity']<.003:reject['below_0.3c_net_edge_floor']+=1;continue
            n=affordable_short_yes_quantity(max(0.,free),row['quantity'],row['yes_price'])
            if n<=0:reject['capital']+=1;continue
            econ=short_yes_economics(n,row['yes_price'],row['fair_'+pricing_variant])
            if econ['expected_edge']/n<.003:reject['below_0.3c_net_edge_floor']+=1;continue
            if econ['maximum_loss']>free+1e-9:reject['capital']+=1;continue
            # Do not allocate a print after known settlement time; report as
            # inconsistent execution/terminal chronology, not an alpha feature.
            st=row['settlement_at'];pay=row['settlement_value']
            if pd.isna(st) or pd.isna(pay):reject['missing_terminal_accounting']+=1;continue
            if st<at:reject['settlement_precedes_trade']+=1;continue
            seen_ticket.add(key);free-=econ['maximum_loss'];realized-=econ['maker_fee'];cumedge+=econ['expected_edge']
            heapq.heappush(pending,(st+60,row['trade_id'],n,row['yes_price'],pay,econ['maximum_loss']))
            for fixture in trade_fixtures[row['trade_id']]:
                fixture_exposure[fixture]+=econ['maximum_loss']
                if fixture_exposure[fixture]>max_fixture_loss:max_fixture_loss=fixture_exposure[fixture];max_fixture=fixture
            locked=sum(x[5] for x in pending);maxlocked=max(maxlocked,locked)
            allocs.append({'at':at,'hour':row['hour'],'expected_edge':econ['expected_edge'],'cumulative_edge':cumedge,'locked_loss':locked,'customer_premium':econ['customer_premium'],'quantity':n,'trade_id':row['trade_id']})
            allocs[-1].update({'free_cash_after_allocation':free,'phase':row['phase'],'terminal_net_pnl':n*(row['yes_price']-pay)-econ['maker_fee'],'printed_quantity':row['quantity'],'capital_limited':n<row['quantity']-1e-8})
        terminal=realized+sum(n*(q-pay) for _,_,n,q,pay,_ in pending)
        phase_totals={}
        for a in allocs:
            p=phase_totals.setdefault(a['phase'],{'allocations':0,'expected_edge':0.,'terminal_net_pnl':0.})
            p['allocations']+=1;p['expected_edge']+=a['expected_edge'];p['terminal_net_pnl']+=a['terminal_net_pnl']
        capital_paths[variant]={'allocations':len(allocs),'expected_edge':cumedge,'terminal_net_pnl':terminal,'maximum_locked_loss':maxlocked,'maximum_single_fixture_loss':max_fixture_loss,'fixture_at_maximum':max_fixture,'rejects':dict(reject),'phase_attribution':phase_totals}
        pd.DataFrame(allocs).to_csv(ROOT/f'output/capital_path_{variant}.csv',index=False)
    # Creator state uses only earlier observed requests. No print is assigned to
    # a creator by approximate timestamp matching.
    requests={};conflicts=0
    for file in (ROOT/'data/raw/rfqs').glob('*.gz'):
        for r in load_gz(file)['payload'].get('rfqs',[]):
            if r['id'] in requests and requests[r['id']]!=r:conflicts+=1
            requests[r['id']]=r
    watch=CreatorWatchlist();rfq_summary=Counter();rfq_rows=[]
    for r in sorted(requests.values(),key=lambda r:(timestamp(r['created_ts']),r['id'])):
        at=timestamp(r['created_ts']);creator=r.get('creator_id');legs=r.get('mve_selected_legs',[])
        state=watch.state(creator) if creator else {'blacklisted':False}
        if START<=at<END:
            rfq_summary['sample_requests']+=1
            rfq_summary['requests_with_creator_id' if creator else 'requests_without_creator_id']+=1
            if len(legs)>=20:rfq_summary['context_requests_with_20_or_more_legs']+=1
            m=markets.get(r['market_ticker'])
            if m:
                rfq_summary['cfb_requests']+=1;h=int((at-START)//3600);cost=float(r.get('target_cost_dollars') or 0)
                hourly[h]['cfb_observed_rfq_count']+=1;hourly[h]['cfb_observed_target_cost']+=cost
                row={'rfq_id':r['id'],'at':at,'hour':h,'target_cost':cost,'contracts_fp':float(r.get('contracts_fp') or 0),'creator_identity_available':bool(creator),'blacklist_prior':state['blacklisted'],'same_game':same_fixture(m)}
                if state['blacklisted']:row['reason']='prior_spam_blacklist'
                elif same_fixture(m):row['reason']='same_game'
                else:
                    v,error=prices.combo(m,at+1)
                    if error:row['reason']=error
                    else:
                        q=quote_floor(v['fair'].upper,.003,m['price_ranges'])
                        if q is None:row['reason']='no_valid_quote'
                        else:
                            n=customer_quantity(cost,q) if cost>0 else row['contracts_fp']
                            econ=short_yes_economics(n,q,v['fair'].upper)
                            row.update({'hypothetical_yes_quote':q,'hypothetical_contracts':n,'maximum_loss':econ['maximum_loss'],'edge_if_filled':econ['expected_edge'],'phase':v['phase'],'reason':'quotable_individually' if 0<econ['maximum_loss']<=10000 else 'size_or_capital'})
                            if row['reason']=='quotable_individually' and econ['expected_edge']<.003*n-1e-10:
                                row['reason']='markup_below_floor_after_fee_rounding'
                            if row['reason']=='quotable_individually':
                                hourly[h]['cfb_model_quotable_target_cost']+=cost
                                rfq_summary['quotable_requests']+=1
                                if 5<=cost<=20:rfq_summary['quotable_5_to_20_target']+=1
                rfq_rows.append(row)
        # Include earlier retained requests in creator state; ignore future day
        # requests so final blacklist is as of the studied day end.
        if at<END:
            sensitive=len(legs)==2 and all(l['event_ticker'].startswith('KXNCAAF') for l in legs) and len({l['event_ticker'].split('-',1)[1] for l in legs})==1
            watch.observe(r['id'],creator,at,[l['market_ticker']+':'+l['side'] for l in legs],correlation_sensitive=sensitive)
    creators=[watch.state(c) for c in watch.counts if c]
    creators.sort(key=lambda s:(-s['evidence'].get('spam_bursts',0),-s['evidence'].get('long_leg_requests',0),-s['evidence'].get('requests',0)))
    identity_status='available_in_sample' if creators else 'unavailable_creator_identity'
    (ROOT/'output/creator_watchlist.json').write_text(json.dumps({'scope':'Retained RFQs in traded CFB markets plus deterministic context sample; incomplete creator histories. No adverse-fill attribution available.','identity_status':identity_status,'policy':watch.policy.__dict__,'creators':creators},indent=2))
    (ROOT/'output/creator_blacklist.json').write_text(json.dumps({'as_of':'2026-09-06T05:00:00Z','use':'offline research only','identity_status':identity_status,'creators':[s for s in creators if s['blacklisted']]},indent=2))
    pd.DataFrame(rfq_rows).to_csv(ROOT/'output/cfb_rfq_quoteability.csv',index=False)
    pd.DataFrame([{'hour':i,**dict(x)} for i,x in enumerate(hourly)]).fillna(0).to_csv(ROOT/'output/hourly_volume.csv',index=False)
    summary={'study_date':'2026-09-05','timezone':'America/Chicago','capital':10000,'requested_three_venue_estimate':None,'missing_required_inputs':['historical Pinnacle paired odds and capacity','comparable historical liquidity across all three venues','historical all-universe competing quotes (private)'],'catalog_complete':(ROOT/'data/derived/catalog_summary.json').exists(),'catalog':json.loads((ROOT/'data/derived/catalog_summary.json').read_text()) if (ROOT/'data/derived/catalog_summary.json').exists() else None,'totals':dict(total),'exclusions':dict(Counter(frame.exclusion)),'eligible_priced_prints':len(eligible),'phase_counts':dict(Counter(eligible.phase)) if len(eligible) else {},'capital_upper_bound_scenarios':capital_paths,'rfq_sample':dict(rfq_summary),'creator_count':len(creators),'creator_review_count':sum(s['status']=='review' for s in creators),'creator_blacklist_count':sum(s['blacklisted'] for s in creators),'rfq_conflicting_retrievals':conflicts,'model':'Kalshi-only fee-expanded marginal independence proxy; full requested blend not estimable','assumptions':{'leg_taker_rate':.07,'combo_maker_rate':.035,'publication_latency_seconds':60,'maximum_additional_age_seconds':120,'reference_minimum_net_markup':.003,'customer_budget_includes_taker_fee':True,'quantity_step':.01,'no_combo_probability_band':True,'pinnacle_available':False,'liquidity_weighting_available':False,'capital_capture':'completed-print capacity upper bound; not observed fills'}}
    summary['catalog_request_complete']=summary['catalog_complete']
    summary['assumptions']['customer_ticket_cap_dollars']=None
    summary['assumptions']['allocation_sizing']='observed quantity clipped to available cash for principal plus maker fee'
    summary['creator_identity_status']=identity_status
    summary['catalog_complete']=bool(summary['catalog'] and not summary['catalog']['missing_tickers'])
    for variant in ['mid','upper','rho002','rho005']:
        s=eligible[f'edge_{variant}'];summary[f'observed_size_{variant}']={'positive_prints':int((s>0).sum()),'positive_edge_dollars':float(s.clip(lower=0).sum()),'signed_edge_all_priced_prints':float(s.sum())}
    summary['polymarket_diagnostic_coverage']=int(eligible.pm_joint_point.notna().sum()) if len(eligible) else 0
    small=eligible[eligible.near_10_dollar_print]
    summary['observed_5_to_20_dollar_prints']={'priced_prints':len(small),'positive_upper_edge_prints':int((small.edge_upper>0).sum()),'positive_upper_edge_at_observed_size':float(small.edge_upper.clip(lower=0).sum()),'signed_upper_edge_at_observed_size':float(small.edge_upper.sum())}
    summary['three_venue_priced_prints']=int(eligible.three_venue_point.notna().sum()) if len(eligible) else 0
    if summary['three_venue_priced_prints']:
        strict=eligible[eligible.three_venue_edge.notna()]
        summary['requested_three_venue_estimate']={'covered_prints':len(strict),'positive_edge_at_observed_size':float(strict.three_venue_edge.clip(lower=0).sum()),'signed_edge_at_observed_size':float(strict.three_venue_edge.sum()),'scope':'covered cross-game printed trades only; no acceptance estimate'}
    unique=eligible.drop_duplicates('ticker',keep='first')
    summary['unique_combo_calibration']={phase:{'markets':len(rows),'expected_yes_midpoint':float(rows.fair_mid.sum()),'expected_yes_upper':float(rows.fair_upper.sum()),'observed_binary_yes':int((rows.settlement_value==1).sum()),'nonbinary_or_missing':int((~rows.settlement_value.isin([0,1])).sum())} for phase,rows in unique.groupby('phase')}
    summary['quote_floor_competitiveness']={k:int(eligible[k].sum()) for k in ['competitive_0.000','competitive_0.001','competitive_0.003','competitive_0.005']}
    summary['latency_sensitivity']={str(l):{'priced':int(eligible[f'edge_upper_latency_{l}'].notna().sum()),'positive_edge':float(eligible[f'edge_upper_latency_{l}'].clip(lower=0).sum())} for l in [0,30,120]}
    (ROOT/'output/summary.json').write_text(json.dumps(summary,indent=2,allow_nan=False))
    print(json.dumps(summary,indent=2),flush=True)

if __name__=='__main__':analyze()

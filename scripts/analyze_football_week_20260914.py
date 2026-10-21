"""Candle-only diagnostic replay. Not the liquidity-weighted production model."""
from bisect import bisect_right, bisect_left
from collections import Counter,defaultdict
from dataclasses import asdict
import gzip
import json
import math
from pathlib import Path
import statistics
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from review_football_week_20260914 import OUT,read,write,FAMILIES
from combos.pricing import Interval,fee_expanded_book,short_yes_economics
from combos.joint_pricing import price_joint
from combos.shadow_engine import quote_price


def stamp(value):return __import__('datetime').datetime.fromisoformat(value.replace('Z','+00:00')).timestamp()

class Candles:
    def __init__(self):
        self.rows={}
        for path in sorted(OUT.glob('candles_*.json.gz')):
            day=path.name[8:18]
            for ticker,cs in read(path.name).items():
                rows=[]
                for c in cs:
                    try:
                        bid=float(c['yes_bid']['close_dollars']);ask=float(c['yes_ask']['close_dollars'])
                        if not 0<=bid<=ask<=1:continue
                        rows.append((c['end_period_ts'],bid,ask,float(c.get('volume_fp',0))))
                    except (KeyError,TypeError,ValueError):continue
                rows.sort();self.rows[(day,ticker)]=([r[0] for r in rows],rows)
    def at(self,day,ticker,at,max_age=180):
        ts,rows=self.rows.get((day,ticker),([],[]));i=bisect_right(ts,at-60)-1
        if i<0:raise ValueError('missing_prior_candle')
        end,bid,ask,volume=rows[i]
        if at-end>max_age:raise ValueError('candle_older_than_'+str(max_age)+'s')
        return {'bid':bid,'ask':ask,'point':(bid+ask)/2,'width_cents':100*(ask-bid),
                'age':at-end,'volume':volume,'end':end}


def summarize(rows):
    q=sum(r['q'] for r in rows);cost=sum(r['cost'] for r in rows)
    settled=[r for r in rows if r.get('pnl') is not None]
    pnl=sum(r['pnl'] for r in settled)
    return {'prints':len(rows),'markets':len({r['ticker'] for r in rows}),'contracts':q,
            'yes_premium_dollars':sum(r['q']*r['price'] for r in rows),'no_collateral_dollars':cost,
            'settled_prints':len(settled),'settled_no_collateral_dollars':sum(r['cost'] for r in settled),
            'settled_seller_pnl_dollars':pnl,'seller_return_on_settled_collateral':pnl/sum(r['cost'] for r in settled) if settled else None,
            'contract_weighted_price':sum(r['q']*r['price'] for r in rows)/q if q else None,
            'quantity_weighted_settlement':sum(r['q']*r['settlement'] for r in settled)/sum(r['q'] for r in settled) if settled else None}


def features(max_legs=4, joint_pricer=price_joint):
    markets=read('traded_market_requests.json.gz');native=read('combo_metadata.json.gz')
    legs=read('leg_metadata.json.gz');starts=json.loads((OUT/'fixture_starts.json').read_text())['starts']
    prod=read('production_request_policy.json.gz');history=Candles()
    groups=defaultdict(list);exclusions=Counter();priced=[];all_rows=[];seen=set();started=time.time()
    for path in sorted(OUT.glob('tape_*.json.gz')):
        tape=read(path.name);day=tape['day']
        for t in tape['trades']:
            if t['trade_id'] in seen:continue
            seen.add(t['trade_id']);ticker=t['market_ticker'];m=markets.get(ticker)
            if not m:exclusions['trade_without_in_scope_RFQ_identity']+=1;continue
            if m['sport']=='excluded_monday':exclusions['monday_prints']+=1;continue
            if m['sport'] not in ('NFL','CFB'):continue
            at=float(t.get('ts_ms',t['ts']*1000))/1000;q=float(t['count_fp']);price=float(t['yes_price_dollars'])
            if not math.isfinite(q) or q<=0 or not 0<price<1:exclusions['invalid_or_boundary_price']+=1;continue
            rate=.0 if ticker.startswith('KXMVECROSSCATEGORY0-SHARD1-') else .035 if ticker.startswith('KXMVECROSSCATEGORY-SHARD1-') else None
            if rate is None:exclusions['unreviewed_fee_series']+=1;continue
            econ=short_yes_economics(q,price,0,rate);nm=native.get(ticker,{})
            settlement=float(nm['settlement_value_dollars']) if nm.get('settlement_ts') and nm.get('settlement_value_dollars') is not None else None
            if settlement is not None and not 0<=settlement<=1:raise ValueError('bad native settlement')
            identity=sorted((l['market_ticker'],l['side']) for l in nm.get('mve_selected_legs',[]))
            if identity and identity!=sorted((l[0],l[1]) for l in m['legs']):raise ValueError('combo identity changed')
            side=t.get('taker_outcome_side') or t.get('taker_side')
            idx=bisect_left(m['request_times'],at-.25)-1
            last_request=m['request_times'][idx] if idx>=0 else None
            lag=at-last_request if last_request is not None else None
            sniffer=m['request_policy'][idx] if idx>=0 else 'unknown'
            blocked=prod[ticker][idx] if idx>=0 else None
            r={'id':t['trade_id'],'ticker':ticker,'sport':m['sport'],'day':day,'at':at,'q':q,'price':price,
               'cost':econ['maximum_loss'],'fee':econ['maker_fee'],'rate':rate,'side':side,'block_trade':bool(t.get('is_block_trade')),
               'settlement':settlement,'settled_at':stamp(nm['settlement_ts']) if nm.get('settlement_ts') else None,
               'pnl':q*(price-settlement)-econ['maker_fee'] if settlement is not None else None,
               'leg_count':m['leg_count'],'distinct_fixtures':m['distinct_fixtures'],
               'fixtures':sorted({l[0].split('-')[1] for l in m['legs']}),'legs':m['legs'],
               'request_lag':lag,'decision_at':last_request,'sniffer_state':sniffer,'production_blocked':blocked,
               'price_ranges':nm.get('price_ranges'),'quote_proxy_eligible':False}
            groups[(m['sport'],'all_observed')].append(r)
            groups[(m['sport'],'day_'+day)].append(r)
            groups[(m['sport'],'leg_count_'+str(m['leg_count']))].append(r)
            groups[(m['sport'],'distinct' if m['distinct_fixtures'] else 'same_fixture')].append(r)
            if side=='yes':groups[(m['sport'],'yes_taker')].append(r)
            all_rows.append(r)
            reason=None
            if side!='yes':reason='no_taker'
            elif r['block_trade']:reason='block_trade'
            elif max_legs is not None and not 2<=m['leg_count']<=max_legs:reason='leg_count'
            elif not m['distinct_fixtures']:reason='same_fixture'
            elif any(l[0].split('-')[0] not in FAMILIES for l in m['legs']):reason='unsupported_family'
            elif any(l[0].split('-')[1] not in starts for l in m['legs']):reason='unknown_kickoff'
            elif any(starts[l[0].split('-')[1]]<=at+60 for l in m['legs']):reason='not_pregame'
            if reason:
                exclusions[m['sport']+':'+reason]+=1;r['replay_exclusion']=reason;continue
            # No trade-time or settlement information enters the forecast.
            decision=last_request if lag is not None and lag<=3 else at-.25
            try:
                obs=[history.at(day,l[0],decision) for l in m['legs']]
                iv=[]
                for o,l in zip(obs,m['legs']):
                    v=fee_expanded_book(o['bid'],o['ask'],.07)
                    if l[1]=='no':v=Interval(1-v.upper,1-v.point,1-v.lower)
                    iv.append(v)
                f=joint_pricer(iv,.05);fair=f['joint']['point']
                r.update(fair=fair,edge_cents=100*(price-fair),net_edge_cents=100*(q*(price-fair)-econ['maker_fee'])/q,
                    mean_width_cents=statistics.mean(o['width_cents'] for o in obs),max_width_cents=max(o['width_cents'] for o in obs),
                    mean_candle_volume=statistics.mean(o['volume'] for o in obs),max_candle_age=max(o['age'] for o in obs),
                    tail_reserve_cents=f['dependence']['reserve_cents'],tail_pass=f['dependence']['reserve_cents']<23.9065,
                    quote_proxy_eligible=lag is not None and .25<=lag<=3,source_points=[o['point'] for o in obs],
                    quote_forecast_at=decision,candle_ends=[o['end'] for o in obs])
                r['tail_bound_method']=f['dependence']['model']
                r['tail_bound_exact']=f['dependence'].get('exact',True)
                for horizon in (60,300):
                    try:
                        if any(starts[l[0].split('-')[1]]<=decision+horizon+60 for l in m['legs']):raise ValueError('kickoff')
                        later=[history.at(day,l[0],decision+horizon) for l in m['legs']]
                        point=math.prod(o['point'] if l[1]=='yes' else 1-o['point'] for o,l in zip(later,m['legs']))
                        r['markout_'+str(horizon)+'_cents']=100*(price-point)-100*econ['maker_fee']/q
                        r['fair_move_'+str(horizon)+'_cents']=100*(point-fair)
                    except ValueError:pass
                priced.append(r)
            except (KeyError,TypeError,ValueError) as exc:
                exclusions[m['sport']+':'+str(exc)]+=1;r['replay_exclusion']=str(exc)
        print('features',day,'priced',len(priced),'elapsed',round(time.time()-started),flush=True)
    write('opportunity_summary.json',{'groups':{'|'.join(k):summarize(v) for k,v in groups.items()},
        'exclusions':dict(exclusions),'distinct_public_combo_prints_scanned':len(seen),'priced':len(priced),
        'basis':'captured public tape matched to observed RFQ market identities; not exchange-wide slate census'})
    write('observed_football_trades.json.gz',all_rows);write('priced_trades.json.gz',priced)


def risk_identity(row,native,mappings):
    from combos.payoff_risk import canonical_leg_risk
    from combos.matching import fixture_teams,norm
    vectors=[];eligible=True
    for ticker,side,*_ in row['legs']:
        m=native[ticker];fixture=ticker.split('-')[1];ml=ticker.split('-')[0] in ('KXNFLGAME','KXNCAAFGAME')
        sign=1 if side=='yes' else -1;key=ticker
        if ticker in mappings:
            r=canonical_leg_risk(mappings[ticker],side);key=r['key'];sign=r['selected_sign']
        elif ticker.startswith('KXNCAAFGAME-'):
            teams=sorted(fixture_teams(m) or []);selected=norm(m.get('yes_sub_title',''))
            if len(teams)==2 and selected in teams:
                key=fixture+':moneyline:'+teams[0];sign*=1 if selected==teams[0] else -1
            else:ml=False
        elif ml:ml=False
        eligible &= ml
        vectors.append((fixture,key,sign,ml and row['sport']=='NFL'))
    return vectors,eligible


def proxy_hedge(ledger,row,q,ask,active,history):
    from combos.inventory_fitting import probability,variance_delta
    if not row['moneyline_eligible']:return False,None
    focus={f:ledger.bucket_state('fixture:'+f,True) for f in row['fixtures']}
    focus={f:s for f,s in focus.items() if s['risk_dollars']>=900}
    if not focus:return False,None
    probs={};positions=[]
    try:
        for old in [*active.values(),row]:
            for leg,vector in zip(old['legs'],old['risk_legs']):
                p=history.at(row['day'],leg[0],row['quote_forecast_at'])['point']
                selected=p if leg[1]=='yes' else 1-p
                cp=selected if vector[2]==1 else 1-selected
                if vector[1] in probs and abs(probs[vector[1]]-cp)>.01:return False,None
                probs[vector[1]]=cp
            if old is not row:positions.append((old['risk_legs'],old['q']))
    except ValueError:return False,None
    delta=variance_delta(row['risk_legs'],q,positions,probs)
    if delta>1e-9:return False,delta
    cost=short_yes_economics(q,ask,0,row['rate'])['maximum_loss'];premium=q-cost
    for f,_,sign,_ in row['risk_legs']:
        if f not in focus:continue
        s=focus[f];side=-sign
        after=s['gross']/10000+max(0,*(s['sides'][d]/10000+(cost if d==side else 0)-
              s['credits'][-d]/10000-(premium if -d==side else 0) for d in (-1,1)))
        old_delta=sum(-n*sg*probability([v for v in ls if v[0]!=f],probs)
                      for ls,n in positions for ff,_,sg,_ in ls if ff==f)
        new_delta=old_delta-q*sign*probability([v for v in row['risk_legs'] if v[0]!=f],probs)
        if after<s['risk_dollars']-1e-9 and abs(new_delta)<abs(old_delta)-1e-9:return True,delta
    return False,delta


def simulate(rows,history,name,edge=.003,width=True,tail=True,blacklist=True,net=False,hedge=None):
    import sqlite3
    from combos.deployment_risk import DeploymentCappedRiskLedger
    class Store:
        def __init__(self):
            self.db=sqlite3.connect(':memory:');self.db.row_factory=sqlite3.Row
        def append(self,*args):pass
    store=Store();policy={'capital_dollars':10000,'maximum_committed_dollars':10000,
        'per_contract_dollars':500,'per_combo_dollars':500,'per_fixture_dollars':1000,
        'inventory_fitting':{'enabled':net}}
    ledger=DeploymentCappedRiskLedger(store,policy);active={};fills=[];rejects=Counter();curves=[]
    peak=0.;peak_fixture=0.;realized=0.;high_equity=10000.;drawdown=0.
    store.db.execute('BEGIN')
    def settle(at):
        nonlocal realized,high_equity,drawdown
        done=sorted((old for old in active.values() if old['settled_at'] is not None and old['settled_at']<=at),key=lambda x:(x['settled_at'],x['id']))
        for old in done:
            ledger.transition(old['id'],'simulated_settled',old['settled_at'],0,old['q']*(1-old['settlement']))
            realized+=old['pnl'];del active[old['id']]
            equity=10000+realized;high_equity=max(high_equity,equity);drawdown=max(drawdown,high_equity-equity)
            curves.append({'at':old['settled_at'],'settled_equity':equity,'kind':'settlement'})
    for row in rows:
        settle(row['at'])
        if not row['quote_proxy_eligible']:rejects['no_250ms_to_3s_prior_RFQ']+=1;continue
        if width and row['max_width_cents']>5+1e-9:rejects['leg_book_width']+=1;continue
        if tail and not row['tail_pass']:rejects['correlation_tail']+=1;continue
        if blacklist and row['production_blocked']:rejects['creator_cooldown']+=1;continue
        floor=edge;discount=False;delta=None
        try:
            if hedge is not None:
                low=quote_price(row['fair'],hedge,row['rate'],row['price_ranges'])
                discount,delta=proxy_hedge(ledger,row,row['q'],low,active,history)
                if discount:floor=hedge
            ask=quote_price(row['fair'],floor,row['rate'],row['price_ranges'])
            econ=short_yes_economics(row['q'],ask,row['fair'],row['rate'])
        except (KeyError,ValueError,TypeError):rejects['no_valid_quote_price']+=1;continue
        if ask>row['price']+1e-12:rejects['not_price_competitive']+=1;continue
        if econ['expected_edge']/row['q']+1e-12<floor:rejects['rounded_fee_edge']+=1;continue
        if econ['maximum_loss']>250+1e-9:rejects['full_print_exceeds_ticket_cap']+=1;continue
        if abs(row['q']*100-round(row['q']*100))>1e-7:rejects['quantity_precision']+=1;continue
        signed={}
        if net and row['moneyline_eligible']:
            signed={'contract':[{'key':k,'side':-s} for f,k,s,t in row['risk_legs']],
                    'fixture':[{'key':f,'side':-s} for f,k,s,t in row['risk_legs']]}
        buckets={'fixture':row['fixtures'],'contract':sorted({l[1] for l in row['risk_legs']}),
                 'combo':['|'.join(sorted(str((l[1],l[2])) for l in row['risk_legs']))]}
        context={'quantity':row['q'],'yes_ask':ask,'maker_fee_rate':row['rate'],
                 'moneyline_offset':{'eligible':bool(signed)}}
        result=ledger.reserve(row['id'],'historical_proxy',econ['maximum_loss'],buckets,row['at']+3,context,signed_buckets=signed)
        if not result['allowed']:rejects[result['reason']]+=1;continue
        ledger.transition(row['id'],'simulated_filled',row['at'],0)
        fill=dict(row,price=ask,public_price=row['price'],cost=econ['maximum_loss'],fee=econ['maker_fee'],
            pnl=row['q']*(ask-row['settlement'])-econ['maker_fee'] if row['settlement'] is not None else None,
            model_ev=econ['expected_edge'],charged_edge_cents=100*(ask-row['fair']),discounted=discount,
            required_edge_cents=100*floor,variance_delta=delta)
        active[row['id']]=fill;fills.append(fill)
        committed=sum(v['cost'] for v in active.values());peak=max(peak,committed)
        peak_fixture=max(peak_fixture,*(ledger.bucket_state('fixture:'+f)['risk_dollars'] for f in row['fixtures']))
        curves.append({'at':row['at'],'committed':committed,'settled_equity':10000+realized,'kind':'fill'})
    settle(float('inf'));store.db.commit();store.db.close()
    result=summarize(fills)
    result.update(name=name,model_ev_dollars=sum(f['model_ev'] for f in fills),peak_committed_dollars=peak,
        peak_fixture_conditional_risk_dollars=peak_fixture,maximum_settled_equity_drawdown=drawdown,
        discounted_fills=sum(f['discounted'] for f in fills),discounted_pnl=sum(f['pnl'] or 0 for f in fills if f['discounted']),
        rejects=dict(rejects),remaining_open=len(active),
        assumption='candle proxy; full public print size; execution at our model ask; no RFQ award or depth verification')
    return result,fills,curves


def performance():
    rows=read('priced_trades.json.gz');native=read('leg_metadata.json.gz');history=Candles()
    maps={m['kalshi_ticker']:m for m in json.loads((ROOT/'config/runtime_nfl_authorized_shadow_20260910.json').read_text())['mappings']}
    for r in rows:r['risk_legs'],r['moneyline_eligible']=risk_identity(r,native,maps)
    scenarios=[('gross_unfiltered',dict(width=False,tail=False,blacklist=False)),
        ('gross_width',dict(tail=False,blacklist=False)),('gross_width_tail',dict(blacklist=False)),
        ('gross_current_filters',{}),('payoff_current_filters',dict(net=True)),
        ('inventory_0.10c',dict(net=True,hedge=.001)),('inventory_0.05c',dict(net=True,hedge=.0005)),
        ('flat_0.10c',dict(edge=.001)),('flat_0.05c',dict(edge=.0005)),('flat_0.50c',dict(edge=.005))]
    results={}
    for sport in ('CFB','NFL'):
        cohort=sorted([r for r in rows if r['sport']==sport],key=lambda r:(r['at'],r['id']))
        for name,options in scenarios:
            key=sport+'_'+name;result,fills,curves=simulate(cohort,history,name,**options);results[key]=result
            write(key+'_fills.json.gz',fills);write(key+'_curve.json.gz',curves)
            print(key,json.dumps({k:result[k] for k in ('prints','settled_seller_pnl_dollars','model_ev_dollars','discounted_fills')}),flush=True)
    write('performance_summary.json',results)


def diagnostics():
    from scipy.stats import spearmanr,pearsonr
    rows=read('priced_trades.json.gz');observed=read('observed_football_trades.json.gz');out={}
    def describe(xs):
        if not xs:return {'prints':0}
        q=sum(r['q'] for r in xs)
        result=summarize(xs)
        result.update(quantity_weighted_gross_edge_cents=sum(r['q']*r['edge_cents'] for r in xs)/q,
            quantity_weighted_net_edge_cents=sum(r['q']*r['net_edge_cents'] for r in xs)/q,
            median_gross_edge_cents=statistics.median(r['edge_cents'] for r in xs),
            point_brier_trade_weighted=statistics.mean((r['fair']-r['settlement'])**2 for r in xs),
            mean_tail_reserve_cents=statistics.mean(r['tail_reserve_cents'] for r in xs),
            max_tail_reserve_cents=max(r['tail_reserve_cents'] for r in xs))
        for h in (60,300):
            ms=[r for r in xs if 'markout_'+str(h)+'_cents' in r];mq=sum(r['q'] for r in ms)
            result['markout_'+str(h)]={'prints':len(ms),'quantity_weighted_net_edge_cents':sum(r['q']*r['markout_'+str(h)+'_cents'] for r in ms)/mq if mq else None,
                'quantity_weighted_fair_move_cents':sum(r['q']*r['fair_move_'+str(h)+'_cents'] for r in ms)/mq if mq else None}
        return result
    for sport in ('CFB','NFL'):
        xs=[r for r in rows if r['sport']==sport];obs=[r for r in observed if r['sport']==sport]
        near=[r for r in xs if r['quote_proxy_eligible']]
        selections={'all_priced':xs,'recent_RFQ':near,
            'recent_RFQ_narrow':[r for r in near if r['max_width_cents']<=5+1e-9],
            'production_clear':[r for r in near if r['production_blocked'] is False],
            'production_cooldown':[r for r in near if r['production_blocked'] is True],
            'sniffer_recurrent':[r for r in near if r['sniffer_state']=='recurrent'],
            'sniffer_other':[r for r in near if r['sniffer_state']!='recurrent']}
        for n in (2,3,4):selections['legs_'+str(n)]=[r for r in xs if r['leg_count']==n]
        for low,hi in ((0,1),(1,3),(3,5),(5,10),(10,101)):
            selections[f'mean_width_{low}_{hi}c']=[r for r in xs if low<=r['mean_width_cents']<hi]
        for low,hi in ((-100,0),(0,.3),(.3,1),(1,3),(3,100)):
            selections[f'public_net_edge_{low}_{hi}c']=[r for r in xs if low<=r['net_edge_cents']<hi]
        correlation={}
        for key in ('mean_width_cents','max_width_cents','mean_candle_volume'):
            rho=spearmanr([r[key] for r in xs],[r['edge_cents'] for r in xs])
            correlation[key]={'spearman':float(rho.statistic) if math.isfinite(rho.statistic) else None,
                'interpretation':'descriptive only; overlapping combos/fixtures invalidate iid significance'}
        baseline=read(sport+'_inventory_0.10c_fills.json.gz')
        fs=sorted({f for r in baseline for f in r['fixtures']})
        concentration=[]
        for fixture in fs:
            involved=[r for r in baseline if fixture in r['fixtures']]
            concentration.append({'fixture':fixture,'fills':len(involved),'involving_fixture_pnl':sum(r['pnl'] for r in involved),
                'pnl_without_any_combo_containing_fixture':sum(r['pnl'] for r in baseline if fixture not in r['fixtures']),
                'collateral':sum(r['cost'] for r in involved)})
        markouts={}
        for h in (60,300):
            fsrows=[r for r in baseline if 'fair_move_'+str(h)+'_cents' in r];q=sum(r['q'] for r in fsrows)
            markouts[str(h)]={'fills':len(fsrows),'quote_net_edge_cents':sum(r['q']*(r['charged_edge_cents']-100*r['fee']/r['q']-r['fair_move_'+str(h)+'_cents']) for r in fsrows)/q if q else None}
        q=sum(r['q'] for r in baseline)
        out[sport]={'pricing_cohorts':{k:describe(v) for k,v in selections.items()},'descriptive_correlations':correlation,
            'fixture_concentration':sorted(concentration,key=lambda r:-abs(r['involving_fixture_pnl'])),
            'baseline_quote_markouts':markouts,
            'baseline_quote_vs_public':{'contracts':q,'charged_gross_edge_cents':sum(r['q']*r['charged_edge_cents'] for r in baseline)/q if q else None,
                'public_gross_edge_cents':sum(r['q']*r['edge_cents'] for r in baseline)/q if q else None,
                'public_minus_our_ask_dollars':sum(r['q']*(r['public_price']-r['price']) for r in baseline)},
            'daily_priced':dict(Counter(r['day'] for r in xs)),'daily_proxy_fills':dict(Counter(r['day'] for r in baseline)),
            'public_observed_policy':{state:summarize([r for r in obs if r['side']=='yes' and r['sniffer_state']==state]) for state in ('clear','provisional','recurrent','unknown')}}
    write('signal_diagnostics.json',out)


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['features','performance','diagnostics']);a=p.parse_args();globals()[a.stage]()

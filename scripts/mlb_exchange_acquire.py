#!/usr/bin/env python3
"""Resumable MLB leg histories; native game time, team and strike joins.

These matches cover ordinary completed games only. Exceptional settlement
equivalence and point-in-time schedule revisions are not certified here.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta
from decimal import Decimal, InvalidOperation
import gzip
import hashlib
import json
import math
from pathlib import Path
import re
import sys
import time
from zoneinfo import ZoneInfo
import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from cfb_full_exchange_acquire import Job, fetch, atomic_json

TEAM_NAMES = {
 'AZ':'Arizona Diamondbacks', 'ATH':'Athletics', 'ATL':'Atlanta Braves',
 'BAL':'Baltimore Orioles', 'BOS':'Boston Red Sox', 'CHC':'Chicago Cubs',
 'CWS':'Chicago White Sox', 'CIN':'Cincinnati Reds', 'CLE':'Cleveland Guardians',
 'COL':'Colorado Rockies', 'DET':'Detroit Tigers', 'HOU':'Houston Astros',
 'KC':'Kansas City Royals', 'LAA':'Los Angeles Angels', 'LAD':'Los Angeles Dodgers',
 'MIA':'Miami Marlins', 'MIL':'Milwaukee Brewers', 'MIN':'Minnesota Twins',
 'NYM':'New York Mets', 'NYY':'New York Yankees', 'PHI':'Philadelphia Phillies',
 'PIT':'Pittsburgh Pirates', 'SD':'San Diego Padres', 'SEA':'Seattle Mariners',
 'SF':'San Francisco Giants', 'STL':'St. Louis Cardinals', 'TB':'Tampa Bay Rays',
 'TEX':'Texas Rangers', 'TOR':'Toronto Blue Jays', 'WSH':'Washington Nationals'}

def norm(s): return re.sub('[^a-z0-9]', '', s.lower())
NAMES = {norm(name):code for code,name in TEAM_NAMES.items()}
NAMES.update({'oaklandathletics':'ATH', 'sacramentoathletics':'ATH', 'stlouiscardinals':'STL'})
def stamp(s):
    dt=datetime.fromisoformat(s.replace('Z','+00:00'))
    if dt.tzinfo is None:raise ValueError('timezone_required')
    return dt.timestamp()
def loadgz(p):
    with gzip.open(p,'rt') as f:return json.load(f)
def array(x):return json.loads(x) if isinstance(x,str) else x

def identity(ticker):
    if not re.fullmatch(r'KXMLB(?:GAME|SPREAD|TOTAL)-\d{2}[A-Z]{3}\d{6}[A-Z]+(?:G[12])?-[A-Z0-9.]+',ticker):
        raise ValueError('unsupported_native_ticker')
    token=ticker.split('-')[1]
    when=datetime.strptime(token[:11],'%y%b%d%H%M').replace(tzinfo=ZoneInfo('America/New_York')).timestamp()
    suffix=re.sub(r'G[12]$','',token[11:])
    pairs=[(a,b) for a in TEAM_NAMES for b in TEAM_NAMES if a!=b and a+b==suffix]
    if len(pairs)!=1:raise ValueError('unresolved_fixture_or_doubleheader_identity')
    return when,pairs[0]


PARTIAL_GAME = re.compile(r'\b(?:first|1st|second|2nd|third|3rd|fourth|4th|fifth|5th|sixth|6th|seventh|7th)\s+(?:(?:one|three|five|seven|\d+)\s+)?innings?\b|\bF[1357]\b|regulation.only|extra innings only',re.I)



# Exact reviewed fixture, across full-game families; never pricing approval.
UNSUPPORTED_EXHIBITION = re.compile(
    r'(?:KXMLBGAME-26JUL142000ALNL-(?:AL|NL)|'
    r'KXMLBSPREAD-26JUL142000ALNL-(?:AL|NL)[0-9]+|'
    r'KXMLBTOTAL-26JUL142000ALNL-[0-9]+)')
IDENTITY_POLICY_VERSION = 'ordinary_mlb_v3_explicit_2026_allstar_fixture_exclusion'


def unsupported_identity_legs(legs):
    unsupported=[]
    for leg in legs:
        ticker=leg['market_ticker']
        if UNSUPPORTED_EXHIBITION.fullmatch(ticker):
            unsupported.append({'ticker':ticker,'reason':'unsupported_exhibition_identity'})
        else:
            identity(ticker)  # All other unresolved identities remain hard failures.
    return unsupported


def half_point(value):
    try:line=Decimal(str(value))
    except InvalidOperation:raise ValueError('invalid_line')
    if not line.is_finite() or abs(line)%1!=Decimal('.5'):
        raise ValueError('push_or_invalid_line')
    return line


def validate_payoff(native, market, outcomes):
    """Verify ordinary full-game payoff prose against both machine lines.

    Schedule text can retain an earlier postponed date, so it is not used as
    the timestamp join. Exceptional settlements remain explicitly unverified.
    """
    desc=market.get('description') or ''
    primary=native.get('rules_primary') or ''
    if not desc or not primary:raise ValueError('payoff_text_missing')
    if PARTIAL_GAME.search(' '.join((desc,primary,market.get('question') or ''))):
        raise ValueError('partial_game_payoff')
    kind=market['sportsMarketType']
    if kind=='moneyline':
        for label in outcomes:
            if f'resolve to "{label}" if the {label} win the game' not in desc:
                raise ValueError('moneyline_payoff_text_unrecognized')
        return
    line=half_point(market.get('line'))
    strike=half_point(native.get('floor_strike'))
    native_line=re.search(r'(?:by more than|score more(?: than)?)\s+(-?\d+(?:\.\d+)?)\s+runs',primary)
    if not native_line or Decimal(native_line[1])!=strike:
        raise ValueError('native_rules_strike_disagree')
    if kind=='totals':
        over=re.search(r'resolve to "Over".*?combine to score (\d+) or more runs',desc,re.S)
        under=re.search(r'combined total is less than (\d+).*?resolve to "Under"',desc,re.S)
        if not over or not under or over[1]!=under[1] or Decimal(over[1])!=line+Decimal('.5'):
            raise ValueError('total_rules_line_disagree')
        if {o.lower() for o in outcomes}!={'over','under'}:
            raise ValueError('total_outcomes_unrecognized')
    elif kind=='spreads':
        cover=re.search(r'resolve to "([^"]+)" if the (.+?) win the game by (\d+) or more runs',desc)
        if not cover or cover[1] not in outcomes or NAMES.get(norm(cover[1]))!=NAMES.get(norm(cover[2])):
            raise ValueError('spread_rules_unrecognized')
        i=outcomes.index(cover[1]);handicap=line if i==0 else -line
        if handicap>=0 or Decimal(cover[3])!=-handicap+Decimal('.5'):
            raise ValueError('spread_rules_line_disagree')
        if f'Otherwise, this market will resolve to "{outcomes[1-i]}".' not in desc:
            raise ValueError('spread_complement_rules_missing')
    else:raise ValueError('unsupported_payoff_type')


def game_number(text):
    matches={int(x) for x in re.findall(r'\bgame\s*([12])\b',text,re.I)}
    if len(matches)>1:raise ValueError('ambiguous_doubleheader_number')
    return next(iter(matches)) if matches else None


def fee_rate(market):
    enabled=market.get('feesEnabled')
    if type(enabled) is not bool:raise ValueError('fee_enablement_unknown')
    if not enabled:return 0.
    schedule=market.get('feeSchedule') or {};rate=schedule.get('rate')
    if (schedule.get('exponent')!=1 or schedule.get('takerOnly') is not True or
        isinstance(rate,bool) or not isinstance(rate,(int,float)) or not math.isfinite(rate) or not 0<=rate<1):
        raise ValueError('unsupported_fee_schedule')
    return float(rate)

def get_cached(out,label,url,params):
    digest=hashlib.sha256(json.dumps([url,params],sort_keys=True).encode()).hexdigest()
    p=out/'metadata'/(label+'_'+digest+'.json.gz')
    if p.exists():
        d=loadgz(p)
        if d.get('status')==200:return d['payload']
    session=requests.Session();session.trust_env=False
    for attempt in range(4):
        r=session.get(url,params=params,timeout=35,allow_redirects=False)
        try:body=r.json()
        except ValueError:body={'invalid_json':True}
        atomic_json(p,{'url':url,'params':params,'status':r.status_code,'retrieved_at':time.time(),'payload':body},True)
        if r.status_code==200:return body
        if r.status_code!=429 and r.status_code<500:break
        time.sleep(2**attempt)
    raise ValueError(label+': HTTP '+str(r.status_code))

def pm_match(native,events):
    ticker=native['ticker']; start,teams=identity(ticker); family=ticker.split('-')[0]
    candidates=[]
    for event in events:
        # Slugs can retain an earlier schedule; never use their date as identity.
        try:
            if abs(stamp(event['startTime'])-start)>1:continue
        except (KeyError,TypeError,ValueError,AttributeError):continue
        native_game=re.search(r'G([12])$',ticker.split('-')[1])
        native_rules_game=game_number(native.get('rules_primary') or '')
        native_game=int(native_game[1]) if native_game else native_rules_game
        if native_game is not None and native_rules_game is not None and native_game!=native_rules_game:continue
        try:pm_game=game_number(' '.join((event.get('title') or '',event.get('description') or '')))
        except ValueError:continue
        if native_game is not None and pm_game is not None and native_game!=pm_game:continue
        money=[m for m in event.get('markets',[]) if m.get('sportsMarketType')=='moneyline']
        if len(money)!=1:continue
        if tuple(NAMES.get(norm(o)) for o in array(money[0]['outcomes']))!=teams:continue
        for m in event.get('markets',[]):
            outcomes=array(m.get('outcomes',[]));tokens=array(m.get('clobTokenIds',[]))
            if (len(outcomes)!=2 or len(set(outcomes))!=2 or len(tokens)!=2 or
                len({str(t) for t in tokens})!=2 or not all(str(t).isdigit() for t in tokens)):continue
            typ=m.get('sportsMarketType'); index=None
            if typ in ('moneyline','spreads') and {NAMES.get(norm(o)) for o in outcomes}!=set(teams):continue
            if family=='KXMLBGAME' and typ=='moneyline':
                selected=ticker.split('-')[2]
                index=next((i for i,o in enumerate(outcomes) if NAMES.get(norm(o))==selected),None)
            elif family=='KXMLBTOTAL' and typ=='totals' and native.get('floor_strike')==m.get('line'):
                index=next((i for i,o in enumerate(outcomes) if o.lower()=='over'),None)
            elif family=='KXMLBSPREAD' and typ=='spreads' and native.get('floor_strike') is not None and m.get('line') is not None:
                selected=re.match(r'[A-Z]+',ticker.split('-')[2]).group()
                index=next((i for i,o in enumerate(outcomes) if NAMES.get(norm(o))==selected
                            and (float(m['line']) if i==0 else -float(m['line']))==-float(native['floor_strike'])),None)
            if index is None:continue
            try:
                validate_payoff(native,m,outcomes)
                rate=fee_rate(m)
                market_game=game_number(' '.join((m.get('question') or '',m.get('description') or '')))
                if native_game is not None and market_game is not None and native_game!=market_game:continue
            except (ValueError,TypeError,InvalidOperation):continue
            fee=m.get('feeSchedule') or {}
            candidates.append({'token':str(tokens[index]),'condition_id':m['conditionId'],
                'event_slug':event['slug'],'market_slug':m['slug'],'start_at':start,'outcome':outcomes[index],
                'fee_rate':rate,'fee_schedule':fee,
                'description':m.get('description'),'mapping_scope':'ordinary_completed_game_only',
                'doubleheader_identity_basis':'exact_scheduled_time_and_teams; explicit_game_number_checked_when_present',
                'exception_rules_verified':False,'historical_fee_effective_date_verified':False})
    unique={c['token']:c for c in candidates}
    return {'status':'matched',**next(iter(unique.values()))} if len(unique)==1 else {
        'status':'unmatched' if not unique else 'ambiguous','candidates':len(unique)}


def gamma_date_bounds(tickers):
    """Derive event discovery bounds from native fixture times, not trade dates.

    Event end dates and postponed slugs are discovery hints only; pm_match
    still requires the exact structured fixture start and native payoff.
    """
    starts = [identity(ticker)[0] for ticker in tickers]
    if not starts:
        raise ValueError('no_eligible_native_fixture_windows')
    return ((datetime.fromtimestamp(min(starts), timezone.utc) - timedelta(days=14)).isoformat(),
            (datetime.fromtimestamp(max(starts), timezone.utc) + timedelta(days=14)).isoformat())

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--cohort',type=Path,default=ROOT/'runs/mlb_historical_20260907/cohort')
    p.add_argument('--out',type=Path,default=ROOT/'runs/mlb_historical_20260907/exchange')
    p.add_argument('--workers',type=int,default=6)
    p.add_argument('--prepare-only',action='store_true')
    p.add_argument('--write-reviewed-mapping',action='store_true',
                   help='Export structurally validated ordinary-game mappings; no exceptional settlement or historical fee certification')
    args=p.parse_args();args.out.mkdir(parents=True,exist_ok=True)
    markets=loadgz(args.cohort/'combo_markets.json.gz'); native=loadgz(args.cohort/'underlying_markets.json.gz')
    windows={};n=0;identity_exclusions=[];unsupported_tickers=set()
    with gzip.open(args.cohort/'candidate_trades.jsonl.gz','rt') as f:
        for line in f:
            row=json.loads(line);c=row['classification'];t=row['trade']
            if not c['distinct_fixtures'] or not 2<=c['nlegs']<=4 or t.get('taker_outcome_side',t.get('taker_side'))!='yes':continue
            n+=1;at=stamp(t['created_time'])
            legs=markets[t['ticker']]['mve_selected_legs']
            rejected=unsupported_identity_legs(legs)
            if rejected:
                identity_exclusions.append({'trade_id':t['trade_id'],'legs':rejected,'count_fp':t['count_fp'],'yes_price_dollars':t['yes_price_dollars']})
                unsupported_tickers.update(r['ticker'] for r in rejected)
            for leg in legs:
                ticker=leg['market_ticker']
                if ticker in unsupported_tickers:continue
                start,_=identity(ticker)
                lo=int(at)-180;hi=min(int(at)+360,int(start)-60)
                if ticker in windows:lo=min(lo,windows[ticker][0]);hi=max(hi,windows[ticker][1])
                windows[ticker]=(lo,hi)
    atomic_json(args.out/'identity_coverage.json',{'policy_version':IDENTITY_POLICY_VERSION,'candidate_prints':n,'unsupported_combo_prints':len(identity_exclusions),'unsupported_tickers':sorted(unsupported_tickers),'excluded_combos':identity_exclusions,'outcomes_used':False})
    if not windows and identity_exclusions:
        raise ValueError('complete_census_unpriced_identity: no supported collection windows; see identity_coverage.json')
    events=[];event_ids=set();event_lo,event_hi=gamma_date_bounds(windows)
    # Wide bounds accommodate native event end dates; exact start identity is checked locally.
    for offset in range(0,5000,100):
        batch=get_cached(args.out,'pm_events','https://gamma-api.polymarket.com/events',
            {'series_id':'3','end_date_min':event_lo,'end_date_max':event_hi,'limit':100,'offset':offset})
        if not isinstance(batch,list):raise ValueError('invalid Gamma event page')
        if not batch:break
        if not any(e['id'] not in event_ids for e in batch):raise ValueError('Gamma pagination repeated')
        for e in batch:
            if e['id'] not in event_ids:events.append(e);event_ids.add(e['id'])
        if len(batch)<100:break
    else:raise ValueError('Gamma pagination incomplete at explicit ceiling')
    mapping={ticker:{'status':'unmatched','reason':'unsupported_exhibition_identity','identity_policy_version':IDENTITY_POLICY_VERSION} for ticker in unsupported_tickers}
    for ticker in windows:
        try:mapping[ticker]=pm_match(native[ticker],events)
        except (ValueError,KeyError,TypeError) as exc:mapping[ticker]={'status':'unmatched','reason':str(exc)}
    atomic_json(args.out/'polymarket_mapping.json',mapping)
    if args.write_reviewed_mapping:
        atomic_json(args.out/'polymarket_mapping_reviewed.json',mapping)
        atomic_json(args.out/'mapping_review_summary.json',{
            'review_method':'Automated native full-game payoff, exact scheduled time, teams, lines, outcomes, tokens and fee schema checks in pm_match',
            'matched':sum(m['status']=='matched' for m in mapping.values()),
            'total':len(mapping),'outcomes_used_for_mapping':False,'exception_rules_verified':False,
            'historical_fee_effective_date_verified':False,
            'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()})
    atomic_json(args.out/'pm_events_complete.json',events)
    cutoff=get_cached(args.out,'kalshi_cutoff','https://external-api.kalshi.com/trade-api/v2/historical/cutoff',{})
    jobs=[];token_windows={}
    for ticker,(lo,hi) in sorted(windows.items()):
        historic=bool(native[ticker].get('settlement_ts')) and stamp(native[ticker]['settlement_ts'])<stamp(cutoff['market_settled_ts'])
        url=('https://external-api.kalshi.com/trade-api/v2/historical/markets/'+ticker+'/candlesticks' if historic else
             'https://external-api.kalshi.com/trade-api/v2/series/'+ticker.split('-')[0]+'/markets/'+ticker+'/candlesticks')
        for part,left in enumerate(range(lo,hi,3*86400)):
            jobs.append(Job('kalshi_parts',ticker+'.part'+str(part),url,
                {'start_ts':left,'end_ts':min(left+3*86400,hi),'period_interval':1,'include_latest_before_start':'true'}))
        m=mapping[ticker]
        if m['status']=='matched':
            token=m['token'];a,b=token_windows.get(token,(lo,hi));token_windows[token]=(min(a,lo),max(b,hi))
    for token,(lo,hi) in token_windows.items():
        jobs.append(Job('polymarket',token,'https://clob.polymarket.com/prices-history',
            {'market':token,'startTs':lo,'endTs':hi,'fidelity':1}))
    plan={'prints':n,'identity_policy_version':IDENTITY_POLICY_VERSION,'unsupported_combo_prints':len(identity_exclusions),'unsupported_tickers':sorted(unsupported_tickers),'kalshi_tickers':len(windows),'pm_matched_legs':sum(m['status']=='matched' for m in mapping.values()),
          'jobs':len(jobs),'windows':windows,'historical_only':True,'scope':'2–4 full-game distinct-fixture pregame scheduled proxy',
          'gamma_event_end_date_bounds':[event_lo,event_hi],
          'fees':'Native PM schedule retained as unverified; replay requires explicit dated fee scenario for new daily cohorts',
          'kalshi_fee_effective_date_verified':False,'pm_rates':sorted({m['fee_rate'] for m in mapping.values() if m['status']=='matched'})}
    atomic_json(args.out/'acquisition_plan.json',plan);print(json.dumps(plan|{'windows':'saved'}),flush=True)
    if args.prepare_only:return
    results=[]
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures=[pool.submit(fetch,job,args.out,[],4) for job in jobs]
        for future in as_completed(futures):
            results.append(future.result())
            if len(results)%100==0:print(json.dumps({'completed':len(results),'total':len(jobs)}),flush=True)
    atomic_json(args.out/'acquisition.json',{'plan':plan,'results':results,'completed_at':time.time()})

if __name__=='__main__':main()

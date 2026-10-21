"""Read-only source audit and compact historical football-slate research exports."""
import argparse
from collections import Counter, defaultdict, deque
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from functools import lru_cache
import gzip
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import time
import zlib
import math
import requests as http
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'runs/football_week_review_20260914'
ZONE=ZoneInfo('America/Chicago')
START=datetime(2026,9,8,tzinfo=ZONE).timestamp()
END=datetime(2026,9,14,tzinfo=ZONE).timestamp()

def write(name,data):
    OUT.mkdir(parents=True,exist_ok=True)
    path=OUT/name
    if name.endswith('.gz'):
        with gzip.open(path,'wt') as f:json.dump(data,f,separators=(',',':'))
    else:path.write_text(json.dumps(data,indent=2)+'\n')

def read(name):
    with gzip.open(OUT/name,'rt') as f:return json.load(f)

def trade_day(path):
    manifest=json.loads(path.read_text());folder=path.parent;day=folder.parent.name
    if not manifest['closed_cleanly']:raise ValueError('unclean capture '+day)
    trades={};counts=Counter();sessions=defaultdict(lambda:[None,None]);issues=[]
    for chunk in manifest['chunks']:
        blob=(folder/chunk['file']).read_bytes()
        if hashlib.sha256(blob).hexdigest()!=chunk['sha256']:raise ValueError('chunk hash mismatch')
        rows=gzip.decompress(blob).splitlines()
        if len(rows)!=chunk['rows']:raise ValueError('chunk row mismatch')
        for line in rows:
            if b'"type":"trade"' in line:
                e=json.loads(line);t=e['payload']['msg'];counts['all_public_prints']+=1
                if t.get('market_ticker','').startswith('KXMVE'):
                    t=dict(t,received_at=e['received_at'])
                    old=trades.get(t['trade_id'])
                    if old:counts['duplicate_combo_prints']+=1
                    else:trades[t['trade_id']]=t
            elif b'"kind":"message"' not in line:
                e=json.loads(line);counts[e['kind']]+=1
                if e['kind']=='heartbeat':
                    a=sessions[e['session_id']]
                    if a[0] is None:a[0]=e['received_at']
                    a[1]=e['received_at']
                if e['kind'] in ('disconnected','error'):issues.append(e)
    result={'day':day,'manifest':str(path),'manifest_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
            'manifest_counts':manifest['counts'],'started_at':manifest['started_at'],'ended_at':manifest['updated_at'],
            'counts':dict(counts),'heartbeat_spans':list(sessions.values()),'issues':issues,'trades':list(trades.values())}
    write('tape_'+day+'.json.gz',result)
    print(json.dumps({'day':day,'combo_prints':len(trades),'counts':dict(counts)}),flush=True)
    return {k:v for k,v in result.items() if k!='trades'}

def trades():
    paths=[p for p in sorted((ROOT/'runs/rfq_sniffer_nightly').glob('2026-09-*/capture*/manifest.json'))
           if '2026-09-08'<=p.parent.parent.name<='2026-09-13']
    with ThreadPoolExecutor(max_workers=2) as pool:reports=list(pool.map(trade_day,paths))
    write('capture_audit.json',reports)

def classify(legs):
    tickers=[l[0] for l in legs]
    if any(t.startswith('KXNFL') and '-26SEP14' in t for t in tickers):return 'excluded_monday',len(legs),False
    nfl=[t.startswith('KXNFL') for t in tickers];cfb=[t.startswith('KXNCAAF') for t in tickers]
    sport='NFL' if nfl and all(nfl) else 'CFB' if cfb and all(cfb) else 'mixed_football' if any(nfl+cfb) else 'other'
    if sport in ('NFL','CFB'):
        dates=[re.search(r'-(26SEP\d\d)',t) for t in tickers]
        if any(not m or not '26SEP08'<=m[1]<='26SEP13' for m in dates):sport='excluded_other_slate_'+sport
    fixtures=[t.split('-')[1] if '-' in t else t for t in tickers]
    return sport,len(legs),len(set(fixtures))==len(fixtures)

def blacklist_intervals(db):
    """Reconstruct the saved behavioral policy causally, never use final lists."""
    p=json.loads(db.execute("SELECT value FROM metadata WHERE key='policy'").fetchone()[0])
    windows=defaultdict(deque);history=defaultdict(list);previous={}
    for creator,at,period in db.execute('SELECT creator,at,period_id FROM bursts WHERE block_eligible=1 ORDER BY at'):
        w=windows[creator];w.append((at,period))
        while w and w[0][0]<=at-p['burst_evidence_seconds']:w.popleft()
        if len(w)<p['bursts_to_blacklist']:continue
        periods=defaultdict(list)
        for t,k in w:periods[k].append(t)
        qualified={k:v[p['bursts_to_blacklist']-1] for k,v in periods.items() if len(v)>=p['bursts_to_blacklist']}
        recurrent=period in qualified and any(k!=period and at-t>=p['recurrence_minimum_seconds'] for k,t in qualified.items())
        old=previous.get(creator)
        if old and old[1]=='recurrent' and old[0]>at:recurrent=True
        confidence='recurrent' if recurrent else 'provisional';expiry=at+p['blacklist_seconds' if recurrent else 'provisional_blacklist_seconds']
        history[creator].append((at,expiry,confidence));previous[creator]=(expiry,confidence)
    return history

def requests():
    tapes=[read(p.name) for p in sorted(OUT.glob('tape_*.json.gz'))]
    wanted={t['market_ticker'] for tape in tapes for t in tape['trades']}
    db=sqlite3.connect((ROOT/'data/derived/rfq_sniffer/evidence_v2.sqlite').as_uri()+'?mode=ro',uri=True)
    db.execute('PRAGMA temp_store=MEMORY');db.execute('PRAGMA cache_size=-64000')
    history=blacklist_intervals(db)
    from bisect import bisect_left
    def blocked(creator,at):
        events=history.get(creator,[]);i=bisect_left(events,(at,))-1
        return events[i][2] if i>=0 and events[i][1]>at else 'clear'
    @lru_cache(maxsize=200000)
    def decoded(blob):return json.loads(zlib.decompress(blob))
    classifications={};markets={};stats=defaultdict(Counter);n=0;started=time.time()
    for ticker,blob,at,creator in db.execute('SELECT ticker,legs,at,creator FROM requests WHERE at>=? AND at<? ORDER BY at',(START,END)):
        n+=1
        day=datetime.fromtimestamp(at,ZONE).strftime('%Y-%m-%d')
        key=classifications.get(ticker)
        if key is None:
            legs=decoded(blob);key=classify(legs);classifications[ticker]=key
        sport,nlegs,distinct=key;stat=stats[day+'|'+sport]
        stat['requests']+=1;stat['legs_'+str(nlegs)]+=1
        state=blocked(creator,at);stat['blacklist_'+state]+=1
        if 2<=nlegs<=4 and distinct:stat['2_to_4_distinct_fixture_requests']+=1
        if ticker in wanted and sport in ('NFL','CFB','excluded_monday'):
            if ticker not in markets:
                markets[ticker]={'legs':decoded(blob),'sport':sport,'leg_count':nlegs,'distinct_fixtures':distinct,
                    'requests':0,'first_at':at,'last_at':at,'request_times':[],'request_policy':[]}
            m=markets[ticker];m['requests']+=1;m['last_at']=at
            m['request_times'].append(at);m['request_policy'].append(state)
        if n%1000000==0:print(json.dumps({'requests':n,'traded_markets_mapped':len(markets),'elapsed':round(time.time()-started)}),flush=True)
    write('request_audit.json',{'requests_scanned':n,'statistics':{k:dict(v) for k,v in stats.items()},
        'traded_tickers':len(wanted),'traded_tickers_with_football_identity':len(markets),'classification_tickers':len(classifications),
        'blacklist_basis':'causal reconstruction of offline sniffer policy; not production sanctions'})
    write('traded_market_requests.json.gz',markets)
    write('blacklist_history.json.gz',dict(history))
    print(json.dumps({'complete':True,'requests':n,'markets':len(markets),'elapsed':time.time()-started}),flush=True)

def public_get(endpoint,params=None):
    from rate_limit import pace
    url=endpoint if endpoint.startswith('https://') else 'https://external-api.kalshi.com/trade-api/v2'+endpoint
    params=params or {};key=hashlib.sha256(json.dumps([url,params],sort_keys=True).encode()).hexdigest()
    folder=OUT/'public_evidence';folder.mkdir(parents=True,exist_ok=True);path=folder/(key+'.json.gz')
    if path.exists():
        with gzip.open(path,'rt') as f:env=json.load(f)
        if env['status']==200:return env['payload']
    for attempt in range(4):
        pace()
        try:
            r=http.get(url,params=params,timeout=30)
            if r.status_code==429 or r.status_code>=500:
                time.sleep(2**attempt);continue
            env={'url':r.url,'params':params,'status':r.status_code,'retrieved_at':time.time(),
                 'response_sha256':hashlib.sha256(r.content).hexdigest(),'payload':r.json()}
            with gzip.open(path,'wt') as f:json.dump(env,f,separators=(',',':'))
            r.raise_for_status();return env['payload']
        except http.RequestException:
            if attempt==3:raise
            time.sleep(2**attempt)
    raise RuntimeError('public GET exhausted '+url)

def gamma():
    events=[]
    for offset in range(0,2000,100):
        rows=public_get('https://gamma-api.polymarket.com/events',{'tag_id':100351,
            'end_date_min':'2026-09-08T00:00:00Z','end_date_max':'2026-09-14T23:59:59Z','limit':100,'offset':offset})
        events.extend(rows)
        if len(rows)<100:break
    else:raise ValueError('Gamma pagination limit')
    write('cfb_events.json.gz',events);print('CFB events',len(events),flush=True)

def production_policy():
    """Production duplicate-burst cooldown, independent of sniffer policy."""
    markets=read('traded_market_requests.json.gz');labels=defaultdict(list);intervals=defaultdict(list)
    db=sqlite3.connect((ROOT/'data/derived/rfq_sniffer/evidence_v2.sqlite').as_uri()+'?mode=ro',uri=True)
    db.execute('PRAGMA cache_size=-64000')
    windows=defaultdict(deque);counts=defaultdict(Counter);state={};n=0;started=time.time()
    @lru_cache(maxsize=100000)
    def signature(blob):
        legs=json.loads(zlib.decompress(blob))
        return hashlib.sha256(json.dumps(sorted((l[0],l[1]) for l in legs),separators=(',',':')).encode()).digest()
    for ticker,blob,at,creator in db.execute('SELECT ticker,legs,at,creator FROM requests WHERE at>=? AND at<? ORDER BY at',(START,END)):
        n+=1
        s=state.setdefault(creator,[-1e30,0,0.])  # last burst, bursts since cooldown, expiry
        # Gate uses strictly previous transitions, before this request.
        if ticker in markets:labels[ticker].append(at<s[2])
        w=windows[creator];c=counts[creator];sig=signature(blob)
        while w and w[0][0]<=at-60:
            _,old=w.popleft();c[old]-=1
            if not c[old]:del c[old]
        w.append((at,sig));c[sig]+=1
        if len(w)>=30 and c[sig]/len(w)>=.8 and at-s[0]>=60:
            s[0]=at;s[1]+=1
            if at>=s[2] and s[1]>=3:
                s[2]=at+3600;s[1]=0;intervals[creator].append((at,s[2]))
        if n%3000000==0:print('production creator replay',n,round(time.time()-started),flush=True)
    assert all(len(labels[t])==m['requests'] for t,m in markets.items())
    write('production_request_policy.json.gz',dict(labels))
    write('production_cooldowns.json.gz',dict(intervals))
    print('production cooldown creators',len(intervals),flush=True)

def scalar_audit():
    """Known settlement factors on original RFQs; no inferred fill or fair."""
    db=sqlite3.connect((ROOT/'data/derived/rfq_sniffer/evidence_v2.sqlite').as_uri()+'?mode=ro',uri=True)
    lower=datetime(2026,9,12,tzinfo=ZONE).timestamp();stats=defaultdict(Counter)
    @lru_cache(maxsize=100000)
    def structure(blob):
        ls=json.loads(zlib.decompress(blob));sport,n,distinct=classify(ls)
        values=[float(l[2]) if l[1]=='yes' else 1-float(l[2]) for l in ls if len(l)>2 and l[2]!='']
        unknown=[l for l in ls if len(l)<=2 or l[2]=='']
        return sport,n,len(unknown),bool(values),any(v==0 for v in values),len({l[0].split('-')[1] for l in unknown})
    n=0
    for blob,at in db.execute('SELECT legs,at FROM requests WHERE at>=? AND at<? ORDER BY at',(lower,END)):
        n+=1;sport,total,unknown,known,zero,fixtures=structure(blob)
        if sport not in ('NFL','CFB'):continue
        day=datetime.fromtimestamp(at,ZONE).date().isoformat();s=stats[day+'|'+sport]
        s['requests']+=1;s['raw_legs_'+str(total)]+=1;s['unknown_legs_'+str(unknown)]+=1
        if known:s['with_explicit_settled_legs']+=1
        if zero:s['known_zero_payoff_factor']+=1
        elif known:
            s['nonzero_scalar_unknown_legs_'+str(unknown)]+=1
            if unknown==1:s['scalar_reduction_to_one_unknown_leg']+=1
            if 2<=unknown<=4 and fixtures==unknown:s['scalar_reduction_to_2_to_4_distinct_unknown_fixtures']+=1
        if n%3000000==0:print('scalar audit',n,flush=True)
    write('scalar_audit.json',{k:dict(v) for k,v in stats.items()});print('scalar audit done',n,flush=True)

def metadata():
    markets=read('traded_market_requests.json.gz')
    combos=sorted(t for t,m in markets.items() if m['sport'] in ('NFL','CFB'))
    legs=sorted({l[0] for t in combos for l in markets[t]['legs']})
    def batches(tickers):
        rows={}
        groups=[tickers[i:i+100] for i in range(0,len(tickers),100)]
        def fetch(batch):
            result=public_get('/markets',{'tickers':','.join(batch),'limit':1000})
            if result.get('cursor'):raise ValueError('unexpected metadata pagination')
            return result['markets']
        with ThreadPoolExecutor(max_workers=3) as pool:
            for i,result in enumerate(pool.map(fetch,groups)):
                for m in result:rows[m['ticker']]=m
                if i%20==0:print('metadata',i+1,'/',len(groups),'returned',len(rows),flush=True)
        return rows
    native=batches(combos);write('combo_metadata.json.gz',native)
    native_legs=batches(legs);write('leg_metadata.json.gz',native_legs)
    write('metadata_audit.json',{'requested_combos':len(combos),'returned_combos':len(native),
        'requested_legs':len(legs),'returned_legs':len(native_legs),
        'missing_combos':sorted(set(combos)-set(native)),'missing_legs':sorted(set(legs)-set(native_legs))})

def fixtures():
    from combos.matching import fixture_teams,norm
    legs=read('leg_metadata.json.gz');events=read('cfb_events.json.gz');pm=defaultdict(list)
    for e in events:
        ml=[m for m in e.get('markets',[]) if m.get('sportsMarketType')=='moneyline']
        if len(ml)==1 and e.get('startTime'):
            teams=frozenset(norm(x) for x in json.loads(ml[0]['outcomes']))
            pm[(teams,e['slug'][-10:])].append(e)
    starts={};refs={};missing=[]
    config=json.loads((ROOT/'config/runtime_nfl_authorized_shadow_20260910.json').read_text())
    for m in config['mappings']:
        fixture=m['kalshi_ticker'].split('-')[1];starts[fixture]=m['start_at'];refs[fixture]='saved_reviewed_NFL_mapping'
    for ticker,m in legs.items():
        fixture=ticker.split('-')[1]
        if not ticker.startswith('KXNCAAF') or fixture in starts:continue
        day=datetime.strptime(fixture[:7],'%y%b%d').date().isoformat()
        candidates=pm.get((fixture_teams(m),day),[])
        unique={e['startTime'] for e in candidates}
        if len(unique)==1:
            starts[fixture]=datetime.fromisoformat(next(iter(unique)).replace('Z','+00:00')).timestamp()
            refs[fixture]=[e['slug'] for e in candidates]
    for ticker in legs:
        if ticker.split('-')[1] not in starts:missing.append(ticker)
    write('fixture_starts.json',{'starts':starts,'references':refs,'unmapped_legs':missing})
    print('fixture starts',len(starts),'unmapped legs',len(missing),flush=True)

FAMILIES={p+s for p in ('KXNFL','KXNCAAF') for s in ('GAME','SPREAD','TOTAL','TEAMTOTAL','1H','1HSPREAD','1HTOTAL','1Q','1QSPREAD','1QTOTAL')}

def candles(max_legs=4):
    markets=read('traded_market_requests.json.gz');starts=json.loads((OUT/'fixture_starts.json').read_text())['starts']
    jobs=[];needed=defaultdict(set)
    for path in sorted(OUT.glob('tape_*.json.gz')):
        tape=read(path.name);day=tape['day']
        for t in tape['trades']:
            m=markets.get(t['market_ticker']);at=float(t.get('ts_ms',t['ts']*1000))/1000
            if not m or m['sport'] not in ('NFL','CFB') or not m['distinct_fixtures']:continue
            if max_legs is not None and not 2<=m['leg_count']<=max_legs:continue
            if any(l[0].split('-')[0] not in FAMILIES for l in m['legs']):continue
            if any(starts.get(l[0].split('-')[1],0)<=at+60 for l in m['legs']):continue
            needed[day].update(l[0] for l in m['legs'])
        lo=int(tape['started_at'])-600;hi=int(tape['ended_at'])+600
        tickers=sorted(needed[day])
        for offset in range(0,len(tickers),60):jobs.append((day,lo,hi,tickers[offset:offset+60]))
    def fetch(job):
        day,lo,hi,batch=job
        result=public_get('/markets/candlesticks',{'market_tickers':','.join(batch),'start_ts':lo,'end_ts':hi,
                'period_interval':1,'include_latest_before_start':'true'})
        return day,result
    results=defaultdict(dict)
    with ThreadPoolExecutor(max_workers=3) as pool:
        for i,(day,result) in enumerate(pool.map(fetch,jobs)):
            for m in result['markets']:results[day][m['market_ticker']]=m['candlesticks']
            if i%10==0:print('candles',i+1,'/',len(jobs),flush=True)
    for day,rows in results.items():write('candles_'+day+'.json.gz',rows)
    write('candle_audit.json',{'needed':{d:len(v) for d,v in needed.items()},
        'returned':{d:len(v) for d,v in results.items()},'batches':len(jobs),'publication_delay_seconds':60})

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['trades','requests','gamma','metadata','fixtures','candles','production_policy','scalar_audit']);a=p.parse_args()
    globals()[a.stage]()

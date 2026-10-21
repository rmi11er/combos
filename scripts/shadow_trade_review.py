"""Read-only quote/public-tape review; writes separate research artifacts."""
import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
import datetime as dt
import hashlib
import json
from pathlib import Path
import sqlite3
import time
import zlib
import requests

def decode(raw):
    return json.loads(zlib.decompress(raw))

def stamp(s):
    return dt.datetime.fromisoformat(s.replace('Z','+00:00')).timestamp()

def write(path, value):
    path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')

def extract(paths, cutoff):
    quotes=[]; marks=[]; runs=[]
    for path in paths:
        c=sqlite3.connect('file:'+str(path.resolve())+'?mode=ro',uri=True,timeout=10)
        name=path.parent.name
        statuses=[list(r) for r in c.execute("SELECT json_extract(result,'$.status'),json_extract(result,'$.reason'),COUNT(*) FROM decisions GROUP BY 1,2")]
        manifest=json.loads(c.execute("SELECT value FROM state WHERE owner='runtime' AND key='manifest'").fetchone()[0])
        config=manifest['config']
        tail=c.execute('SELECT seq,received_at FROM events ORDER BY seq DESC LIMIT 1').fetchone()
        consumers=[dict(name=n,seq=seq,lag_events=tail[0]-seq) for n,seq in c.execute('SELECT name,seq FROM consumers')]
        runs.append(dict(run=name,decisions=statuses,event_tail=list(tail),consumers=consumers,
            markout_status_counts=dict(c.execute('SELECT status,COUNT(*) FROM markouts GROUP BY status').fetchall()),
            correlation_rho=config.get('correlation_rho'),correlation_tail=config.get('correlation_tail'),creator_policy=config.get('creator_policy'),capture_filter='Only collection-candidate RFQs retained; creator history excludes out-of-scope requests.'))
        local={}
        query="""SELECT d.source_seq,e.payload FROM decisions d JOIN events e
            ON e.seq=json_extract(d.result,'$.decision_event_seq')
            WHERE json_extract(d.result,'$.status') IN ('shadow_quote','shadow_quote_blocked')"""
        for seq,raw in c.execute(query):
            d=decode(raw)
            if d['decision_completed_at']>cutoff:continue
            d['run']=name; d['quote_key']=f'{name}:{seq}'
            d['valid_until']=min(d['expires_at'],cutoff)
            local[seq]=d;quotes.append(d)
        for raw, in c.execute("SELECT payload FROM events WHERE kind='quote_invalidated'"):
            d=decode(raw)
            # Resolve via reservation ID rather than assuming event schema fields.
            rid=d.get('reservation_id')
            for q in local.values():
                if rid and q.get('reservation_id')==rid:
                    q['invalidation']=d
        for seq,at,raw in c.execute("SELECT seq,received_at,payload FROM events WHERE kind='quote_invalidated'"):
            d=decode(raw)
            for q in local.values():
                if d.get('reservation_id') and q.get('reservation_id')==d['reservation_id']:
                    q['valid_until']=min(q['valid_until'],at)
        for raw, in c.execute("SELECT payload FROM events WHERE kind='markout'"):
            m=decode(raw)
            if m.get('decision_seq') in local:
                m.pop('pricing',None);m['quote_key']=local[m['decision_seq']]['quote_key'];marks.append(m)
        c.close()
    return quotes,marks,runs

def acquire(ticker, lo, hi, folder):
    path=folder/(hashlib.sha256(ticker.encode()).hexdigest()+'.json')
    if path.exists():
        old=json.loads(path.read_text())
        if old['lo']==lo and old['hi']==hi and old['complete']:return old
    result=dict(ticker=ticker,lo=lo,hi=hi,complete=False,pages=[],trades=[])
    session=requests.Session(); cursor='';seen=set()
    try:
        for _ in range(100):
            params=dict(ticker=ticker,min_ts=int(lo)-1,max_ts=int(hi)+1,limit=1000)
            if cursor:params['cursor']=cursor
            for attempt in range(5):
                r=session.get('https://external-api.kalshi.com/trade-api/v2/markets/trades',params=params,timeout=20)
                if r.status_code==429 or r.status_code>=500:time.sleep(1+attempt);continue
                r.raise_for_status();break
            else:raise RuntimeError('request_retries_exhausted')
            data=r.json();result['pages'].append(dict(url=r.url,retrieved_at=time.time(),payload=data))
            result['trades'].extend(data['trades']);cursor=data.get('cursor')
            if cursor=='':result['complete']=True;break
            if not isinstance(cursor,str) or cursor in seen:raise RuntimeError('invalid_cursor')
            seen.add(cursor)
    except Exception as e:result['error']=type(e).__name__
    finally:session.close()
    write(path,result)
    return result

def match(quotes,tapes,latency):
    qs=defaultdict(list);fills=[]
    for q in quotes:
        if q['status']=='shadow_quote':qs[q['market_ticker']].append(q)
    remaining={q['quote_key']:q['quantity'] for q in quotes}
    for ticker,group in qs.items():
        group.sort(key=lambda q:q['decision_completed_at'])
        seen=set()
        for t in sorted(tapes[ticker]['trades'],key=lambda t:t['created_time']):
            if t['trade_id'] in seen:continue
            seen.add(t['trade_id'])
            side=t.get('taker_outcome_side') or t.get('taker_side')
            if side!='yes':continue
            at=stamp(t['created_time']);price=float(t['yes_price_dollars']);available=float(t['count_fp'])
            for q in group:
                if not(q['decision_completed_at']+latency<=at<q['valid_until']):continue
                if price+1e-9<q['yes_ask']:continue
                quantity=min(available,remaining[q['quote_key']])
                if quantity<=0:continue
                remaining[q['quote_key']]-=quantity;available-=quantity
                fee=q['economics']['maker_fee']/q['quantity']
                fills.append(dict(quote_key=q['quote_key'],ticker=ticker,trade_id=t['trade_id'],at=at,
                    public_yes_price=price,hypothetical_yes_price=q['yes_ask'],quantity=quantity,
                    point_edge_dollars=quantity*(q['yes_ask']-q['pricing']['joint']['point']-fee),
                    charged_edge_dollars=quantity*q['economics']['expected_edge']/q['quantity'],
                    public_price_edge_at_quote_fair_dollars=quantity*(price-q['pricing']['joint']['point']-fee),
                    liability_dollars=quantity*(1-q['yes_ask'])+quantity*fee))
                if available<=0:break
    return sorted(fills,key=lambda f:f['at'])

def main():
    p=argparse.ArgumentParser();p.add_argument('--db',type=Path,action='append',required=True)
    p.add_argument('--out',type=Path,required=True);p.add_argument('--cutoff',required=True)
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True);cutoff=stamp(a.cutoff)
    quotes,marks,runs=extract(a.db,cutoff)
    with (a.out/'quotes.jsonl').open('w') as f:
        for q in quotes:f.write(json.dumps(q,allow_nan=False)+'\n')
    with (a.out/'markouts.jsonl').open('w') as f:
        for m in marks:f.write(json.dumps(m,allow_nan=False)+'\n')
    print('extracted',len(quotes),'quotes',len(marks),'markouts',flush=True)
    folder=a.out/'public_tape';folder.mkdir(exist_ok=True)
    groups=defaultdict(list)
    for q in quotes:groups[q['market_ticker']].append(q)
    jobs=[(t,min(q['received_at'] for q in qs),cutoff,folder) for t,qs in groups.items()]
    tapes={}
    with ThreadPoolExecutor(max_workers=4) as pool:
        for i,result in enumerate(pool.map(lambda job:acquire(*job),jobs)):
            tapes[result['ticker']]=result
            if i%25==0:print('tape',i+1,'/',len(jobs),flush=True)
    accepted=[q for q in quotes if q['status']=='shadow_quote']
    observations=[];comparisons=[]
    for q in quotes:
        tape=tapes[q['market_ticker']]
        after=[t for t in tape['trades'] if q['decision_completed_at']<=stamp(t['created_time'])<=cutoff]
        active=[t for t in after if stamp(t['created_time'])<q['valid_until']]
        for t in active:
            price=float(t['yes_price_dollars'])
            comparisons.append(dict(quote_key=q['quote_key'],ticker=q['market_ticker'],trade_id=t['trade_id'],
                quote_yes_ask=q['yes_ask'],trade_yes_price=price,trade_at=stamp(t['created_time']),
                taker_side=t.get('taker_outcome_side') or t.get('taker_side'),
                gap_cents=100*(q['yes_ask']-price),
                trade_minus_point_cents=100*(price-q['pricing']['joint']['point']),
                trade_minus_stressed_reference_cents=100*(price-q['quote_reference']['value']),
                correlation_charge_cents=q['pricing']['dependence']['reserve_cents']))
        observations.append(dict(quote_key=q['quote_key'],complete=tape['complete'],post_quote_public_trades=len(after),
            trades_during_quote_life=len(active),first_post_quote_trade=after[-1] if after else None))
    write(a.out/'quote_trade_context.json',observations)
    write(a.out/'active_quote_trade_comparisons.json',comparisons)
    stats={}
    for delay in (0,.1,.25,.5,1):
        fills=match(quotes,tapes,delay);write(a.out/f'fill_proxy_{delay}s.json',fills)
        stats[str(delay)]=dict(matched_quotes=len({f['quote_key'] for f in fills}),
            public_trade_ids=len({f['trade_id'] for f in fills}),contracts=sum(f['quantity'] for f in fills),
            point_edge_dollars=sum(f['point_edge_dollars'] for f in fills),
            charged_edge_dollars=sum(f['charged_edge_dollars'] for f in fills),
            liability_if_held=sum(f['liability_dollars'] for f in fills))
    import numpy as np
    def distribution(values):
        return dict(n=len(values),mean=float(np.mean(values)),p50=float(np.median(values)),p95=float(np.percentile(values,95))) if values else dict(n=0)
    by_h=defaultdict(list)
    for m in marks:by_h[str(m['horizon_seconds'])].append(m)
    markstats={h:dict(total=len(ms),observed=sum(m['status']=='observed' for m in ms),
        adverse_move_cents=distribution([m['adverse_move_cents'] for m in ms if m['status']=='observed']),
        residual_charged_edge_cents=distribution([100*m['markout_net_edge_per_share'] for m in ms if m['status']=='observed']),
        unavailable_reasons=dict(Counter(m.get('reason') for m in ms if m['status']!='observed'))) for h,ms in by_h.items()}
    summary=dict(cutoff=a.cutoff,runs=runs,quote_count=len(accepted),unique_quoted_markets=len({q['market_ticker'] for q in accepted}),
        blocked_counterfactual_quotes=len(quotes)-len(accepted),complete_tapes=sum(t['complete'] for t in tapes.values()),total_tapes=len(tapes),
        quotes_with_later_public_trades=sum(o['post_quote_public_trades']>0 for o in observations),
        quotes_with_trade_during_life=sum(o['trades_during_quote_life']>0 for o in observations),
        latency_seconds=distribution([q['completed_processing_lag_seconds'] for q in accepted]),
        charged_edge_cents=distribution([100*q['economics']['expected_edge']/q['quantity'] for q in accepted]),
        point_edge_cents=distribution([100*q['point_economics']['expected_edge']/q['quantity'] for q in accepted]),
        correlation_charge_cents=distribution([q['pricing']['dependence']['reserve_cents'] for q in accepted]),
        total_reference_reserve_cents=distribution([100*q['quote_reference']['reserve_per_share'] for q in accepted]),
        leg_counts=dict(Counter(q['leg_count'] for q in accepted)),markouts=markstats,fill_proxy_sensitivity=stats)
    summary['active_trade_comparison']=dict(quote_trade_pairs=len(comparisons),unique_trades=len({r['trade_id'] for r in comparisons}),
        unique_markets=len({r['ticker'] for r in comparisons}),
        gap_cents=distribution([r['gap_cents'] for r in comparisons]),
        trade_minus_point_cents=distribution([r['trade_minus_point_cents'] for r in comparisons]),
        trade_minus_stressed_reference_cents=distribution([r['trade_minus_stressed_reference_cents'] for r in comparisons]))
    write(a.out/'summary.json',summary)
    print(json.dumps(summary,indent=2),flush=True)

if __name__=='__main__':main()

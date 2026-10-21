"""Compare expanded replay with complete session public tape."""
import gzip,json,math
from pathlib import Path
from collections import Counter,defaultdict
from bisect import bisect_left,bisect_right
import numpy as np
from shadow_trade_review import match,stamp
from corrected_shadow_review import fillstats,funded,dist
ROOT=Path(__file__).resolve().parents[1];D=ROOT/'runs/shadow_exchange_fallback_20260909'
def write(name,value):(D/name).write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')
quotes=[json.loads(l) for l in (D/'quotes.jsonl').open()];qs={q['quote_key']:q for q in quotes}
tapes={q['market_ticker']:{'trades':[]} for q in quotes};seen=set();allcounts=Counter();mvecounts=Counter();captured=Counter()
manifest=json.loads((D/'public_session/manifest.json').read_text())
assert len(manifest)==38 and all(r['complete'] for r in manifest)
for p in sorted((D/'public_session').glob('*.json.gz')):
    with gzip.open(p,'rt') as f:data=json.load(f)['payload']
    for t in data['trades']:
        if t['trade_id'] in seen or not 1788988292<=stamp(t['created_time'])<=1788999600:continue
        seen.add(t['trade_id']);side=t.get('taker_outcome_side') or t.get('taker_side');qty=float(t['count_fp']);price=float(t['yes_price_dollars'])
        counts={'trades':1,'contracts':qty,'yes_seller_collateral':qty*(1-price),'block_trades':int(t.get('is_block_trade') is True)}
        allcounts.update(counts)
        if t['ticker'].startswith('KXMVE'):mvecounts.update(counts)
        if t['ticker'] in tapes:
            tapes[t['ticker']]['trades'].append(t);captured.update(counts)
            if side=='yes':captured['yes_taker_seller_collateral']+=qty*(1-price)
del seen
for ticker,tape in tapes.items():tape['trades'].sort(key=lambda t:t['created_time'])
with (D/'quoted_market_trades.jsonl').open('w') as f:
    for ticker,tape in tapes.items():
        for t in tape['trades']:f.write(json.dumps(t)+'\n')
print('public_tape',dict(allcounts),'quoted',dict(captured),flush=True)
scenarios={};base=[]
for delay in (0,.25,1):
    fills=match(quotes,tapes,delay);scenarios[str(delay)]=fillstats(fills)
    if delay==0:base=fills
write('potential_fills.json',base)
budget=funded(base,qs);write('held_inventory.json',budget)
by_market=defaultdict(list)
for f in base:by_market[f['ticker']].append(f)
markets=[]
for ticker,fs in by_market.items():
    q=qs[fs[0]['quote_key']];qty=sum(f['quantity'] for f in fs)
    markets.append(dict(ticker=ticker,legs=q['request']['mve_selected_legs'],**fillstats(fs),
        our_ask_cents=100*sum(f['quantity']*f['hypothetical_yes_price'] for f in fs)/qty,
        public_price_cents=100*sum(f['quantity']*f['public_yes_price'] for f in fs)/qty))
markets.sort(key=lambda r:r['collateral_dollars'],reverse=True);write('market_breakdown.json',markets)
groups=defaultdict(list)
for q in quotes:groups[q['market_ticker']].append(q)
pairs=[];active={}
for ticker,group in groups.items():
    group.sort(key=lambda q:q['decision_completed_at']);times=[q['decision_completed_at'] for q in group]
    for t in tapes[ticker]['trades']:
        at=stamp(t['created_time']);price=float(t['yes_price_dollars'])
        for q in group[bisect_left(times,at-3):bisect_right(times,at)]:
            if at>=q['valid_until']:continue
            active[t['trade_id']]=t
            pairs.append(dict(quote_key=q['quote_key'],ticker=ticker,trade_id=t['trade_id'],
                public_minus_ask_cents=100*(price-q['yes_ask']),public_minus_fair_cents=100*(price-q['pricing']['joint']['point']),
                side=t.get('taker_outcome_side') or t.get('taker_side')))
write('active_price_comparisons.json',pairs)
publicmarks=[]
for f in base:
    trades=tapes[f['ticker']]['trades'];times=[stamp(t['created_time']) for t in trades]
    for h in (5,30,120):
        i=bisect_left(times,f['at']+h)
        if i<len(times) and times[i]<=min(f['at']+h+30,1788999600):
            price=float(trades[i]['yes_price_dollars']);publicmarks.append(dict(quote_key=f['quote_key'],horizon=h,
                quantity=f['quantity'],markout_cents=100*(f['hypothetical_yes_price']-price),
                dollars=f['quantity']*(f['hypothetical_yes_price']-price),benchmark_trade_id=trades[i]['trade_id']))
write('public_marks.json',publicmarks)
result=dict(public_session=dict(allcounts),all_combo_public_session=dict(mvecounts),quoted_market_public_session=dict(captured),
    quotes=len(quotes),markets=len(tapes),markets_with_public_trades=sum(bool(t['trades']) for t in tapes.values()),
    scenarios=scenarios,held_inventory={**fillstats(budget['fills']),'risk_rejected_allocations':len(budget['rejected'])},
    active_window_trades=len(active),active_window_seller_collateral=sum(float(t['count_fp'])*(1-float(t['yes_price_dollars'])) for t in active.values()),
    active_window_yes_taker_collateral=sum(float(t['count_fp'])*(1-float(t['yes_price_dollars'])) for t in active.values() if (t.get('taker_outcome_side') or t.get('taker_side'))=='yes'),
    active_comparisons=dict(pairs=len(pairs),public_minus_ask_cents=dist([p['public_minus_ask_cents'] for p in pairs]),
        price_compatible_yes_pairs=sum(p['public_minus_ask_cents']>=-1e-9 and p['side']=='yes' for p in pairs)),
    public_marks={str(h):dict(allocations=sum(m['horizon']==h for m in publicmarks),
        contracts=sum(m['quantity'] for m in publicmarks if m['horizon']==h),dollars=sum(m['dollars'] for m in publicmarks if m['horizon']==h)) for h in (5,30,120)},
    original_reasons_of_new_quotes=dict(Counter(q['original_reason'] for q in quotes)))
write('performance.json',result);print(json.dumps(result,indent=2))

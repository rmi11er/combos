"""Offline NFL research panel: fixed-source price marks and explicit censoring.

Never changes trading configuration. All prices remain historical candle proxies.
"""
import argparse
from collections import Counter
from datetime import datetime
import gzip
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from combos.kalshi_history import KalshiHistory


def product_selected(legs, points):
    if len(legs) != len(points):
        raise ValueError('leg/point mismatch')
    if any(l['side'] not in ('yes', 'no') for l in legs):
        raise ValueError('unknown side')
    if any(not math.isfinite(p) or not 0 <= p <= 1 for p in points):
        raise ValueError('invalid probability')
    return math.prod(p if l['side'] == 'yes' else 1-p for l,p in zip(legs, points))


def mark_at(history, legs, at, first_start):
    if at >= first_start:
        return {'status': 'crosses_first_kickoff'}
    try:
        states = [history.at(l['market_ticker'], at) for l in legs]
    except ValueError as exc:
        return {'status': 'unavailable', 'reason': str(exc)}
    assert all(s['available_at'] <= at for s in states)
    return {'status': 'observed', 'at': at,
            'fair': product_selected(legs, [s['interval']['point'] for s in states]),
            'selected_mids': [s['interval']['point'] if l['side']=='yes' else 1-s['interval']['point'] for l,s in zip(legs,states)],
            'selected_bids': [s['yes_bid'] if l['side']=='yes' else 1-s['yes_ask'] for l,s in zip(legs,states)],
            'selected_asks': [s['yes_ask'] if l['side']=='yes' else 1-s['yes_bid'] for l,s in zip(legs,states)],
            'max_age_seconds': max(s['raw_age_seconds'] for s in states),
            'source_at': [s['source_at'] for s in states]}


def run(out):
    source = ROOT/'runs/nfl_moneyline_replay_20260907/jan5_18'
    paths = [source/'opportunities.json', source/'pricing_context.jsonl.gz']
    data = json.loads(paths[0].read_text())
    rows = {r['evaluation_id']: r for r in data['opportunities'] if r['model']=='kalshi'}
    assert len(rows) == sum(r['model']=='kalshi' for r in data['opportunities'])
    history = KalshiHistory(ROOT/'runs/nfl_playoffs_history_20260907/exchange_history',
                            fallback_dirs=[], publication_delay=60, taker_rate=.07, cache_size=32)
    out.mkdir(parents=True, exist_ok=True)
    counts = Counter(); seen = set()
    with gzip.open(paths[1], 'rt') as contexts, gzip.open(out/'nfl_panel.jsonl.gz', 'wt') as dest:
        for line in contexts:
            c = json.loads(line); row = rows[c['evaluation_id']]
            assert c['evaluation_id'] not in seen
            seen.add(c['evaluation_id'])
            legs = c['legs']; entry = product_selected(legs, [s['kalshi']['interval']['point'] for s in c['sources']])
            assert abs(entry-row['fair_point']) < 1e-12
            first = row['source']['start_at']; at = row['at']
            marks = {}
            for label, future_at in [(str(h), at+h) for h in (60,300,900,3600)]+[('close',first-60)]:
                if future_at <= at:
                    m = {'status':'no_future_pregame_reference'}
                else:
                    m = mark_at(history, legs, future_at, first)
                if m['status']=='observed':
                    m['seller_net_markout_cents'] = 100*(row['yes_price']-m['fair']-row['maker_fee']/row['quantity'])
                    m['seller_fair_move_cents'] = 100*(entry-m['fair'])
                counts[(label,m['status'])] += 1; marks[label] = m
            selected = []
            asks = []; bids = []; spreads = []
            for leg,s in zip(legs,c['sources']):
                fixture = s['mapping']['fixture']
                team = s['mapping']['team']
                if leg['side']=='no':
                    team = fixture['home'] if team==fixture['away'] else fixture['away']
                assert team in (fixture['home'],fixture['away'])
                key = fixture['scheduled_start'][:10]+':'+ '-'.join(sorted((fixture['home_code'],fixture['away_code'])))
                selected.append([key, int(team==fixture['home'])])
                k = s['kalshi']; bid,ask = k['yes_bid'],k['yes_ask']
                bids.append(bid if leg['side']=='yes' else 1-ask)
                asks.append(ask if leg['side']=='yes' else 1-bid)
                spreads.append(ask-bid)
            assert len(set(f for f,_ in selected))==len(legs)
            record = {**row, 'selected_fixture_bits': selected,
                'entry_max_age_seconds':max(s['kalshi']['raw_age_seconds'] for s in c['sources']),
                'leg_bids':bids,'leg_asks':asks,'leg_mids':[(a+b)/2 for a,b in zip(asks,bids)],'mean_leg_spread':sum(spreads)/len(spreads),
                'hours_to_first_start':(first-at)/3600,'marks':marks}
            dest.write(json.dumps(record,allow_nan=False)+'\n')
            if len(seen)%5000==0: print('marked',len(seen),flush=True)
    assert seen==rows.keys()
    files = paths+sorted((history.data_run/'kalshi_parts').glob('*.json.gz'))+[Path(__file__)]
    summary = {'prints':len(seen), 'dates':data['completed_dates'],
        'coverage':[{'horizon':h,'status':s,'prints':n} for (h,s),n in sorted(counts.items())],
        'hashes':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
        'limitations':['Common priced distinct-fixture moneyline YES-taker cohort, not all NFL tape.',
            'Fixed Kalshi independent midpoint model; no blend-weight changes.',
            'Minute candles plus 60s availability lag; raw source age retained, not verified live freshness.',
            'Entry fee assumptions retained; no actual execution or acceptance model.',
            'Close is the available reference 60s before conservative scheduled first kickoff.']}
    (out/'extraction.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps({k:v for k,v in summary.items() if k!='hashes'},indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--out',type=Path,required=True)
    run(p.parse_args().out)

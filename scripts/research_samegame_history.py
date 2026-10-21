"""Executed-tape same-game opportunity and conservative offset study.

No independence price or acceptance claim. Same-native-market scalar-safe bounds.
"""
import argparse
from collections import defaultdict,Counter
from datetime import datetime
from decimal import Decimal
import gzip
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'scripts'))
from combos.research_spend_risk import payout_upper
from combos.fees import kalshi_fill_fee
from nfl_moneyline_replay import certified_days


def bound(rows):
    grouped=defaultdict(float)
    for r in rows:grouped[tuple(sorted(r['legs']))]+=r['quantity']
    result=payout_upper(list(grouped),list(grouped.values()),time_limit=30)
    principal=sum(r['quantity']*r['price'] for r in rows);fees=sum(r['maker_fee'] for r in rows)
    pnl=sum(r['quantity']*(r['price']-r['settlement'])-r['maker_fee'] for r in rows if r['settlement'] is not None)
    return {**result,'prints':len(rows),'unique_tickets':len(grouped),'principal':principal,'maker_fees':fees,
        'gross_seller_collateral':result['gross_payout_units']-principal+fees,
        'positive_loss_upper':max(0,result['payout_upper_units']-principal+fees),
        'hypothetical_sell_all_settlement_pnl':pnl,'unknown_outcomes':sum(r['settlement'] is None for r in rows)}


def run(out):
    groups=defaultdict(list);daily=[];seen=set()
    for date,cohort,summary,_ in certified_days(ROOT/'runs/nfl_playoffs_history_20260907'):
        markets=json.load(gzip.open(cohort/'combo_markets.json.gz','rt'));counts=Counter();handle=Counter()
        with gzip.open(cohort/'universe_trades.jsonl.gz','rt') as f:
            for line in f:
                r=json.loads(line);c=r['classification'];t=r['trade']
                counts['pure_nfl_prints']+=1
                if not (c['target_fixtures_only'] and c['fullgame_core'] and r['pregame_scheduled_proxy'] and 2<=c['nlegs']<=4):continue
                assert t['trade_id'] not in seen;seen.add(t['trade_id'])
                category='distinct' if c['distinct_fixtures'] else 'same_game_containing'
                counts[category]+=1;handle[category]+=float(t['count_fp'])*float(t['yes_price_dollars'])
                if c['distinct_fixtures'] or len(set(c['fixture_tokens']))!=1 or t.get('taker_side')!='yes':continue
                q=float(t['count_fp']);p=float(t['yes_price_dollars'])
                if q<=0 or not 0<p<1:continue
                counts['single_game_yes_taker']+=1
                legs=markets[t['ticker']]['mve_selected_legs']
                groups[c['fixture_tokens'][0]].append({'id':t['trade_id'],'at':datetime.fromisoformat(t['created_time'].replace('Z','+00:00')).timestamp(),
                    'quantity':q,'price':p,'legs':[(l['market_ticker'],l['side']) for l in legs],
                    'maker_fee':float(kalshi_fill_fee(t['count_fp'],1-Decimal(t['yes_price_dollars']),'.035')['net_fee']),
                    'settlement':None if r['settlement_value_dollars'] is None else float(r['settlement_value_dollars'])})
        daily.append({'date':date,'counts':dict(counts),'principal':dict(handle)});print(date,dict(counts),flush=True)
    results=[]
    for fixture,rows in sorted(groups.items()):
        rows.sort(key=lambda r:(r['at'],r['id']))
        for fraction in [.25,.5,1.]:
            subset=rows[:max(1,int(len(rows)*fraction))]
            entry={'fixture':fixture,'scenario':'chronological','print_fraction':fraction,**bound(subset)}
            results.append(entry);print(fixture,fraction,entry['prints'],entry['guaranteed_reduction_fraction'],flush=True)
        all_yes=[r for r in rows if all(s=='yes' for _,s in r['legs'])]
        if all_yes:results.append({'fixture':fixture,'scenario':'all_legs_yes_selection','print_fraction':1.,**bound(all_yes)})
    result={'daily':daily,'portfolio_bounds':results,'limitations':[
        'Fullgame moneyline/spread/total, pregame, 2-4 legs, target playoff fixtures; not all sports or all same-game products.',
        'Bounds use only complements of identical native markets and allow scalar leg settlement; no unverified score/parity constraints.',
        'Same-market product settlement is an explicit research payoff assumption; exceptional combo rules are not certified.',
        'Hypothetical seller of every observed YES-taker print, with archived .035 maker-fee scenario; no cash-constrained admission or joint fair model.',
        'Chronological fractions are fractions of prints, not elapsed time or filled probabilities.',
        'Bounded loss is not capital released by the exchange; no collateral credit.',
        'A positive bound reduction demonstrates structural offset, not accurate pricing or expected profitability.']}
    (out/'samegame_history.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);run(p.parse_args().out)

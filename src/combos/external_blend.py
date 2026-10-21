"""Strict adapter for externally supplied historical three-venue books.

Each JSONL record names the canonical Kalshi market ticker and requires a
verified payoff mapping, source reference, availability timestamps and
liquidity in common payout-dollar capacity. Raw YES-side books are widened
here. Pinnacle rows supply both opposing decimal odds instead of a fake book.
"""
from collections import defaultdict
import bisect,json
from pathlib import Path
from .pricing import Interval,VenueFair,fee_expanded_book,pinnacle_fair,liquidity_blend

class HistoricalBlend:
    def __init__(self,path:Path):
        self.data=defaultdict(list);self.times={}
        if not path.exists():return
        with path.open() as f:
            for line in f:
                row=json.loads(line)
                if row.get('mapping_verified') is not True or not row.get('source_reference'):raise ValueError('missing mapping/source evidence')
                venue=row['venue'];key=row['kalshi_market_ticker']
                if venue=='pinnacle':interval=pinnacle_fair(row['decimal_odds_yes'],row['decimal_odds_no'])
                elif venue in ['kalshi','polymarket']:interval=fee_expanded_book(row['yes_bid'],row['yes_ask'],row['historical_taker_rate'])
                else:raise ValueError('unexpected venue')
                v=VenueFair(venue,interval,float(row['available_at']),float(row['liquidity_payout_dollars']),float(row['liquidity_available_at']),key)
                self.data[(key,venue)].append(v)
        for key,rows in self.data.items():
            rows.sort(key=lambda r:r.available_at)
            if len({r.available_at for r in rows})!=len(rows):raise ValueError('duplicate venue availability timestamp')
            self.times[key]=[r.available_at for r in rows]

    def leg(self,ticker,side,at):
        values=[]
        for venue in ['kalshi','polymarket','pinnacle']:
            key=(ticker,venue);times=self.times.get(key,[]);i=bisect.bisect_right(times,at)-1
            if i<0:raise ValueError('required historical venue unavailable')
            values.append(self.data[key][i])
        fair=liquidity_blend(values,at,ticker)
        if side=='yes':return fair
        if side=='no':return Interval(1-fair.upper,1-fair.point,1-fair.lower)
        raise ValueError('invalid side')

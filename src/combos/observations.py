"""Venue-neutral, canonical-YES snapshots for historical and live research."""
from dataclasses import dataclass
import math
from .pricing import Interval, fee_expanded_book, pinnacle_fair
from .fees import taker_fee_context

VENUES = ('kalshi', 'polymarket', 'pinnacle')

@dataclass(frozen=True)
class Observation:
    market_key: str
    venue: str
    observed_at: float
    available_at: float
    active: bool
    interval: Interval | None
    bid_capacity: float | None
    ask_capacity: float | None
    source_reference: str
    mapping_reference: str
    fee_reference: str | None
    fee_context: dict | None = None
    freshness_context: dict | None = None

    @classmethod
    def from_record(cls, row):
        for field in ('market_key', 'source_reference', 'mapping_reference'):
            if not isinstance(row.get(field), str) or not row[field].strip():
                raise ValueError(f'missing {field}')
        venue = row['venue']
        if venue not in VENUES:
            raise ValueError('unsupported venue')
        observed, available = float(row['observed_at']), float(row['available_at'])
        if not all(math.isfinite(x) for x in (observed, available)) or available < observed:
            raise ValueError('invalid observation/availability chronology')
        if not isinstance(row.get('active'), bool):
            raise ValueError('active must be explicitly true or false')
        interval = bid_capacity = ask_capacity = fee_context = None
        if row['active']:
            if venue == 'pinnacle':
                yes, no = float(row['decimal_odds_yes']), float(row['decimal_odds_no'])
                interval = pinnacle_fair(yes, no)
                if row.get('limit_currency') != 'USD' or row.get('limit_unit') != 'stake':
                    raise ValueError('Pinnacle limits must be verified USD stake amounts')
                # Capacity on each opposing side, expressed as $1 payout shares.
                bid_capacity = float(row['max_stake_no']) * no
                ask_capacity = float(row['max_stake_yes']) * yes
            else:
                if not isinstance(row.get('fee_reference'), str) or not row['fee_reference'].strip():
                    raise ValueError('exchange fee schedule/version reference required')
                interval = fee_expanded_book(float(row['yes_bid']), float(row['yes_ask']), float(row['taker_rate']))
                if row.get('size_unit') != 'payout_dollars':
                    raise ValueError('exchange sizes must be $1 payout capacity')
                bid_capacity = float(row['yes_bid_size'])
                ask_capacity = float(row['yes_ask_size'])
            if not all(math.isfinite(x) and x > 0 for x in (bid_capacity, ask_capacity)):
                raise ValueError('missing positive two-sided capacity')
            if venue!='pinnacle' and row.get('fee_model') is not None:
                if row['fee_model']!='venue_cash_v2':raise ValueError('unsupported exchange fee model')
                if venue=='kalshi' and row.get('balance_precision') not in ('.0001','.01'):
                    raise ValueError('verified Kalshi balance precision required')
                fee_context=taker_fee_context(venue,row['yes_bid'],row['yes_ask'],bid_capacity,ask_capacity,
                    row['taker_rate'],row.get('balance_precision','.0001'))
                interval=Interval(max(0.,float(row['yes_bid'])-fee_context['sides']['bid']['conservative_fee_per_share']),
                    interval.point,min(1.,float(row['yes_ask'])+fee_context['sides']['ask']['conservative_fee_per_share']))
        return cls(row['market_key'], venue, observed, available, row['active'],
                   interval, bid_capacity, ask_capacity, row['source_reference'], row['mapping_reference'], row.get('fee_reference'),fee_context,
                   row.get('freshness_context'))

    def selected_interval(self, side):
        if self.interval is None:
            raise ValueError('inactive observation')
        if side == 'yes':
            return self.interval
        if side == 'no':
            return Interval(1-self.interval.upper, 1-self.interval.point, 1-self.interval.lower)
        raise ValueError('invalid side')

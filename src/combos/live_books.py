"""Reconstruct exchange ladders and emit the common observation contract."""
from decimal import Decimal
import math
from .observations import Observation


def number(value):
    d=Decimal(str(value))
    if not d.is_finite():raise ValueError('nonfinite book value')
    return d


class Books:
    def __init__(self,venue,mappings,clock_tolerance_seconds=.25):
        self.venue=venue;self.books={};self.sequences={}
        self.targets=None;self.awaiting_snapshots=set()
        self.clock_tolerance=clock_tolerance_seconds
        field='kalshi_ticker' if venue=='kalshi' else 'polymarket_yes_token'
        self.maps={m[field]:m for m in mappings if m.get(field)}

    def set_targets(self,targets):
        """Retire local ladders without mistaking in-flight deltas for a gap."""
        targets=set(targets)
        previous=self.targets if self.targets is not None else set(self.books)
        self.awaiting_snapshots=(self.awaiting_snapshots | (targets-previous)) & targets
        for ticker in previous-targets:self.books.pop(ticker,None)
        self.targets=targets

    def levels(self,rows):
        result={}
        for price,size in rows:
            p,q=number(price),number(size)
            if not 0<=p<=1 or q<0:raise ValueError('invalid book level')
            if q:result[p]=q
        return result

    def consume(self,payload,received_at,reference):
        touched=[];observed=received_at
        if self.venue=='kalshi':
            typ=payload.get('type');msg=payload.get('msg',{})
            sid,seq=payload.get('sid'),payload.get('seq')
            if sid is not None and seq is not None:
                if sid in self.sequences and seq!=self.sequences[sid]+1:raise ValueError('kalshi_sequence_gap')
                self.sequences[sid]=seq
            if typ not in ('orderbook_snapshot','orderbook_delta'):return []
            ticker=msg['market_ticker'];touched=[ticker]
            if self.targets is not None and (ticker not in self.targets or typ=='orderbook_delta' and ticker in self.awaiting_snapshots):
                return [('book_update_ignored',{'market_ticker':ticker,'source_reference':reference,
                    'reason':'unsubscribed_book' if ticker not in self.targets else 'awaiting_fresh_snapshot',
                    'observed_at':received_at})]
            if msg.get('ts_ms') is not None:observed=float(msg['ts_ms'])/1000
            if typ=='orderbook_snapshot':
                self.awaiting_snapshots.discard(ticker)
                # Live empty snapshots omit both ladder fields entirely.
                self.books[ticker]={'bid':self.levels(msg.get('yes_dollars_fp',[])),
                    'ask':{1-p:q for p,q in self.levels(msg.get('no_dollars_fp',[])).items()}}
            else:
                if ticker not in self.books:raise ValueError('delta_without_snapshot')
                price=number(msg['price_dollars']);delta=number(msg['delta_fp'])
                if msg['side'] not in ('yes','no') or not 0<=price<=1:raise ValueError('invalid delta')
                side='bid' if msg['side']=='yes' else 'ask';price=price if side=='bid' else 1-price
                levels=self.books[ticker][side];quantity=levels.get(price,Decimal(0))+delta
                if quantity<0:raise ValueError('negative_book_depth')
                if quantity:levels[price]=quantity
                else:levels.pop(price,None)
        else:
            typ=payload.get('event_type')
            if payload.get('timestamp') is not None:observed=float(payload['timestamp'])/1000
            if typ=='book':
                ticker=payload['asset_id'];touched=[ticker]
                self.books[ticker]={side:self.levels((r['price'],r['size']) for r in payload[field])
                    for side,field in (('bid','bids'),('ask','asks'))}
            elif typ=='price_change':
                for change in payload['price_changes']:
                    ticker=change['asset_id']
                    if ticker not in self.maps:continue
                    if ticker not in self.books:raise ValueError('polymarket_delta_without_snapshot')
                    if change['side'] not in ('BUY','SELL'):raise ValueError('invalid Polymarket side')
                    p,q=number(change['price']),number(change['size'])
                    if not 0<=p<=1 or q<0:raise ValueError('invalid Polymarket level')
                    levels=self.books[ticker]['bid' if change['side']=='BUY' else 'ask']
                    if q:levels[p]=q
                    else:levels.pop(p,None)
                    touched.append(ticker)
            elif typ=='market_resolved':
                for ticker in payload.get('assets_ids',[]):
                    if ticker in self.books:self.books[ticker]={'bid':{},'ask':{}};touched.append(ticker)
            else:return []
        if not math.isfinite(observed):raise ValueError('nonfinite_book_time')
        source_observed=observed
        clock_valid=source_observed-received_at<=self.clock_tolerance
        # Venue and host clocks differ. Preserve source time and conservatively
        # age the usable state; a large offset invalidates pricing, not capture.
        observed=min(observed,received_at)-self.clock_tolerance
        output=[]
        for ticker in set(touched):
            book=self.books[ticker];valid=bool(book['bid'] and book['ask']) and clock_valid
            top={'valid':valid,'observed_at':observed,'source_reference':reference,
                 'source_observed_at':source_observed,'source_clock_ahead_seconds':max(0,source_observed-received_at),
                 'clock_uncertainty_seconds':self.clock_tolerance}
            if not clock_valid:top['invalid_reason']='source_clock_offset_exceeds_tolerance'
            if valid:
                bid,ask=max(book['bid']),min(book['ask'])
                if bid>ask:raise ValueError('crossed_book')
                top.update(yes_bid=float(bid),yes_ask=float(ask),yes_bid_size=float(book['bid'][bid]),yes_ask_size=float(book['ask'][ask]))
            mapping=self.maps.get(ticker)
            if mapping:
                fees=mapping.get('fees',{}).get(self.venue)
                # Raw depth is retained even when fee metadata has not been reviewed.
                if not fees:continue
                if fees.get('valid_until') is not None and received_at>=fees['valid_until']:
                    valid=False;top['invalid_reason']='fee_metadata_expired'
                row={'market_key':mapping['market_key'],'venue':self.venue,'active':valid,
                     'observed_at':observed,'available_at':received_at,'mapping_reference':mapping['mapping_reference'],
                     'source_reference':reference,'fee_reference':fees['reference'],'taker_rate':fees['rate'],
                     'size_unit':'payout_dollars',**{k:v for k,v in top.items() if k!='valid'}}
                for key in ('fee_model','balance_precision'):
                    if key in fees:row[key]=fees[key]
                Observation.from_record(row);output.append(('observation',row))
            elif self.venue=='kalshi':output.append(('combo_book' if ticker.startswith('KXMVE') else 'unmapped_book',{'market_ticker':ticker,**top}))
        return output

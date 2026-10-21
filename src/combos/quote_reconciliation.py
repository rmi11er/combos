"""Validate private quote snapshots before any confirmation or risk release.

This is evidence matching, not an authenticated collector or a confirmation gate.
Unknown/mismatched snapshots never change the journal's dispatch or hold state.
"""
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
import math
from .execution_journal import encoded


def decimal(value):
    try: result=Decimal(str(value))
    except InvalidOperation:raise ValueError('invalid exchange decimal') from None
    if not result.is_finite():raise ValueError('nonfinite exchange decimal')
    return result


def timestamp(value):
    dt=datetime.fromisoformat(value.replace('Z','+00:00'))
    if dt.tzinfo is None:raise ValueError('quote timestamp lacks timezone')
    return dt.timestamp()


@dataclass(frozen=True)
class ExpectedQuote:
    rfq_id: str
    market_ticker: str
    creator_user_id: str
    creator_subaccount: int
    yes_bid: str
    no_bid: str
    maximum_contracts: str
    prepared_at: float
    rest_remainder: bool = False
    post_only: bool = True
    quote_id: str | None = None
    fixed_contracts: str | None = None

    def __post_init__(self):
        if any(not isinstance(v,str) or not v for v in (self.rfq_id,self.market_ticker,self.creator_user_id)):
            raise ValueError('quote identity required')
        if type(self.creator_subaccount) is not int or not 0<=self.creator_subaccount<=63:
            raise ValueError('invalid expected subaccount')
        if not math.isfinite(self.prepared_at):raise ValueError('invalid preparation time')
        yes,no=decimal(self.yes_bid),decimal(self.no_bid)
        if yes!=0 or not 0<no<1:raise ValueError('this strategy requires only a NO bid')
        q=decimal(self.maximum_contracts)
        if q<=0 or q%Decimal('.01'):raise ValueError('invalid reserved contract bound')
        if self.fixed_contracts is not None and decimal(self.fixed_contracts)!=q:
            raise ValueError('fixed RFQ requires its full contract count')
        if type(self.rest_remainder) is not bool or type(self.post_only) is not bool:
            raise ValueError('explicit order behavior required')


def match_quote(expected, quote, received_at, now, maximum_age_seconds=2):
    if not all(math.isfinite(v) for v in (received_at,now,maximum_age_seconds)) or maximum_age_seconds<=0:
        raise ValueError('invalid quote observation time')
    if not 0<=now-received_at<=maximum_age_seconds:raise ValueError('stale_or_future_quote_snapshot')
    for key in ('rfq_id','market_ticker','creator_user_id','creator_subaccount','rest_remainder','post_only'):
        if quote.get(key)!=getattr(expected,key) or type(quote.get(key)) is not type(getattr(expected,key)):
            raise ValueError('quote_mismatch:'+key)
    if not isinstance(quote.get('id'),str) or not quote['id']:
        raise ValueError('quote_id_missing')
    if expected.quote_id is not None and quote['id']!=expected.quote_id:
        raise ValueError('quote_mismatch:id')
    for key,field in (('yes_bid_dollars','yes_bid'),('no_bid_dollars','no_bid')):
        if decimal(quote[key])!=decimal(getattr(expected,field)):
            raise ValueError('quote_mismatch:'+key)
    created,updated=timestamp(quote['created_ts']),timestamp(quote['updated_ts'])
    if not expected.prepared_at<=created<=updated<=received_at:
        raise ValueError('quote_timing_does_not_match_intent')
    quantities={}
    # Until side-size semantics are verified on private traffic, bound BOTH
    # returned side counts. Never guess a missing target-cost count from price.
    for field in ('yes_contracts_fp','no_contracts_fp'):
        q=decimal(quote[field])
        if q<0 or q%Decimal('.01') or q>decimal(expected.maximum_contracts):
            raise ValueError('exchange_quantity_exceeds_or_invalidates_hold')
        quantities[field]=str(q)
    if expected.fixed_contracts is not None:
        if decimal(quote['contracts_fp'])!=decimal(expected.fixed_contracts):
            raise ValueError('fixed_RFQ_quantity_changed')
    if decimal(quantities['no_contracts_fp'])<=0:
        raise ValueError('quoted_NO_side_has_no_contracts')
    if quote.get('accepted_side') not in (None,'','no'):
        raise ValueError('unexpected_accepted_quote_side')
    return {'matched':True,'quote_id':quote['id'],'status':quote.get('status'),
            'accepted_side':quote.get('accepted_side'),'quantities':quantities,
            'received_at':received_at,'created_at':created,'updated_at':updated,
            'confirmation_authorized':False,'capital_release_authorized':False,
            'remaining_checks':['authenticated_snapshot_provenance','accepted_side_size_semantics',
                'fresh_pricing_and_creator_policy','fee_inclusive_liability','deadline','orders_and_fills']}


class QuoteReconciler:
    def __init__(self,journal):self.journal=journal

    def record(self,operation_key,expected,quote,received_at,now,source_reference):
        if not isinstance(source_reference,str) or not source_reference:
            raise ValueError('quote snapshot evidence reference required')
        intent=self.journal.get(operation_key)
        if intent['state'] not in ('inflight','unknown','acknowledged'):
            raise ValueError('quote intent was not dispatched')
        request=intent['request']
        if request['method']!='POST' or request['path']!='/trade-api/v2/communications/quotes':
            raise ValueError('quote reconciliation requires a create intent')
        body=request['body']
        for key in ('rfq_id','yes_bid','no_bid','rest_remainder','post_only'):
            value=getattr(expected,key)
            if key in ('yes_bid','no_bid'):
                if decimal(body[key])!=decimal(value):raise ValueError('expectation_conflicts_with_intent')
            elif body.get(key)!=value:raise ValueError('expectation_conflicts_with_intent')
        if body.get('subaccount',0)!=expected.creator_subaccount:
            raise ValueError('expectation_conflicts_with_intent')
        if expected.prepared_at!=intent['created_at']:
            raise ValueError('expectation_conflicts_with_intent_time')
        sent=self.journal.db.execute("SELECT MIN(at) FROM execution_intent_events WHERE operation_key=? AND state='inflight'",(operation_key,)).fetchone()[0]
        if sent is None:raise ValueError('dispatch evidence missing')
        if intent['response'] and intent['response'].get('id')!=quote.get('id'):
            result={'matched':False,'reason':'quote_id_differs_from_create_ack'}
        else:
            try:
                result=match_quote(expected,quote,received_at,now)
                if result['created_at']<sent:raise ValueError('quote predates dispatch')
            except (KeyError,TypeError,ValueError) as exc:
                result={'matched':False,'reason':str(exc)}
        encoded(quote)
        with self.journal.transaction():
            self.journal.event(operation_key,received_at,'quote_snapshot',
                {'source_reference':source_reference,'quote':quote,'assessment':result})
        return result

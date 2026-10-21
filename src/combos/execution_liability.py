"""Fee-inclusive cash bounds for NO-only, post-only quote commitments."""
from dataclasses import asdict, dataclass
from decimal import Decimal, ROUND_CEILING
import math
from .execution_journal import encoded
from .quote_reconciliation import decimal


@dataclass(frozen=True)
class FeeEvidence:
    maximum_rate: str
    balance_precision: str
    fee_reference: str
    precision_reference: str
    valid_from: float
    valid_until: float

    def check(self, at):
        if not all(math.isfinite(v) for v in (at,self.valid_from,self.valid_until)) or not self.valid_from<=at<self.valid_until:
            raise ValueError('fee or precision evidence outside validity window')
        if not self.fee_reference or not self.precision_reference:
            raise ValueError('fee and account precision evidence required')
        if not 0<=decimal(self.maximum_rate)<1 or decimal(self.balance_precision) not in (Decimal('.0001'),Decimal('.01')):
            raise ValueError('invalid fee ceiling or account precision')


def no_quote_cash_bound(quantity, no_bid, evidence, at):
    evidence.check(at)
    q,p=decimal(quantity),decimal(no_bid)
    if q<=0 or q%Decimal('.01') or not 0<p<1 or p%Decimal('.0001'):
        raise ValueError('invalid fixed-point quote quantity or price')
    rate=decimal(evidence.maximum_rate);precision=decimal(evidence.balance_precision)
    maximum_fills=int(q/Decimal('.01'))
    principal=q*p
    model_fee=q*rate*p*(1-p)
    # Per fill, six-decimal model-fee ceiling plus balance alignment adds
    # at most one precision unit. Ignoring rebates bounds any fragmentation.
    rounding_allowance=maximum_fills*precision
    bound=(principal+model_fee+rounding_allowance).quantize(Decimal('.0001'),rounding=ROUND_CEILING)
    return {'quantity':str(q),'no_bid':str(p),'principal':str(principal),
        'model_fee_ceiling_at_limit':str(model_fee),'fragmentation_allowance':str(rounding_allowance),
        'maximum_fills':maximum_fills,'cash_bound':str(bound),'fee_evidence':asdict(evidence),
        'interpretation':'Cash hold bound, not expected fee or edge charge; no rebate credited.'}


class QuoteLiability:
    def __init__(self, holds):
        self.holds=holds;self.journal=holds.journal;self.db=holds.db
        self.db.execute('CREATE TABLE IF NOT EXISTS execution_liability_evidence(reservation_id TEXT PRIMARY KEY, evidence TEXT NOT NULL)')

    def reserve(self, operation_key, reservation_id, body, maximum_contracts, evidence, at, buckets, risk_multiplier=1):
        if decimal(body['yes_bid'])!=0 or body.get('post_only') is not True:
            raise ValueError('NO-only post-only quote required for maker fee bound')
        assessment=no_quote_cash_bound(maximum_contracts,body['no_bid'],evidence,at)
        data=encoded(assessment)
        with self.journal.transaction():
            old=self.db.execute('SELECT evidence FROM execution_liability_evidence WHERE reservation_id=?',(reservation_id,)).fetchone()
            if old and old[0]!=data:raise ValueError('conflicting liability evidence')
            if not old:self.db.execute('INSERT INTO execution_liability_evidence VALUES(?,?)',(reservation_id,data))
            intent=self.holds.reserve_create(operation_key,reservation_id,body,assessment['cash_bound'],buckets,risk_multiplier)
        return {'intent':intent,'liability':assessment}

    def assess_returned_size(self, operation_key, quote, evidence, at):
        intent=self.journal.get(operation_key)
        hold=self.db.execute('SELECT * FROM execution_holds WHERE reservation_id=?',(intent['reservation_id'],)).fetchone()
        if hold is None or hold['state']!='held':raise ValueError('active execution hold missing')
        body=intent['request']['body']
        if quote['rfq_id']!=body['rfq_id'] or decimal(quote['no_bid_dollars'])!=decimal(body['no_bid']):
            raise ValueError('quote liability identity mismatch')
        if decimal(quote['yes_bid_dollars'])!=0 or quote.get('post_only') is not True:
            raise ValueError('quote violates maker-only NO liability basis')
        if not self.db.execute('SELECT 1 FROM execution_liability_evidence WHERE reservation_id=?',(intent['reservation_id'],)).fetchone():
            raise ValueError('original liability evidence missing')
        quantities=[decimal(quote[k]) for k in ('yes_contracts_fp','no_contracts_fp')]
        if any(q<0 or q%Decimal('.01') for q in quantities):raise ValueError('invalid returned quantity')
        assessment=no_quote_cash_bound(max(quantities),body['no_bid'],evidence,at)
        needed=int(decimal(assessment['cash_bound'])*10000)
        result={'within_reserved_cash':needed<=hold['units'],'reserved_units':hold['units'],
                'required_units':needed,'liability':assessment,
                'confirmation_authorized':False,'capital_release_authorized':False}
        with self.journal.transaction():
            self.journal.event(operation_key,at,'quote_liability_assessed',result)
        return result

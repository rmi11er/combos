"""Persistent account fill evidence, separate from strategy ownership and cash.

Recorded principal/fees are trade economics, not an account balance delta: balance
rounding, rebates, collateral netting and settlement require separate evidence.
"""
from decimal import Decimal, InvalidOperation
import json
import math
from .execution_journal import encoded


def fixed(value, quantum):
    try:
        number = Decimal(str(value))
        if not number.is_finite() or number < 0 or number % Decimal(quantum):
            raise ValueError('invalid fixed-point fill value')
    except InvalidOperation:
        raise ValueError('invalid fixed-point fill value') from None
    return number


def normalize_fill(row):
    result = {}
    for field in ('fill_id', 'order_id', 'trade_id', 'ticker'):
        value = row[field]
        if not isinstance(value, str) or not value:
            raise ValueError('missing fill identity')
        result[field] = value
    if row.get('market_ticker', row['ticker']) != row['ticker']:
        raise ValueError('conflicting market identity')
    for field, maximum in (('subaccount_number', 63), ('exchange_index', None)):
        value = row[field]
        if type(value) is not int or value < 0 or (maximum is not None and value > maximum):
            raise ValueError('invalid account identity')
        result[field] = value
    side, action = row['side'], row['action']
    if side not in ('yes', 'no') or action not in ('buy', 'sell'):
        raise ValueError('unsupported fill direction')
    if row.get('outcome_side', side) != side:
        raise ValueError('conflicting fill side')
    if type(row['is_taker']) is not bool:
        raise ValueError('missing maker/taker evidence')
    quantity = fixed(row['count_fp'], '.01')
    yes, no = (fixed(row[field], '.0001') for field in ('yes_price_dollars', 'no_price_dollars'))
    fee = fixed(row['fee_cost'], '.000001')
    if quantity <= 0 or yes + no != 1:
        raise ValueError('invalid fill quantity or complementary prices')
    principal = quantity * (yes if side == 'yes' else no)
    result.update(side=side, action=action, is_taker=row['is_taker'],
        quantity=str(quantity.normalize()), yes_price=str(yes.normalize()),
        no_price=str(no.normalize()), fee=str(fee.normalize()),
        principal=str(principal.normalize()),
        trade_cash_flow_before_balance_adjustments=str(
            ((-principal if action == 'buy' else principal) - fee).normalize()))
    return result


class FillEvidence:
    def __init__(self, journal):
        self.journal = journal
        self.db = journal.db
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS account_fill_evidence (
                exchange_index INTEGER NOT NULL, fill_id TEXT NOT NULL,
                economics TEXT NOT NULL, PRIMARY KEY(exchange_index,fill_id));
            CREATE TABLE IF NOT EXISTS account_fill_observations (
                seq INTEGER PRIMARY KEY, source_reference TEXT NOT NULL,
                received_at REAL NOT NULL, envelope TEXT NOT NULL);
        ''')

    def ingest(self, envelope, source_reference):
        if not isinstance(source_reference, str) or not source_reference:
            raise ValueError('source reference required')
        if (envelope.get('method') != 'GET' or
            envelope.get('path') != '/trade-api/v2/portfolio/fills' or
            envelope.get('http_status') != 200):
            raise ValueError('successful fill read required')
        began, received = envelope['request_started_at'], envelope['received_at']
        if not all(math.isfinite(t) for t in (began, received)) or began > received:
            raise ValueError('invalid observation timing')
        rows = envelope['payload']['fills']
        if not isinstance(rows, list):
            raise ValueError('fill list required')
        normalized = [normalize_fill(row) for row in rows]
        requested_account = envelope.get('params', {}).get('subaccount')
        if requested_account is not None and any(r['subaccount_number'] != requested_account for r in normalized):
            raise ValueError('fill outside requested subaccount')
        inserted = 0
        with self.journal.transaction():
            for row in normalized:
                identity = (row['exchange_index'], row['fill_id'])
                value = encoded(row)
                prior = self.db.execute('SELECT economics FROM account_fill_evidence WHERE exchange_index=? AND fill_id=?', identity).fetchone()
                if prior:
                    if prior[0] != value:
                        raise ValueError('conflicting existing fill economics')
                else:
                    self.db.execute('INSERT INTO account_fill_evidence VALUES(?,?,?)', (*identity, value))
                    inserted += 1
            self.db.execute('INSERT INTO account_fill_observations(source_reference,received_at,envelope) VALUES(?,?,?)',
                (source_reference, received, encoded(envelope)))
        return {'new_fills': inserted, 'observed_fills': len(rows),
                'strategy_ownership_established': False, 'capital_release_authorized': False}

    def order_totals(self, order_id, subaccount, exchange_index):
        rows = [json.loads(r[0]) for r in self.db.execute('SELECT economics FROM account_fill_evidence WHERE exchange_index=?', (exchange_index,))]
        rows = [r for r in rows if r['order_id'] == order_id and r['subaccount_number'] == subaccount]
        return {'fill_count': len(rows), **{field: str(sum((Decimal(r[field]) for r in rows), Decimal(0)))
                for field in ('quantity', 'fee', 'principal', 'trade_cash_flow_before_balance_adjustments')},
                'order_complete': False, 'capital_release_authorized': False}

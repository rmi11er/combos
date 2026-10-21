"""Durable maker ownership and cumulative fill evidence; never releases holds."""
import json
from decimal import Decimal
from .execution_journal import encoded
from .execution_ownership import match_maker_order
from .execution_fills import FillEvidence
from .quote_reconciliation import QuoteReconciler,decimal


class MakerOwnership:
    def __init__(self,journal):
        self.journal=journal;self.db=journal.db;self.fills=FillEvidence(journal)
        self.db.executescript('''CREATE TABLE IF NOT EXISTS maker_order_ownership(
            exchange_index INTEGER,order_id TEXT,operation_key TEXT UNIQUE,binding TEXT NOT NULL,
            PRIMARY KEY(exchange_index,order_id));''')

    def record(self,operation_key,expected,quote,order,received_at,now,exchange_index,source_reference):
        if not source_reference:raise ValueError('private evidence reference required')
        binding=match_maker_order(expected,quote,order,received_at,now,exchange_index)
        with self.journal.transaction():
            assessment=QuoteReconciler(self.journal).record(operation_key,expected,quote,received_at,now,source_reference)
            if not assessment['matched']:raise ValueError('quote not matched to dispatched intent')
            prior=self.db.execute('SELECT operation_key,binding FROM maker_order_ownership WHERE exchange_index=? AND order_id=?',(exchange_index,binding['order_id'])).fetchone()
            if prior:
                if prior['operation_key']!=operation_key or prior['binding']!=encoded(binding):raise ValueError('conflicting maker ownership')
            else:self.db.execute('INSERT INTO maker_order_ownership VALUES(?,?,?,?)',(exchange_index,binding['order_id'],operation_key,encoded(binding)))
            self.journal.event(operation_key,received_at,'maker_order_binding',{'source_reference':source_reference,'binding':binding,'order_snapshot':order})
        return binding

    def reconcile_fills(self,exchange_index,order_id,reported_filled):
        row=self.db.execute('SELECT binding FROM maker_order_ownership WHERE exchange_index=? AND order_id=?',(exchange_index,order_id)).fetchone()
        if row is None:raise ValueError('unknown maker order')
        b=json.loads(row['binding']);reported=decimal(reported_filled)
        if reported<0 or reported%Decimal('.01') or reported>decimal(b['maximum_quantity']):raise ValueError('invalid reported fill count')
        fills=[json.loads(r[0]) for r in self.db.execute('SELECT economics FROM account_fill_evidence WHERE exchange_index=?',(exchange_index,))]
        fills=[r for r in fills if r['order_id']==order_id]
        quantity=Decimal(0);fees=Decimal(0);principal=Decimal(0)
        for f in fills:
            for key in ('ticker','subaccount_number','exchange_index','side','action'):
                if f[key]!=b[key] or type(f[key]) is not type(b[key]):raise ValueError('owned fill identity mismatch')
            if f['is_taker'] or decimal(f['no_price'])>decimal(b['limit_price']):raise ValueError('owned fill execution violates quote')
            quantity+=decimal(f['quantity']);fees+=decimal(f['fee']);principal+=decimal(f['principal'])
        if quantity>decimal(b['maximum_quantity']):raise ValueError('cumulative fills exceed owned order')
        return {'order_id':order_id,'fill_records':len(fills),'quantity':str(quantity),'reported_filled':str(reported),'fees':str(fees),'principal':str(principal),
            'status':'counts_match' if quantity==reported else 'fill_evidence_incomplete' if quantity<reported else 'order_snapshot_behind_fills',
            'capital_release_authorized':False,'remaining_checks':['fresh_terminal_order','settlement_and_balance_reconciliation']}

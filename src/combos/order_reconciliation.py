"""Fresh private order evidence matched to durable ownership; no hold release.

Envelopes must come from the authenticated read collector. Structural validation
does not authenticate arbitrary caller-supplied JSON.
"""
import json
import math

from .kalshi_readonly import order_read_path, private_json
from .quote_reconciliation import decimal, timestamp


def assess_order(binding, envelope, now):
    if (envelope.get('method') != 'GET' or
            envelope.get('path') != order_read_path(binding['order_id']) or
            envelope.get('http_status') != 200 or envelope.get('error')):
        raise ValueError('successful exact private order read required')
    started, received = (envelope[k] for k in ('request_started_at', 'received_at'))
    if any(type(v) not in (int, float) or not math.isfinite(v) for v in (started, received, now)):
        raise ValueError('invalid order observation time')
    if not started <= received <= now or now-started > 2:
        raise ValueError('stale or future order read')
    order = envelope['payload']['order']
    for key in ('order_id', 'user_id', 'ticker', 'subaccount_number', 'exchange_index', 'side', 'action'):
        if order.get(key) != binding[key] or type(order.get(key)) is not type(binding[key]):
            raise ValueError('order identity mismatch: ' + key)
    if order.get('outcome_side', 'no') != 'no':
        raise ValueError('order outcome mismatch')
    yes, no = (decimal(order[k]) for k in ('yes_price_dollars', 'no_price_dollars'))
    if yes+no != 1 or no != decimal(binding['limit_price']):
        raise ValueError('owned order limit changed')
    initial, filled, remaining = (decimal(order[k]) for k in
        ('initial_count_fp', 'fill_count_fp', 'remaining_count_fp'))
    if (initial != decimal(binding['maximum_quantity']) or
            any(q < 0 or q % decimal('.01') for q in (initial, filled, remaining)) or
            filled+remaining > initial):
        raise ValueError('invalid order quantities')
    created, updated = (timestamp(order[k]) for k in ('created_time', 'last_update_time'))
    if not created <= updated <= received:
        raise ValueError('invalid exchange order chronology')
    status = order.get('status')
    if status not in ('resting', 'executed', 'canceled'):
        raise ValueError('unknown order status')
    terminal = status in ('executed', 'canceled')
    if terminal and remaining != 0:
        raise ValueError('terminal order has remaining quantity')
    if status == 'executed' and filled != initial:
        raise ValueError('executed order is not fully filled')
    if status == 'resting' and remaining <= 0:
        raise ValueError('resting order has no remaining quantity')
    return {'status': status, 'terminal': terminal, 'updated_at': updated,
            'filled_quantity': str(filled), 'open_quantity': str(remaining),
            'canceled_quantity': str(initial-filled) if status == 'canceled' else '0',
            'capital_release_authorized': False}


class OrderReconciler:
    def __init__(self, ownership):
        self.ownership = ownership
        self.journal = ownership.journal

    def collect(self, client, exchange_index, order_id, archive_path):
        """Archive one authenticated GET before reconciliation; never retry it."""
        if self.journal.db.execute(
                'SELECT 1 FROM maker_order_ownership WHERE exchange_index=? AND order_id=?',
                (exchange_index, order_id)).fetchone() is None:
            raise ValueError('unknown owned order')
        envelope = client.get(order_read_path(order_id))
        private_json(archive_path, envelope)
        return self.record(exchange_index, order_id, envelope, client.clock(), str(archive_path))

    def record(self, exchange_index, order_id, envelope, now, source_reference):
        if not isinstance(source_reference, str) or not source_reference:
            raise ValueError('private source reference required')
        with self.journal.transaction():
            row = self.journal.db.execute(
                'SELECT operation_key,binding FROM maker_order_ownership WHERE exchange_index=? AND order_id=?',
                (exchange_index, order_id)).fetchone()
            if row is None:
                raise ValueError('unknown owned order')
            assessment = assess_order(json.loads(row['binding']), envelope, now)
            # Ownership itself contains prior fill evidence, even before the
            # first explicit order-reconciliation read. Never forget that floor.
            bindings = self.journal.db.execute(
                "SELECT detail FROM execution_intent_events WHERE operation_key=? AND state='maker_order_binding'",
                (row['operation_key'],)).fetchall()
            if not bindings:
                raise ValueError('owned order lacks original snapshot evidence')
            for recorded in bindings:
                original = json.loads(recorded['detail'])['order_snapshot']
                if (decimal(assessment['filled_quantity']) < decimal(original['fill_count_fp']) or
                        assessment['updated_at'] < timestamp(original['last_update_time'])):
                    raise ValueError('order snapshot regressed below ownership evidence')
                if timestamp(envelope['payload']['order']['created_time']) != timestamp(original['created_time']):
                    raise ValueError('owned order creation time changed')
                if original.get('status') in ('canceled', 'executed'):
                    if (assessment['status'] != original['status'] or
                            decimal(assessment['filled_quantity']) != decimal(original['fill_count_fp'])):
                        raise ValueError('terminal ownership snapshot changed')
            prior = self.journal.db.execute(
                "SELECT detail FROM execution_intent_events WHERE operation_key=? AND state='order_reconciliation' ORDER BY seq DESC LIMIT 1",
                (row['operation_key'],)).fetchone()
            if prior:
                old = json.loads(prior['detail'])['assessment']
                if (assessment['updated_at'] < old['updated_at'] or
                        decimal(assessment['filled_quantity']) < decimal(old['filled_quantity']) or
                        (old['terminal'] and assessment['status'] != old['status'])):
                    raise ValueError('order snapshot regressed')
                if old['terminal'] and assessment['filled_quantity'] != old['filled_quantity']:
                    raise ValueError('terminal fill count changed')
            fills = self.ownership.reconcile_fills(exchange_index, order_id, assessment['filled_quantity'])
            assessment['fills'] = fills
            assessment['terminal_fills_reconciled'] = assessment['terminal'] and fills['status'] == 'counts_match'
            assessment['remaining_checks'] = ['settlement_and_balance_reconciliation']
            if not assessment['terminal_fills_reconciled']:
                assessment['remaining_checks'].insert(0, 'terminal_order_and_complete_fills')
            self.journal.event(row['operation_key'], envelope['received_at'], 'order_reconciliation',
                {'source_reference': source_reference, 'envelope': envelope, 'assessment': assessment})
        return assessment

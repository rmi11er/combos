"""Release local risk for a proven canceled, zero-fill maker order only."""
import json
from .order_reconciliation import OrderReconciler
from .quote_reconciliation import decimal


class UnfilledHoldReleaser:
    def __init__(self, holds, ownership):
        if holds.db is not ownership.db:
            raise ValueError('risk and ownership must share one transaction database')
        self.holds=holds;self.ownership=ownership;self.journal=holds.journal;self.db=holds.db

    def release(self,reservation_id,exchange_index,order_id,now):
        with self.journal.transaction():
            hold=self.db.execute('SELECT * FROM execution_holds WHERE reservation_id=?',(reservation_id,)).fetchone()
            owned=self.db.execute('SELECT * FROM maker_order_ownership WHERE exchange_index=? AND order_id=?',(exchange_index,order_id)).fetchone()
            if hold is None or owned is None:raise ValueError('known hold and maker order required')
            binding=json.loads(owned['binding'])
            if owned['operation_key']!=hold['operation_key'] or binding['rfq_id']!=hold['rfq_id']:
                raise ValueError('order does not belong to reservation')
            if hold['state']=='released_unfilled':
                old=self.db.execute("SELECT detail FROM execution_intent_events WHERE operation_key=? AND state='risk_released_unfilled' ORDER BY seq DESC LIMIT 1",(hold['operation_key'],)).fetchone()
                if old is None:raise ValueError('released hold lacks receipt')
                result=json.loads(old['detail'])
                if result['order_id']!=order_id or result['exchange_index']!=exchange_index:raise ValueError('release receipt identity differs')
                return result
            if hold['state']!='held':raise ValueError('hold is not active')
            quote_path='/trade-api/v2/communications/quotes/'+binding['quote_id']
            for intent in self.db.execute('SELECT * FROM execution_intents WHERE reservation_id=?',(reservation_id,)):
                if intent['state']=='abandoned':continue
                if intent['state']!='acknowledged':raise ValueError('unresolved dispatched or prepared operation')
                request=json.loads(intent['request'])
                if intent['operation_key']==hold['operation_key']:
                    response=json.loads(intent['response'] or '{}')
                    if response.get('id')!=binding['quote_id']:raise ValueError('create acknowledgment does not match owned quote')
                elif (request['method'],request['path']) not in (('PUT',quote_path+'/confirm'),('DELETE',quote_path)):
                    raise ValueError('other reservation operation requires reconciliation')
            prior=self.db.execute("SELECT seq,detail FROM execution_intent_events WHERE operation_key=? AND state='order_reconciliation' ORDER BY seq DESC LIMIT 1",(hold['operation_key'],)).fetchone()
            if prior is None:raise ValueError('fresh terminal order reconciliation required')
            evidence=json.loads(prior['detail'])
            # Revalidate original ownership floors, freshness and current fill
            # evidence inside the same transaction as the release.
            assessment=OrderReconciler(self.ownership).record(exchange_index,order_id,evidence['envelope'],now,evidence['source_reference'])
            if (assessment['status']!='canceled' or not assessment['terminal_fills_reconciled']
                    or decimal(assessment['filled_quantity'])!=0 or assessment['fills']['fill_records']!=0):
                raise ValueError('terminal zero-fill cancellation required')
            result={'reservation_id':reservation_id,'order_id':order_id,'exchange_index':exchange_index,
                'quote_id':binding['quote_id'],'released_units':hold['units'],
                'order_evidence_seq':prior['seq'],'released_at':now,'basis':'fresh_owned_terminal_zero_fill',
                'account_balance_increased':False,'filled_position_release_authorized':False}
            self.db.execute("UPDATE execution_holds SET state='released_unfilled' WHERE reservation_id=?",(reservation_id,))
            self.journal.event(hold['operation_key'],now,'risk_released_unfilled',result)
            return result

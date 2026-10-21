"""Fixed-horizon research labels. No inferred fills or automatic creator sanctions."""
from copy import deepcopy
import heapq
import math


class ResearchMarkouts:
    def __init__(self, pricing, horizons=(10,30,60)):
        if not horizons or any(type(h) not in (int,float) or not math.isfinite(h) or h<=0 for h in horizons):
            raise ValueError('positive finite markout horizons required')
        if len(set(horizons))!=len(horizons):raise ValueError('distinct horizons required')
        self.pricing=pricing;self.horizons=tuple(horizons);self.pending=[];self.seen=set()

    def schedule(self,msg,entry):
        seq=entry['source_seq']
        if seq in self.seen:raise ValueError('duplicate markout entry')
        if entry['rfq_id']!=msg['id']:raise ValueError('entry RFQ mismatch')
        self.seen.add(seq)
        for horizon in self.horizons:
            heapq.heappush(self.pending,(entry['at']+horizon,seq,horizon,deepcopy(msg),deepcopy(entry)))

    def advance(self,before_at,available_source_seq,inclusive=False):
        """Call BEFORE applying an event later than the horizon to pricing state."""
        while self.pending and (self.pending[0][0]<before_at or inclusive and self.pending[0][0]==before_at):
            at,seq,horizon,msg,entry=heapq.heappop(self.pending)
            row={'decision_seq':seq,'rfq_id':msg['id'],'creator_id':msg.get('creator_id'),
                'horizon_seconds':horizon,'entry_at':entry['at'],'valuation_at':at,
                'available_source_seq':available_source_seq,'status':'unavailable',
                'nlegs':entry['nlegs'],'entry_scenario':entry['scenario']}
            future=self.pricing.revalue(msg,at,seq)
            row['future_pricing']=future
            if future['status']=='scenario_priced':
                s=next(s for s in future['scenarios'] if s['assumed_usd_per_native_unit']==1)
                initial=entry['scenario']['independent_combo_point'];later=s['independent_combo_point']
                row.update(status='observed',adverse_move_cents=100*(later-initial))
                # Positive move means a YES seller's liability increased.
                q=entry['research_policy'].get('quote')
                if q:
                    row['quote_minus_future_fair_cents']=100*(float(q['yes_ask'])-later-float(q['single_fill_fee'])/float(q['quantity_bound']))
            else:row['reason']=future.get('reason','future_fair_unavailable')
            yield row

    def finish(self):
        while self.pending:
            at,seq,horizon,msg,entry=heapq.heappop(self.pending)
            yield {'decision_seq':seq,'rfq_id':msg['id'],'creator_id':msg.get('creator_id'),
                'horizon_seconds':horizon,'entry_at':entry['at'],'valuation_at':at,
                'status':'right_censored','reason':'capture_ended_before_horizon'}

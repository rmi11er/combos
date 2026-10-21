"""Causal shadow view of native-age and snapshot-verified observations."""
from copy import deepcopy
import math


class VerifiedBookState:
    def __init__(self, maximum_age=15):
        if not math.isfinite(maximum_age) or maximum_age<=0:raise ValueError('invalid maximum age')
        self.maximum_age=maximum_age;self.books={};self.certificates={};self.seq=0

    def consume(self,event):
        if type(event['seq']) is not int or event['seq']<=self.seq:
            raise ValueError('events must advance in sequence')
        self.seq=event['seq'];row=event['payload'];kind=event['kind']
        if kind=='venue_reset' and event['source']=='polymarket':
            self.books.clear();self.certificates.clear()
        elif kind=='observation' and row.get('venue')=='polymarket':
            key=row['market_key'];self.books[key]=deepcopy(row)
            # Any new observation requires fresh verification in this version.
            self.certificates.pop(key,None)
        elif kind=='book_verification':
            key=row['market_key'];current=self.books.get(key);evidence=row['evidence']
            baseline=row['baseline_observation']
            if not current:raise ValueError('verification has no current book')
            if evidence['basis']!='matching_rest_ws_full_depth_v1':raise ValueError('unknown verification basis')
            if current.get('connection_generation')!=evidence['generation'] or current.get('book_revision')!=evidence['revision']:
                raise ValueError('verification generation/revision mismatch')
            fields=('source_reference','observed_at','available_at','yes_bid','yes_ask','yes_bid_size','yes_ask_size','active','market_key','venue')
            if any(current.get(f)!=baseline.get(f) for f in fields):raise ValueError('verification baseline differs')
            if not evidence['verified_at']<=evidence['available_at']<=event['received_at']:
                raise ValueError('verification publication is noncausal')
            self.certificates[key]={'evidence':deepcopy(evidence),'published_at':event['received_at'],'event_seq':event['seq']}

    def pair(self,key,now):
        if not math.isfinite(now):raise ValueError('invalid decision time')
        native=self.books.get(key)
        if not native:return {'baseline':None,'candidate':None}
        if not native.get('active') or native['available_at']>now or min(native.get('yes_bid_size',0),native.get('yes_ask_size',0))<=0:
            return {'baseline':None,'candidate':None}
        baseline=deepcopy(native) if 0<=now-native['observed_at']<=self.maximum_age else None
        candidate=deepcopy(baseline);certificate=self.certificates.get(key)
        if certificate:
            evidence=certificate['evidence']
            if certificate['published_at']<=now and 0<=now-evidence['verified_at']<=self.maximum_age and evidence['verified_at']>native['observed_at']:
                candidate=deepcopy(native)
                candidate.update(native_observed_at=native['observed_at'],observed_at=evidence['verified_at'],
                    available_at=max(native['available_at'],certificate['published_at']),
                    freshness_basis=evidence['basis'],verification_event_seq=certificate['event_seq'],
                    verification_reference=evidence['source_reference'],shadow_freshness_candidate=True)
        return {'baseline':baseline,'candidate':candidate}

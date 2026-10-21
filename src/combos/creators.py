"""Causal creator evidence; structural risk is separate from intent attribution."""
from collections import defaultdict,deque
from dataclasses import dataclass,asdict
import hashlib

@dataclass(frozen=True)
class CreatorPolicy:
    long_combo_legs:int=20
    spam_window_seconds:int=60
    spam_requests:int=30
    duplicate_fraction:float=.8
    minimum_adverse_labels:int=30
    adverse_rate:float=.8

class CreatorWatchlist:
    def __init__(self,policy=CreatorPolicy()):
        self.policy=policy;self.history=defaultdict(deque);self.counts=defaultdict(lambda:defaultdict(int));self.seen=set();self.last_time=float('-inf');self.last_spam=defaultdict(lambda:float('-inf'))

    def observe(self,rfq_id,creator,at,leg_keys,proven_pickoff=False,correlation_sensitive=False):
        if at<self.last_time: raise ValueError('creator observations must be chronological')
        self.last_time=at
        if rfq_id in self.seen: return
        self.seen.add(rfq_id)
        if not creator: return
        hist=self.history[creator];count=self.counts[creator];key=tuple(sorted(leg_keys))
        while hist and hist[0][0]<=at-self.policy.spam_window_seconds: hist.popleft()
        # Flags enter state only after observing this request; caller must read
        # decision-time state before calling observe for the current RFQ.
        hist.append((at,key));count['requests']+=1
        if len(leg_keys)>=self.policy.long_combo_legs: count['long_leg_requests']+=1
        if proven_pickoff: count['proven_pickoff_requests']+=1
        if correlation_sensitive:count['correlation_sensitive_requests']+=1
        duplicates=sum(k==key for _,k in hist)/len(hist)
        if len(hist)>=self.policy.spam_requests and duplicates>=self.policy.duplicate_fraction and at-self.last_spam[creator]>=self.policy.spam_window_seconds:
            count['spam_bursts']+=1;self.last_spam[creator]=at

    def label(self,creator,available_at,adverse):
        if available_at<self.last_time: raise ValueError('label arrived out of chronological order')
        self.last_time=available_at
        self.counts[creator]['markout_labels']+=1
        self.counts[creator]['adverse_labels']+=int(adverse)

    def state(self,creator):
        c=dict(self.counts[creator]); n=c.get('markout_labels',0)
        reasons=[]
        if c.get('long_leg_requests',0): reasons.append('long_leg_context')
        if c.get('spam_bursts',0): reasons.append('repetitive_request_burst')
        if c.get('proven_pickoff_requests',0): reasons.append('verified_structural_pickoff')
        if c.get('correlation_sensitive_requests',0):reasons.append('same_fixture_pricing_review')
        if n>=self.policy.minimum_adverse_labels and c.get('adverse_labels',0)/n>=self.policy.adverse_rate: reasons.append('repeated_adverse_markouts')
        # Offline research exclusion only. Three disjoint observed repetitive
        # bursts are sufficient operational evidence; long legs alone are not.
        blocked=c.get('spam_bursts',0)>=3
        return {'creator_hash':hashlib.sha256(creator.encode()).hexdigest()[:16],'evidence':c,'reasons':reasons,'blacklisted':blocked,'status':'research_blacklist' if blocked else 'review' if reasons else 'unflagged'}

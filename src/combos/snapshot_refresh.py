"""Bounded quiet-book snapshot request scheduling, independent of pricing."""
import math
from .refresh_demand import choose as demand_choose


class SnapshotRefresh:
    def __init__(self,config,mode):
        if mode!='shadow':raise ValueError('snapshot refresh is shadow only')
        self.interval=config.get('interval_seconds',5)
        self.quiet=config.get('quiet_seconds',15)
        self.batch=config.get('maximum_books_per_request',100)
        self.maximum=config.get('maximum_requests',3)
        if not all(type(v) in (int,float) and math.isfinite(v) for v in (self.interval,self.quiet)) or self.interval<5 or self.quiet<15:
            raise ValueError('invalid snapshot timing')
        if type(self.batch) is not int or not 1<=self.batch<=100 or type(self.maximum) is not int or not 1<=self.maximum<=100:
            raise ValueError('invalid snapshot request budget')
        self.demand_priority=config.get('demand_priority',False)
        self.demand_refresh_seconds=config.get('demand_refresh_seconds',8)
        if type(self.demand_priority) is not bool or type(self.demand_refresh_seconds) not in (int,float) or not math.isfinite(self.demand_refresh_seconds) or not 5<=self.demand_refresh_seconds<15:
            raise ValueError('invalid demand refresh timing')
        self.sent=0;self.last_sent=None;self.attempted={};self.reset()

    def reset(self):
        self.updated={}

    def observed(self,ticker,now):
        self.updated[ticker]=now

    def choose(self,targets,now,demand=None):
        if self.sent>=self.maximum or self.last_sent is not None and now-self.last_sent<self.interval:
            return []
        demand=set(demand or ()) if self.demand_priority else set()
        candidates=[t for t in targets if t in self.updated and now-self.updated[t]>=(self.demand_refresh_seconds if t in demand else self.quiet)]
        candidates.sort(key=lambda t:(self.attempted.get(t,float('-inf')),self.updated[t],t))
        chosen=demand_choose(candidates,self.attempted,demand,now,self.batch,refresh_after=self.demand_refresh_seconds) if self.demand_priority else candidates[:self.batch]
        if chosen:
            self.sent+=1;self.last_sent=now
            for t in chosen:self.attempted[t]=now
        return chosen

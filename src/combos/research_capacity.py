"""Research-only reservation replay; expiry is an explicit no-fill assumption."""
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR


def units(value, rounding):
    d=Decimal(str(value))
    if not d.is_finite() or d<=0:raise ValueError('positive finite dollars required')
    return int((d*10000).to_integral_value(rounding=rounding))


class CapacityReplay:
    def __init__(self, capital, caps, lifetime=None):
        if set(caps)!={'contract','combo','fixture'}:raise ValueError('complete caps required')
        if lifetime is not None and (not Decimal(str(lifetime)).is_finite() or lifetime<=0):raise ValueError('invalid lifetime')
        self.capital=units(capital,ROUND_FLOOR)
        self.caps={k:units(v,ROUND_FLOOR) for k,v in caps.items()}
        self.lifetime=lifetime;self.active={};self.seen=set();self.last_at=float('-inf');self.peak=0

    def admit(self, identifier, at, dollars, buckets, risk_multiplier=1):
        if not Decimal(str(at)).is_finite() or at<self.last_at:raise ValueError('noncausal clock')
        if set(buckets)!=set(self.caps) or any(not v or any(not isinstance(k,str) or not k for k in v) for v in buckets.values()):raise ValueError('complete buckets required')
        multiplier=Decimal(str(risk_multiplier))
        if not multiplier.is_finite() or not 0<multiplier<=1:raise ValueError('invalid risk multiplier')
        cost=units(dollars,ROUND_CEILING);self.last_at=at
        self.active={k:v for k,v in self.active.items() if v['expires'] is None or at<v['expires']}
        reasons=[]
        if identifier in self.seen:reasons.append('duplicate_rfq')
        self.seen.add(identifier)
        used=sum(v['cost'] for v in self.active.values())
        if used+cost>self.capital:reasons.append('capital')
        for kind,keys in buckets.items():
            cap=int((Decimal(self.caps[kind])*multiplier).to_integral_value(rounding=ROUND_FLOOR))
            if any(cost+sum(v['cost'] for v in self.active.values() if key in v['buckets'][kind])>cap for key in set(keys)):
                reasons.append(kind)
        if not reasons:
            self.active[identifier]={'cost':cost,'buckets':{k:set(v) for k,v in buckets.items()},'expires':None if self.lifetime is None else at+self.lifetime}
            used+=cost
        self.peak=max(self.peak,used)
        return {'admitted':not reasons,'binding_limits':reasons,'committed_units':used,'active_reservations':len(self.active)}

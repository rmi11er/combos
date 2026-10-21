"""Joint pending-plus-filled gross-risk scenario on validated tape candidates."""
import json,heapq
from pathlib import Path
from collections import Counter,defaultdict
from corrected_shadow_review import fillstats
ROOT=Path(__file__).resolve().parents[1];D=ROOT/'runs/shadow_exchange_fallback_20260909'
qs={q['quote_key']:q for q in map(json.loads,(D/'quotes.jsonl').open())}
fills=json.loads((D/'validated_potential_fills.json').read_text())
events=[(q['decision_completed_at'],0,k) for k,q in qs.items()]+[(f['at'],1,i) for i,f in enumerate(fills)]
events.sort();used=defaultdict(float);pending={};expiries=[];accepted=[];counts=Counter();peaks=defaultdict(float)
def limits(q):
    mult=q['pricing']['risk_multiplier'];ls={'total':10000.,'combo:'+q['market_ticker']:500*mult}
    ls.update({'contract:'+k:500*mult for k in set(q['pricing']['contracts'])})
    ls.update({'fixture:'+k:1000*mult for k in set(q['pricing']['fixtures'])})
    return ls
for at,kind,key in events:
    while expiries and expiries[0][0]<=at:
        _,k=heapq.heappop(expiries);remaining,buckets=pending.pop(k)
        for b in buckets:used[b]-=remaining
    if kind==0:
        q=qs[key];ls=limits(q);cost=q['quantity']*(1-q['yes_ask'])+q['economics']['maker_fee']
        if any(used[b]+cost>cap+1e-8 for b,cap in ls.items()):counts['quote_intents_rejected_by_joint_risk']+=1;continue
        counts['quote_intents_admitted']+=1
        for b in ls:used[b]+=cost;peaks[b]=max(peaks[b],used[b])
        pending[key]=[cost,list(ls)];heapq.heappush(expiries,(q['valid_until'],key))
    else:
        f=fills[key];q=qs[f['quote_key']]
        if f['quote_key'] not in pending:counts['candidate_allocations_without_admitted_quote']+=1;continue
        # Reservation already covers this fill; keep its collateral committed
        # after expiry by releasing only the unfilled reservation remainder.
        pending[f['quote_key']][0]-=f['liability_dollars']
        assert pending[f['quote_key']][0]>=-1e-8
        accepted.append(f)
while expiries:
    _,key=heapq.heappop(expiries);remaining,buckets=pending.pop(key)
    for b in buckets:used[b]-=remaining
summary=dict(**fillstats(accepted),counts=dict(counts),ending_used=dict(used),peak_used=dict(peaks),
    limitations='Conservative gross limits, no netting/settlement recycling. Fixed initial quote-intent cohort and validated allocation pairs; no reassignment of lost public volume or revival of initially risk-blocked opportunities. No intermediate last-look cancellation simulation.')
(D/'joint_risk_fills.json').write_text(json.dumps(accepted,indent=2)+'\n')
(D/'joint_risk_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps({k:v for k,v in summary.items() if k not in ('ending_used','peak_used')},indent=2))

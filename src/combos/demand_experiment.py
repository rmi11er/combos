"""Offline RFQ demand experiment assignment and observed-response scoring.

No order transport. Candidate generation and customer exposure are separate.
"""
import hashlib
import math
from collections import Counter, defaultdict

ARMS = {'flat_0.2c': .002, 'flat_0.3c': .003, 'flat_0.5c': .005}
VERSION = 'nfl-demand-flat-arms-v1'


def assign(rfq_id, seed):
    if not rfq_id or not seed:
        raise ValueError('rfq_identity_and_seed_required')
    # Repeated processing of an RFQ always yields the same arm. Arm probability
    # is equal within every pre-treatment price/leg/size stratum in expectation.
    digest = hashlib.sha256(f'{VERSION}|{seed}|{rfq_id}'.encode()).digest()
    index = int.from_bytes(digest[:8], 'big') % len(ARMS)
    return {'experiment': VERSION, 'assignment_id':digest.hex(),
            'rfq_id':rfq_id, 'arm':list(ARMS)[index], 'propensity':1/len(ARMS)}


def price_band(p):
    if not math.isfinite(p) or not 0 <= p <= 1:
        raise ValueError('invalid_fair_price')
    return '<10c' if p < .1 else '10-25c' if p < .25 else '25-40c' if p < .4 else '40c+'


def score(assignments, responses):
    """Score externally verified exposure records; absent records stay missing.

    Non-acceptance requires observation through the entire response window.
    Positive acceptance may be known before that window ends. Acknowledgment
    alone is insufficient evidence that a customer could see the quote.
    """
    indexed = {a['assignment_id']:a for a in assignments}
    if len(indexed) != len(assignments):
        raise ValueError('duplicate_assignment')
    seen, quotes, labels = set(), set(), []
    for r in responses:
        key = r['assignment_id']
        if key in seen or key not in indexed:
            raise ValueError('duplicate_or_unknown_response_assignment')
        seen.add(key); a = indexed[key]
        if a.get('experiment_stage') != 'prospective_frozen':
            raise ValueError('prospective_assignment_required')
        if r.get('source_type') != 'observed_live' or r.get('customer_exposure_confirmed') is not True:
            raise ValueError('real_customer_exposure_required')
        if not r.get('quote_id') or not r.get('evidence_reference'):
            raise ValueError('quote_identity_and_provenance_required')
        if r['quote_id'] in quotes:
            raise ValueError('quote_used_for_multiple_assignments')
        quotes.add(r['quote_id'])
        if r['arm'] != a['arm']:
            raise ValueError('assigned_arm_mismatch')
        chosen = a['candidates'][a['arm']]
        for field in ('yes_ask', 'quantity'):
            if not math.isclose(float(r[field]),float(chosen[field]),abs_tol=1e-10,rel_tol=0):
                raise ValueError('exposed_candidate_mismatch')
        sent, ack, end, through = (float(r[k]) for k in ('sent_at','ack_at','response_end_at','observed_through_at'))
        if not all(math.isfinite(x) for x in (sent,ack,end,through)) or not a['decision_at'] <= sent <= ack < end or through < ack:
            raise ValueError('invalid_exposure_timing')
        frozen = float(a['assignment_frozen_at'])
        if not math.isfinite(frozen) or not a['decision_at'] <= frozen <= sent:
            raise ValueError('assignment_must_precede_exposure')
        if end != float(a['response_end_at']):
            raise ValueError('response_window_changed')
        accepted = r.get('accepted_at')
        if accepted is not None:
            if not math.isfinite(float(accepted)) or not ack <= float(accepted) <= min(end,through):
                raise ValueError('invalid_acceptance_time')
            if not r.get('acceptance_evidence_reference'):
                raise ValueError('acceptance_provenance_required')
            status = 'accepted'
        else:
            status = 'not_accepted' if through >= end and r.get('continuous_observation') is True and r.get('full_window_exposure') is True else 'censored'
        labels.append({'assignment_id':key,'arm':a['arm'],'price_band':a['price_band'],
                       'status':status,'quote_id':r['quote_id'],
                       'accepted_at':float(accepted) if accepted is not None else None})
    groups = defaultdict(list)
    for a in assignments:
        groups[a['arm'],a['price_band']].append(a)
    summaries = []
    by_label = {x['assignment_id']:x for x in labels}
    for (arm,band), rows in sorted(groups.items()):
        counts = Counter(by_label.get(a['assignment_id'],{'status':'not_exposed'})['status'] for a in rows)
        n = counts['accepted']+counts['not_accepted']
        exposed = n+counts['censored']
        summaries.append({'arm':arm,'price_band':band,'assigned':len(rows),**counts,
            'resolved_responses':n,'exposed':exposed,
            'acceptance_rate_resolved':counts['accepted']/n if n else None,
            'acceptance_lower_bound_exposed':counts['accepted']/exposed if exposed else None,
            'acceptance_upper_bound_exposed':(counts['accepted']+counts['censored'])/exposed if exposed else None})
    return {'assignments':len(assignments),'observed_exposures':len(labels),'groups':summaries,
            'labels':labels,'inference':'Descriptive rates and censor bounds. No causal claim from retrospective assignments; no fill or profit estimate.'}


def score_markouts(assignments, response_result, fills, horizons=(10,30,60,300)):
    """Seller markouts from real fills and causal, as-of fair observations.

    Each mark requires its horizon, observation timestamp, available timestamp,
    and provenance. Missing/stale marks remain missing, never zero. Actual fees
    are allocated to individual fills upstream; quantities may be fractional.
    """
    indexed = {a['assignment_id']: a for a in assignments}
    accepted = {r['assignment_id']: r for r in response_result['labels'] if r['status']=='accepted'}
    seen = set(); buckets = defaultdict(list); total_quantity = Counter()
    filled_quantity = Counter()
    for f in fills:
        key = f['assignment_id']
        if key not in accepted or f.get('source_type') != 'observed_live' or not f.get('evidence_reference'):
            raise ValueError('observed_accepted_fill_required')
        if not f.get('fill_id') or f['fill_id'] in seen or f['quote_id'] != accepted[key]['quote_id']:
            raise ValueError('invalid_fill_identity')
        seen.add(f['fill_id']); a=indexed[key]; chosen=a['candidates'][a['arm']]
        q,p,fee,t = (float(f[k]) for k in ('quantity','yes_price','maker_fee_dollars','filled_at'))
        if not all(math.isfinite(x) for x in (q,p,fee,t)) or q<=0 or not 0<=p<=1 or fee<0 or t<accepted[key]['accepted_at'] or p<float(chosen['yes_ask']):
            raise ValueError('invalid_fill_economics')
        filled_quantity[key]+=q
        if filled_quantity[key]>float(chosen['quantity'])+1e-9:
            raise ValueError('overfilled_quote')
        group=(a['arm'],a['price_band']); total_quantity[group]+=q
        marks={m['horizon_seconds']:m for m in f.get('marks',[])}
        if len(marks)!=len(f.get('marks',[])):
            raise ValueError('duplicate_mark_horizon')
        for h in horizons:
            m=marks.get(h)
            if m is None:continue
            fair,observed,available=(float(m[k]) for k in ('fair','observed_at','available_at'))
            if not all(math.isfinite(x) for x in (fair,observed,available)) or not 0<=fair<=1 or not t<=observed<=available<=t+h or not m.get('evidence_reference'):
                raise ValueError('invalid_or_lookahead_mark')
            if t+h-observed>2:continue  # Frozen maximum as-of staleness, seconds.
            buckets[group,h].append((q,q*(p-fair)-fee))
    rows=[]
    for group,total in sorted(total_quantity.items()):
        for h in horizons:
            values=buckets[group,h];quantity=sum(v[0] for v in values)
            pnl=sum(v[1] for v in values)
            rows.append({'arm':group[0],'price_band':group[1],'horizon_seconds':h,
                         'filled_quantity':total,'marked_quantity':quantity,'marked_fills':len(values),
                         'quantity_coverage':quantity/total,
                         'net_markout_dollars':pnl if quantity else None,
                         'net_markout_cents_per_contract':100*pnl/quantity if quantity else None})
    return {'observed_fills':len(seen),'groups':rows,
            'interpretation':'Conditional on execution and mark availability, not incremental strategy PnL. Positive favors seller.'}

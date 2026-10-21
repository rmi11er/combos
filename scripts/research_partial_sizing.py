"""Research-only whole-contract sizing with causal integer cash reservations.

Reprices the documented historical fee scenario at the smaller quantity. Public
print quantities are ceilings, not evidence of executable partial RFQ fills.
"""
from collections import defaultdict
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
import heapq
import math


def units(value):
    return int((Decimal(str(value))*10000).to_integral_value(rounding=ROUND_CEILING))


def fee(quantity, price, rate):
    q, p, r = map(lambda x: Decimal(str(x)), (quantity, price, rate))
    raw = (q*p*(1-p)*r).quantize(Decimal('.000001'), rounding=ROUND_CEILING)
    cash = -q*(1-p)
    aligned = ((cash-raw)/Decimal('.0001')).to_integral_value(rounding=ROUND_FLOOR)*Decimal('.0001')
    return float(cash-aligned)


def size_rows(rows, config, event_fraction=1.):
    ceiling_value = getattr(config, 'maximum_committed_dollars', None)
    ceiling = None
    if ceiling_value is not None:
        value = Decimal(str(ceiling_value))
        if not value.is_finite() or value <= 0:
            raise ValueError('invalid deployment ceiling')
        ceiling = int((value*10000).to_integral_value(rounding=ROUND_FLOOR))
        if ceiling <= 0:
            raise ValueError('deployment ceiling below ledger precision')
    fraction = Decimal(str(event_fraction))
    if not fraction.is_finite() or not 0 < fraction <= 1:
        raise ValueError('event fraction must be in (0,1]')
    if config.entry_filter != 'minimum_edge' or config.maximum_yes_premium_dollars is not None:
        raise ValueError('unsupported entry policy')
    output, accepted = [], set()
    for model in sorted({r['model'] for r in rows}):
        cash = units(config.capital_dollars)
        committed = 0
        used = defaultdict(int)
        pending = []
        for row in sorted((r for r in rows if r['model']==model), key=lambda r:(r['at'],r['evaluation_id'])):
            while pending and pending[0][0] <= row['at']:
                _, _, payout, cost, buckets = heapq.heappop(pending)
                cash += payout
                committed -= cost
                for bucket in buckets: used[bucket] -= cost
            buckets = [(kind,key) for kind,keys in row['buckets'].items() for key in sorted(set(keys))]
            assert set(row['buckets']) == {'contract','fixture','combo'}
            budget = min([cash]+[
                int(Decimal(str(getattr(config,'per_'+kind+'_dollars')))*Decimal(str(row['risk_multiplier']))*10000)-used[(kind,key)]
                for kind,key in buckets])
            ticket_budget = int(Decimal(str(config.per_fixture_dollars))*Decimal(str(row['risk_multiplier']))*fraction*10000)
            budget = min(budget, ticket_budget)
            if ceiling is not None:
                budget = min(budget, ceiling-committed)
            rate = row['source']['fee_basis']['rate']
            if not math.isclose(fee(row['quantity'],row['yes_price'],rate),row['maker_fee'],abs_tol=1e-8):
                raise ValueError('fee scenario does not reproduce original print')
            def economics(q):
                f = fee(q,row['yes_price'],rate)
                # Match the production ledger's conservative conversion of float cash cost.
                return f, units(q*(1-row['yes_price'])+f)
            low, high = 0, int(Decimal(str(row['quantity'])).to_integral_value(rounding=ROUND_FLOOR))
            while low < high:
                mid = (low+high+1)//2
                if economics(mid)[1] <= budget: low = mid
                else: high = mid-1
            candidate = dict(row)
            candidate['source'] = {**row['source'],'sizing_research':{
                'observed_quantity':row['quantity'],'available_risk_units':budget,
                'event_fraction':float(fraction),'per_ticket_budget_units':ticket_budget,
                'maximum_whole_quantity':low,'policy':'whole_contract_maximum_that_fits'}}
            if ceiling is not None:
                candidate['source']['sizing_research'].update(
                    deployment_ceiling_units=ceiling, committed_before_units=committed,
                    deployment_headroom_units=ceiling-committed)
            if low:
                f, cost = economics(low)
                basis = row['fair_point'] if config.entry_basis=='point' else row['stressed_upper']
                multiplier = row['source']['nlegs'] if config.minimum_net_edge_unit=='leg_contract' else 1
                if row['quote_allowed'] and low*(row['yes_price']-basis)-f >= low*config.minimum_net_edge_per_share*multiplier:
                    candidate.update(quantity=float(low),maker_fee=f)
                    cash -= cost
                    committed += cost
                    for bucket in buckets: used[bucket] += cost
                    accepted.add((model,row['evaluation_id']))
                    if row['settled_at'] is not None:
                        payout = units(low*(1-row['yes_settlement']))
                        heapq.heappush(pending,(row['settled_at']+config.settlement_delay_seconds,row['evaluation_id'],payout,cost,buckets))
            # Non-admitted rows are explicitly disabled in the independently replayed ledger.
            candidate['quote_allowed'] = (model,row['evaluation_id']) in accepted
            output.append(candidate)
    return output, accepted

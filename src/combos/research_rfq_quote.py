"""Explicit research quote scenarios; no exchange sizing or execution authority."""
from decimal import Decimal, ROUND_CEILING
from .fees import kalshi_fill_fee

D = Decimal


def solve_quote(point, upper, reserve_fraction, edge, *, contracts=None,
                target_cost=None, rate='.035', precision='.0001', tick='.0001', ranges=None):
    """Lowest scenario-grid ask covering a single-fill fee and required edge.

    Target cost / ask, rounded UP to .01 contracts, is a quantity bound, not the
    exchange's fee-inclusive target sizing. Fixed RFQs retain their full size.
    Fragmentation cash bound assumes at most quantity/.01 separate fills.
    """
    point, upper, alpha, edge, rate, tick = map(D, map(str,
        (point, upper, reserve_fraction, edge, rate, tick)))
    if not all(x.is_finite() for x in (point, upper, alpha, edge, rate, tick)):
        raise ValueError('nonfinite input')
    if not (0 <= point <= upper <= 1 and 0 <= alpha <= 1 and edge >= 0
            and 0 <= rate < 1 and tick >= D('.0001') and tick % D('.0001') == 0):
        raise ValueError('invalid quote inputs')
    if (contracts is None) == (target_cost is None):
        raise ValueError('exactly one sizing input required')
    size = D(str(contracts if contracts is not None else target_cost))
    if not size.is_finite() or size <= 0:
        raise ValueError('invalid size')
    if contracts is not None and size % D('.01'):
        raise ValueError('invalid contract precision')
    reference = point + alpha * (upper-point)
    price = max(tick, ((reference+edge)/tick).to_integral_value(rounding=ROUND_CEILING)*tick)
    allowed = None
    if ranges is not None:
        allowed = set()
        for grid in ranges:
            start,end,step=(D(str(grid[k])) for k in ('start','end','step'))
            if not all(x.is_finite() for x in (start,end,step)) or not 0<=start<end<=1 or step<=0 or start%D('.0001') or step%D('.0001'):
                raise ValueError('invalid price grid')
            v=start
            while v<end:
                if 0<v<1:allowed.add(v)
                v+=step
        candidates=iter(sorted(v for v in allowed if v>=price))
    else:
        candidates=None
    while price < 1:
        if candidates is not None:
            price=next(candidates,D(1))
            if price>=1:break
        q = size if contracts is not None else (size/price).quantize(D('.01'), rounding=ROUND_CEILING)
        fee = kalshi_fill_fee(q, 1-price, rate, 'buy', precision)['net_fee']
        compensation = q*(price-reference)-fee
        if compensation >= q*edge:
            hold = (q*(1-price) + q*rate*price*(1-price) + q/D('.01')*D(precision))
            hold = hold.quantize(D(precision), rounding=ROUND_CEILING)
            return {'yes_ask':price, 'no_bid':1-price, 'quantity_bound':q,
                    'sizing_basis':'fixed_contracts' if contracts is not None else 'target_cost_upper_bound',
                    'quote_reference':reference, 'single_fill_fee':fee,
                    'reference_compensation':compensation,
                    'point_compensation':q*(price-point)-fee,
                    'single_fill_cash':q*(1-price)+fee,
                    'fragmentation_cash_bound':hold}
        price += tick
    raise ValueError('no_price_with_required_edge')

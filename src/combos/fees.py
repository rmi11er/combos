"""Current cash fee mechanics, separate from archived study approximations.

Sources: docs.kalshi.com/getting_started/fee_rounding and
docs.polymarket.com/trading/fees (verified September 7, 2026).
"""
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP


def value(x):
    d=Decimal(str(x))
    if not d.is_finite():raise ValueError('nonfinite fee input')
    return d


def quadratic_fee(quantity,price,rate):
    q,p,r=map(value,(quantity,price,rate))
    if q<=0 or not 0<=p<=1 or not 0<=r<1:raise ValueError('invalid fee input')
    return q*r*p*(1-p)


def kalshi_fill_fee(quantity,price,rate,action='buy',balance_precision='.0001',accumulator=0):
    """Per-order stateful rounding for one fill; returned amounts are Decimal.

    The account precision must be verified: direct .0001, non-direct .01.
    Fees are ceiled at six decimals before signed-revenue balance alignment.
    """
    if action not in ('buy','sell'):raise ValueError('unknown fee action')
    q,p,unit,carry=map(value,(quantity,price,balance_precision,accumulator))
    if unit not in (Decimal('.0001'),Decimal('.01')) or carry<0:raise ValueError('invalid fee precision/accumulator')
    fee=quadratic_fee(q,p,rate).quantize(Decimal('.000001'),rounding=ROUND_CEILING)
    revenue=q*p*(1 if action=='sell' else -1)
    if revenue!=revenue.quantize(Decimal('.000001')):raise ValueError('fill revenue exceeds six decimal precision')
    aligned=((revenue-fee)/unit).to_integral_value(rounding=ROUND_FLOOR)*unit
    rounding=revenue-fee-aligned
    available=carry+rounding
    rebate=min((available/unit).to_integral_value(rounding=ROUND_FLOOR),
               ((fee+rounding)/unit).to_integral_value(rounding=ROUND_FLOOR))*unit
    return {'model_fee':quadratic_fee(q,p,rate),'trade_fee':fee,'rounding_fee':rounding,'rebate':rebate,
            'net_fee':fee+rounding-rebate,'accumulator':available-rebate,
            'balance_change':aligned+rebate,'balance_precision':unit}


def polymarket_fill_fee(quantity,price,rate):
    """USDC/USD cash fee, five decimal places. No assumed future rebates.

    Public docs specify five decimals but not midpoint tie-breaking. HALF_UP is
    an explicit convention to validate against actual fills, not a claimed
    exchange guarantee. Fee bounds below also cover either nearest-rounding tie.
    """
    raw=quadratic_fee(quantity,price,rate)
    rounded=raw.quantize(Decimal('.00001'),rounding=ROUND_HALF_UP)
    return {'model_fee':raw,'net_fee':rounded,'rounding_tie_convention':'half_up_pending_fill_validation'}


def taker_fee_context(venue,bid,ask,bid_quantity,ask_quantity,rate,balance_precision='.0001'):
    """Conservative finite-size cash fees for selling bid / buying ask.

    No prior-order rounding rebate is assumed. The smooth p(1-p) allowance is
    retained as a floor, so tiny fee-free rounds cannot narrow fair uncertainty.
    """
    result={'model':'venue_cash_v2','venue':venue,'rate':float(rate),'sides':{}}
    for side,p,q,action in (('bid',bid,bid_quantity,'sell'),('ask',ask,ask_quantity,'buy')):
        if venue=='kalshi':fee=kalshi_fill_fee(q,p,rate,action,balance_precision)
        elif venue=='polymarket':fee=polymarket_fill_fee(q,p,rate)
        else:raise ValueError('unknown exchange fee venue')
        raw=fee['model_fee'];net=fee['net_fee']
        # Tie-breaking is unspecified for PM; ceil is a conservative bound.
        bound=max(raw,net) if venue=='kalshi' else raw.quantize(Decimal('.00001'),rounding=ROUND_CEILING)
        result['sides'][side]={'quantity':float(q),'price':float(p),'action':action,
            **{k:float(v) if isinstance(v,Decimal) else v for k,v in fee.items()},
            'conservative_fee_per_share':float(bound/value(q))}
    return result

"""Explicit fee, probability and sizing units for two-leg research."""
from dataclasses import dataclass
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
import math
from typing import Sequence

@dataclass(frozen=True)
class Interval:
    lower: float
    point: float
    upper: float

    def __post_init__(self):
        if not all(math.isfinite(x) for x in (self.lower,self.point,self.upper)) or not 0 <= self.lower <= self.point <= self.upper <= 1:
            raise ValueError('invalid probability interval')

def selected_book(yes_bid: float, yes_ask: float, side: str) -> tuple[float,float]:
    if not 0 <= yes_bid <= yes_ask <= 1: raise ValueError('invalid or crossed book')
    if side=='yes': return yes_bid,yes_ask
    if side=='no': return 1-yes_ask,1-yes_bid
    raise ValueError('unknown selected side')

def fee_per_share(price:float, rate:float) -> float:
    if not 0 <= price <= 1 or not math.isfinite(rate) or rate < 0: raise ValueError('invalid fee input')
    return rate*price*(1-price)

def fee_expanded_book(bid:float,ask:float,taker_rate:float) -> Interval:
    if not 0 <= bid <= ask <= 1: raise ValueError('invalid or crossed book')
    return Interval(max(0,bid-fee_per_share(bid,taker_rate)),(bid+ask)/2,min(1,ask+fee_per_share(ask,taker_rate)))

def pinnacle_fair(decimal_yes:float,decimal_no:float) -> Interval:
    """Multiplicative de-vig center; two-sided executable odds bracket.

    Bookmaker margin is already in the odds; no invented extra taker fee.
    This center is an assumption, and must be sensitivity-tested for longshots.
    """
    if not all(math.isfinite(v) and v>1 for v in (decimal_yes,decimal_no)): raise ValueError('invalid decimal odds')
    yes,no=1/decimal_yes,1/decimal_no
    if yes+no < 1-1e-12: raise ValueError('crossed bookmaker odds')
    # Exact zero-margin odds can invert endpoints by one floating-point ULP.
    lower,upper=min(yes,max(0,1-no)),min(1,yes)
    return Interval(lower,min(upper,max(lower,yes/(yes+no))),upper)

@dataclass(frozen=True)
class VenueFair:
    venue: str
    interval: Interval
    available_at: float
    liquidity_payout_dollars: float
    liquidity_available_at: float
    matched_contract_key: str

def liquidity_blend(values:Sequence[VenueFair],decision_at:float,contract_key:str,required_venues=frozenset({'kalshi','polymarket','pinnacle'}),maximum_age_seconds:float=120) -> Interval:
    if not values or {v.venue for v in values} != set(required_venues): raise ValueError('required venues missing or unexpected')
    if len({v.venue for v in values})!=len(values): raise ValueError('duplicate venue')
    for v in values:
        if v.matched_contract_key!=contract_key: raise ValueError('payoff mismatch')
        if not all(0 <= decision_at-t <= maximum_age_seconds for t in [v.available_at,v.liquidity_available_at]): raise ValueError('future or stale price/liquidity')
        if not math.isfinite(v.liquidity_payout_dollars) or v.liquidity_payout_dollars<=0: raise ValueError('liquidity missing or invalid')
    total=sum(v.liquidity_payout_dollars for v in values)
    return Interval(*(sum(getattr(v.interval,k)*v.liquidity_payout_dollars for v in values)/total for k in ['lower','point','upper']))

def joint_independence(left:Interval,right:Interval,rho:float=0) -> Interval:
    """Cross-fixture scenario; rho is an assumption, never fitted from prices."""
    if not 0<=rho<=1: raise ValueError('invalid adverse correlation stress')
    def joint(a,b): return min(a,b,a*b+rho*math.sqrt(a*(1-a)*b*(1-b)))
    # For positive rho, the function is not monotonic over all marginal ranges.
    # Keep the base interval monotonic and apply correlation reserve separately.
    if rho: raise ValueError('use stressed_joint_upper for correlation sensitivity')
    return Interval(left.lower*right.lower,left.point*right.point,left.upper*right.upper)

def stressed_joint_upper(left:Interval,right:Interval,rho:float) -> float:
    if not 0<=rho<=1: raise ValueError('invalid correlation stress')
    # sqrt(p(1-p)) reaches its interval maximum nearest 0.5. Bounding each
    # variance independently is conservative even when maxima occur elsewhere.
    a=min(left.upper,max(left.lower,.5));b=min(right.upper,max(right.lower,.5))
    return min(left.upper,right.upper,left.upper*right.upper+rho*math.sqrt(a*(1-a)*b*(1-b)))

def total_fee(quantity:float,price:float,rate:float,rounding_unit:float=.0001) -> float:
    """July-2026 convention: ceil(position cost + fee) to a centicent.

    Price is the purchased side's price. YES and NO quadratic fees agree before
    rounding; fractional quantity makes the position-cost rounding material.
    """
    if quantity<0 or not math.isfinite(quantity): raise ValueError('invalid quantity')
    fee_per_share(price,rate)
    q,p,r,u=map(lambda x:Decimal(str(x)),[quantity,price,rate,rounding_unit])
    if u<=0: raise ValueError('invalid rounding unit')
    cost=q*p; raw=q*r*p*(1-p)
    return float(((cost+raw)/u).to_integral_value(rounding=ROUND_CEILING)*u-cost)

def customer_quantity(budget:float,yes_price:float,taker_rate:float=.07,quantity_step:float=.01,include_customer_fee:bool=True) -> float:
    """Customer buys YES; $budget is not the maker's NO collateral."""
    if budget<=0 or not 0<yes_price<1 or quantity_step<=0: raise ValueError('invalid ticket inputs')
    unit=yes_price+(fee_per_share(yes_price,taker_rate) if include_customer_fee else 0)
    count=math.floor((budget/unit+1e-12)/quantity_step)*quantity_step
    while count>0 and count*yes_price+(total_fee(count,yes_price,taker_rate) if include_customer_fee else 0)>budget+1e-10:
        count=round(count-quantity_step,8)
    return round(count,8)

def short_yes_economics(quantity:float,yes_price:float,fair:float,maker_rate:float=.035) -> dict[str,float]:
    if not 0<=fair<=1 or not 0<yes_price<1: raise ValueError('invalid economics input')
    fee=total_fee(quantity,round(1-yes_price,10),maker_rate)
    return {'customer_premium':quantity*yes_price,'maker_fee':fee,'maximum_loss':quantity*(1-yes_price)+fee,'expected_edge':quantity*(yes_price-fair)-fee}

def affordable_short_yes_quantity(available_cash:float,observed_quantity:float,yes_price:float,maker_rate:float=.035,quantity_step:float=.01) -> float:
    """Use observed print capacity, limited only by cash for NO principal + fee."""
    if not all(math.isfinite(x) and x>=0 for x in [available_cash,observed_quantity]):raise ValueError('invalid capital or observed quantity')
    if not 0<yes_price<1 or quantity_step<=0:raise ValueError('invalid price or quantity step')
    if available_cash==0 or observed_quantity==0:return 0.
    affordable=customer_quantity(available_cash,round(1-yes_price,10),taker_rate=maker_rate,quantity_step=quantity_step)
    observed_steps=math.floor((observed_quantity+1e-10)/quantity_step)
    return round(min(affordable,observed_steps*quantity_step),8)

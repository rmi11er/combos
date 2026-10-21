"""Historical-only imputation and causal state reconstruction for fair research.

No collector or forward PricingService imports this module. Candle/price-only
inputs cannot establish executable size or a verified upstream heartbeat.
"""
from bisect import bisect_right
from dataclasses import replace
from datetime import datetime
import math
from .observations import Observation
from .weighted_fair import WeightPolicy,weighted_fair


def timestamp(value):return datetime.fromisoformat(value.replace('Z','+00:00')).timestamp()


class History:
    """Last available state, including suspensions; never skip an inactive row."""
    def __init__(self, rows, time_key):
        indexed={}
        for row in rows:
            at=timestamp(row[time_key]) if isinstance(row[time_key],str) else row[time_key]
            if at in indexed and indexed[at]!=row:raise ValueError('conflicting historical state timestamp')
            indexed[at]=row
        self.times=sorted(indexed);self.rows=[indexed[t] for t in self.times]

    def latest(self, at, delay=0):
        if delay<0:raise ValueError('negative historical delay')
        i=bisect_right(self.times,at-delay)-1
        if i<0:raise ValueError('no_prior_state')
        row=self.rows[i]
        if row.get('active') is False:raise ValueError('inactive_latest_state')
        return self.times[i],row


def historical_observations(key,kalshi,pm,pinnacle,at,depth=1000.,delay=30.,pm_fee=.05):
    """Impute PM depth from K; absent K depth uses an explicit shared scenario.

    PM raw spread is also unavailable in price-history: use the contemporaneous
    K raw spread as a separately disclosed proxy, then apply PM's own fees.
    State carry-forward is a historical completeness hypothesis, not proof of
    a fresh live poll. Original state times are retained in every record.
    """
    if not math.isfinite(depth) or depth<=0:raise ValueError('invalid depth scenario')
    kt,kr=kalshi;pt,pr=pm;yt,yr,nt,nr=pinnacle
    if max(kt+60,pt+60,yt+delay,nt+delay)>at:raise ValueError('historical lookahead')
    if any(r.get('active') is False for r in (yr,nr)):raise ValueError('inactive Pinnacle side')
    bid=float(kr['yes_bid']['close_dollars']);ask=float(kr['yes_ask']['close_dollars'])
    if not 0<=bid<=ask<=1:raise ValueError('invalid historical Kalshi book')
    point=float(pr['p'])
    if not 0<=point<=1:raise ValueError('invalid historical PM price')
    half=min((ask-bid)/2,point,1-point)
    kbid=kr.get('yes_bid_size',depth);kask=kr.get('yes_ask_size',depth)
    p_bid=pr.get('yes_bid',max(0.,point-half));p_ask=pr.get('yes_ask',min(1.,point+half))
    common={'market_key':key,'historical_only':True,'mapping_reference':'historical:normal_completed_game_only',
            'active':True,'available_at':at,'source_reference':'historical-pilot:'+key,
            'freshness_context':{'historical_state_carry_forward_assumed':True,
               'kalshi_state_at':kt,'polymarket_state_at':pt,'pinnacle_side_state_at':[yt,nt],
               'extra_archive_delay_seconds':delay,'upstream_freshness_validated':False}}
    k={**common,'venue':'kalshi','observed_at':at-60,'yes_bid':bid,'yes_ask':ask,
       'yes_bid_size':kbid,'yes_ask_size':kask,'size_unit':'payout_dollars','taker_rate':.07,
       'fee_reference':'historical:kalshi-.07-assumption','depth_imputed':not all(s in kr for s in ('yes_bid_size','yes_ask_size')),
       'depth_basis':'shared_historical_scenario_no_candle_depth'}
    p={**common,'venue':'polymarket','observed_at':at-60,'yes_bid':p_bid,'yes_ask':p_ask,
       'yes_bid_size':pr.get('yes_bid_size',kbid),'yes_ask_size':pr.get('yes_ask_size',kask),'size_unit':'payout_dollars','taker_rate':pm_fee,
       'fee_reference':'historical:retained-polymarket-fee-schedule','depth_imputed':not all(s in pr for s in ('yes_bid_size','yes_ask_size')),
       'depth_basis':'native_if_present_else_equal_to_Kalshi_historical_only','spread_imputed':not all(s in pr for s in ('yes_bid','yes_ask')),
       'spread_basis':'Kalshi_raw_spread_centered_on_PM_historical_price'}
    pin={**common,'venue':'pinnacle','observed_at':at-max(delay,30.),
         'decimal_odds_yes':yr['price'],'decimal_odds_no':nr['price'],
         'max_stake_yes':yr['limit'],'max_stake_no':nr['limit'],'limit_currency':'USD','limit_unit':'stake',
         'limit_basis':'historical_USD_stake_assumption_pending_provider_unit_confirmation'}
    return [k,p,pin]


def compare_fairs(records, stronger=False, policy=None, stronger_overrides=None):
    observations=[Observation.from_record(r) for r in records]
    policy=policy or WeightPolicy(delayed_pinnacle=True,exchange_max_age_seconds=180.,pregame_max_age_seconds=180.)
    if stronger:policy=replace(policy,**(stronger_overrides or {'pinnacle_score_multiplier':1.5,'pinnacle_weight_cap':.5}))
    at=records[0]['available_at'];fair=weighted_fair(observations,at,'pregame',policy)
    return fair,observations

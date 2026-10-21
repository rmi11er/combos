"""Retrospective walk-forward hygiene and causal historical markout scoring.

No execution, source collection or live pricing policy is implemented here.
"""
from bisect import bisect_right
from collections import defaultdict
from dataclasses import dataclass
import math
from statistics import mean


def finite(value, name):
    if isinstance(value, bool) or not math.isfinite(float(value)):
        raise ValueError('finite '+name+' required')
    return float(value)


@dataclass(frozen=True)
class Forecast:
    identifier: str
    model: str
    decision_at: float
    probability: float
    fixtures: tuple[str, ...]
    payoff: str
    quantity: float
    yes_price: float
    maker_fee: float
    outcome: float | None = None
    outcome_available_at: float | None = None
    quote_allowed: bool = True
    forecast_available_at: float | None = None

    def __post_init__(self):
        if not self.identifier or not self.model or not self.payoff or not self.fixtures:
            raise ValueError('forecast identity and fixture keys required')
        if not isinstance(self.fixtures, tuple) or any(not isinstance(f,str) or not f for f in self.fixtures):
            raise ValueError('immutable nonempty fixture keys required')
        if len(set(self.fixtures)) != len(self.fixtures):
            raise ValueError('duplicate fixture in forecast')
        at=finite(self.decision_at,'decision time')
        if not 0<=finite(self.probability,'probability')<=1:
            raise ValueError('invalid probability')
        if finite(self.quantity,'quantity')<=0 or not 0<finite(self.yes_price,'YES price')<1 or finite(self.maker_fee,'fee')<0:
            raise ValueError('invalid economics')
        if self.forecast_available_at is None or finite(self.forecast_available_at,'forecast availability')>at:
            raise ValueError('forecast unavailable at decision')
        if (self.outcome is None)!=(self.outcome_available_at is None):
            raise ValueError('outcome and availability must be paired')
        if self.outcome is not None:
            if not 0<=finite(self.outcome,'outcome')<=1 or finite(self.outcome_available_at,'outcome availability')<=at:
                raise ValueError('invalid outcome chronology/value')
        if type(self.quote_allowed) is not bool:
            raise ValueError('explicit quote guard required')


@dataclass(frozen=True)
class Fold:
    name: str
    fit_at: float
    test_end_at: float

    def __post_init__(self):
        if not self.name or finite(self.test_end_at,'test end')<=finite(self.fit_at,'fit time'):
            raise ValueError('invalid chronological fold')


def purged_fold(records, fold):
    """Training labels must be known strictly before fit; purge entire rows.

    Test fixture membership is an offline purge boundary, not a prediction
    feature. Deployable fitting needs its exclusion universe declared at fit.
    """
    test=[r for r in records if fold.fit_at<=r.decision_at<fold.test_end_at]
    test_fixtures={f for r in test for f in r.fixtures}
    prior=[r for r in records if r.decision_at<fold.fit_at]
    known=[r for r in prior if r.outcome is not None and r.outcome_available_at<fold.fit_at]
    train=[r for r in known if not test_fixtures.intersection(r.fixtures)]
    assert not {f for r in train for f in r.fixtures}.intersection(test_fixtures)
    return train,test,{'prior_forecasts':len(prior),'prior_with_known_labels':len(known),
                       'unknown_or_not_yet_available_labels':len(prior)-len(known),
                       'purged_training_rows':len(known)-len(train),
                       'training_rows':len(train),'test_rows':len(test),
                       'training_fixtures':len({f for r in train for f in r.fixtures}),
                       'test_fixtures':len(test_fixtures)}


@dataclass(frozen=True)
class CalibrationPolicy:
    minimum_training_fixtures: int = 20
    minimum_training_payoffs: int = 100
    minimum_training_days: int = 3
    prior_fixture_strength: float = 50.
    maximum_absolute_adjustment: float = .03

    def __post_init__(self):
        if any(type(v) is not int or v<1 for v in (self.minimum_training_fixtures,self.minimum_training_payoffs,self.minimum_training_days)):
            raise ValueError('positive training minima required')
        if finite(self.prior_fixture_strength,'prior strength')<=0 or not 0<finite(self.maximum_absolute_adjustment,'maximum adjustment')<1:
            raise ValueError('invalid calibration shrinkage')


@dataclass(frozen=True)
class ShrunkCalibration:
    adjustment: float
    fallback_reasons: tuple[str, ...]
    training_rows: int
    training_payoffs: int
    training_fixtures: int
    training_days: int
    fit_at: float

    def predict(self, probability):
        p=finite(probability,'probability')
        if not 0<=p<=1:raise ValueError('invalid probability')
        return min(1.,max(0.,p+self.adjustment))


def fit_shrunk_calibration(train, fit_at, policy=CalibrationPolicy(), day_key=None):
    """Fixed candidate: fixture-balanced residual, shrunk toward no adjustment.

    Repeated prints are averaged within economic payoff before fitting. No
    quantity weights or test results influence the fit. This is a hypothesis,
    not an assertion that additive calibration is optimal.
    """
    if len({r.model for r in train})>1:raise ValueError('fit one model at a time')
    if any(r.decision_at>=fit_at or r.outcome is None or r.outcome_available_at>=fit_at for r in train):
        raise ValueError('training chronology or outcome availability violation')
    day_key=day_key or (lambda t:int(t//86400))
    payoffs=defaultdict(list)
    for r in train:payoffs[r.payoff].append(r)
    fixtures=defaultdict(list)
    for rows in payoffs.values():
        if len({r.outcome for r in rows})!=1 or len({r.fixtures for r in rows})!=1:
            raise ValueError('conflicting economic payoff label or fixture identity')
        residual=mean(r.outcome-r.probability for r in rows)
        for fixture in rows[0].fixtures:fixtures[fixture].append(residual)
    days=len({day_key(r.decision_at) for r in train});reasons=[]
    if len(fixtures)<policy.minimum_training_fixtures:reasons.append('insufficient_training_fixtures')
    if len(payoffs)<policy.minimum_training_payoffs:reasons.append('insufficient_training_payoffs')
    if days<policy.minimum_training_days:reasons.append('insufficient_training_days')
    adjustment=0.
    if not reasons:
        raw=mean(mean(v) for v in fixtures.values())
        adjustment=len(fixtures)/(len(fixtures)+policy.prior_fixture_strength)*raw
        adjustment=max(-policy.maximum_absolute_adjustment,min(policy.maximum_absolute_adjustment,adjustment))
    return ShrunkCalibration(adjustment,tuple(reasons),len(train),len(payoffs),len(fixtures),days,fit_at)


def exposure_metrics(records, predictions=None, selected_only=False, minimum_edge=.003, outcome_as_of=math.inf):
    """Public-print economics; no inferred fills, funding path or Sharpe."""
    records=list(records)
    if len({r.model for r in records})>1:raise ValueError('score one model at a time')
    if len({r.identifier for r in records})!=len(records):raise ValueError('duplicate forecast identifier')
    if finite(minimum_edge,'minimum edge')<0:raise ValueError('nonnegative minimum edge required')
    predictions={r.identifier:r.probability for r in records} if predictions is None else predictions
    rows=[]
    for r in records:
        p=predictions[r.identifier]
        if not math.isfinite(p) or not 0<=p<=1:raise ValueError('invalid prediction')
        edge=r.quantity*(r.yes_price-p)-r.maker_fee
        if selected_only and (not r.quote_allowed or edge<minimum_edge*r.quantity):continue
        rows.append((r,p,edge))
    known=[(r,p,e) for r,p,e in rows if r.outcome is not None and r.outcome_available_at<=outcome_as_of]
    collateral=sum(r.quantity*(1-r.yes_price)+r.maker_fee for r,_,_ in rows)
    fixture_exposure=defaultdict(float)
    for r,_,_ in rows:
        cost=r.quantity*(1-r.yes_price)+r.maker_fee
        for fixture in r.fixtures:fixture_exposure[fixture]+=cost
    quantity=sum(r.quantity for r,_,_ in known)
    return {'observations':len(rows),'unique_payoffs':len({r.payoff for r,_,_ in rows}),
            'fixtures':len(fixture_exposure),'known_outcomes':len(known),
            'payout_notional':sum(r.quantity for r,_,_ in rows),
            'yes_premium':sum(r.quantity*r.yes_price for r,_,_ in rows),
            'gross_maximum_loss_sum':collateral,
            'largest_fixture_share_of_gross_loss':max(fixture_exposure.values(),default=0)/collateral if collateral else None,
            'expected_net_edge':sum(e for _,_,e in rows),
            'known_outcome_expected_edge':sum(e for _,_,e in known),
            'known_outcome_hypothetical_profit':sum(r.quantity*(r.yes_price-r.outcome)-r.maker_fee for r,_,_ in known),
            'brier':mean((p-r.outcome)**2 for r,p,_ in known) if known else None,
            'quantity_weighted_brier':sum(r.quantity*(p-r.outcome)**2 for r,p,_ in known)/quantity if quantity else None,
            'outcome_minus_forecast':mean(r.outcome-p for r,p,_ in known) if known else None,
            'quantity_weighted_outcome_minus_forecast':sum(r.quantity*(r.outcome-p) for r,p,_ in known)/quantity if quantity else None}


@dataclass(frozen=True)
class PricePoint:
    probability: float | None
    source_at: float
    available_at: float
    active: bool = True
    reference: str = ''

    def __post_init__(self):
        if finite(self.available_at,'availability')<finite(self.source_at,'source time'):
            raise ValueError('price availability precedes source')
        if type(self.active) is not bool:raise ValueError('explicit active flag required')
        if self.active and (self.probability is None or not 0<=finite(self.probability,'probability')<=1):
            raise ValueError('active probability required')


class CausalPriceSeries:
    def __init__(self, points):
        dedup={}
        for p in points:
            key=(p.available_at,p.source_at)
            if key in dedup and dedup[key]!=p:raise ValueError('conflicting price at identical source/availability')
            dedup[key]=p
        self.points=sorted(dedup.values(),key=lambda p:(p.available_at,p.source_at))
        self.available=[p.available_at for p in self.points];self.latest=[];best=None
        for p in self.points:
            if best is None or (p.source_at,p.available_at)>(best.source_at,best.available_at):best=p
            self.latest.append(best)

    def asof(self, at, maximum_source_age=None):
        if maximum_source_age is not None and finite(maximum_source_age,'maximum source age')<0:
            raise ValueError('nonnegative maximum source age required')
        at=finite(at,'as-of time');i=bisect_right(self.available,at)-1
        if i<0:raise ValueError('no_available_price')
        p=self.latest[i]
        if not p.active:raise ValueError('latest_price_inactive')
        if maximum_source_age is not None and at-p.source_at>maximum_source_age:raise ValueError('price_source_too_old')
        return p


def score_markout(entry, target, decision_at, horizon_seconds, yes_price, quantity, maker_fee=0.,
                  require_post_decision_source=True):
    """Future model mark, not executed liquidation or realized settlement P&L."""
    decision_at=finite(decision_at,'decision');horizon=finite(horizon_seconds,'horizon')
    if horizon<=0:raise ValueError('positive markout horizon required')
    target_at=decision_at+horizon
    if not entry.active or not target.active:raise ValueError('inactive_markout_state')
    if entry.available_at>decision_at:raise ValueError('entry_price_unavailable')
    if target.available_at>target_at:raise ValueError('target_price_unavailable_at_horizon')
    if target.available_at<=decision_at or target.source_at<=entry.source_at:
        raise ValueError('no_new_future_price_information')
    if require_post_decision_source and target.source_at<=decision_at:
        raise ValueError('target_source_not_after_decision')
    q=finite(quantity,'quantity');c=finite(yes_price,'YES price');fee=finite(maker_fee,'fee')
    if q<=0 or not 0<c<1 or fee<0:raise ValueError('invalid markout economics')
    return {'decision_at':decision_at,'horizon_seconds':horizon,'target_at':target_at,
            'entry_probability':entry.probability,'target_probability':target.probability,
            'probability_change':target.probability-entry.probability,
            'maker_NO_mark_change':q*(entry.probability-target.probability),
            'net_value_at_target':q*(c-target.probability)-fee,
            'entry_source_at':entry.source_at,'target_source_at':target.source_at,
            'target_available_at':target.available_at,'effective_source_horizon':target.source_at-decision_at,
            'entry_reference':entry.reference,'target_reference':target.reference}

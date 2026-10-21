"""Chronological, hypothetical public-print execution with explicit portfolio policy.

Pricing adapters provide causal probabilities; this module never reads future prices.
Settlement metadata affects allocation only at cash availability. Retrospective
performance separately attributes known eventual outcomes to the original trade.
"""
from collections import Counter, defaultdict
from dataclasses import dataclass, asdict
from datetime import datetime, time, timedelta
from decimal import Decimal
import heapq
import math
from statistics import mean, variance
from zoneinfo import ZoneInfo

from .event_store import EventStore
from .performance import build_curves, _number
from .risk import RiskLedger


@dataclass(frozen=True)
class BacktestConfig:
    entry_basis: str = 'stressed_upper'
    minimum_net_edge_per_share: float = .003
    capital_dollars: float = 10000.
    per_contract_dollars: float = 100.
    per_combo_dollars: float = 100.
    per_fixture_dollars: float = 250.
    settlement_delay_seconds: float = 0.
    timezone: str = 'America/Chicago'
    annualization_days: int = 365
    outcome_as_of: float | None = None
    maximum_yes_premium_dollars: float | None = None
    entry_filter: str = 'minimum_edge'
    minimum_net_edge_unit: str = 'combo_contract'

    def __post_init__(self):
        if self.entry_basis not in ('point', 'stressed_upper'):
            raise ValueError('unsupported entry basis')
        if self.entry_filter not in ('minimum_edge', 'all_priced'):
            raise ValueError('unsupported entry filter')
        if self.minimum_net_edge_unit not in ('combo_contract', 'leg_contract'):
            raise ValueError('unsupported minimum edge unit')
        for name in ('capital_dollars', 'per_contract_dollars', 'per_combo_dollars', 'per_fixture_dollars'):
            if _number(getattr(self, name), name, 0) <= 0:
                raise ValueError('capital and limits must be positive')
        _number(self.minimum_net_edge_per_share, 'minimum edge', 0)
        _number(self.settlement_delay_seconds, 'settlement delay', 0)
        _number(self.annualization_days, 'annualization days', 1)
        if self.outcome_as_of is not None:
            _number(self.outcome_as_of, 'outcome observation cutoff')
        if self.maximum_yes_premium_dollars is not None:
            if _number(self.maximum_yes_premium_dollars, 'maximum YES premium', 0) <= 0:
                raise ValueError('maximum YES premium must be positive')
        ZoneInfo(self.timezone)


def validate_opportunity(row, start_at, end_at):
    if not row['model'] or not row['evaluation_id']:
        raise ValueError('model and evaluation identifier required')
    at = _number(row['at'], 'decision time')
    if not start_at <= at < end_at:
        raise ValueError('decision outside reporting window')
    if _number(row['quantity'], 'quantity', 0) <= 0:
        raise ValueError('positive quantity required')
    if not 0 < _number(row['yes_price'], 'YES price', 0, 1) < 1:
        raise ValueError('open-market price must be strictly between zero and one')
    _number(row['maker_fee'], 'maker fee', 0)
    point = _number(row['fair_point'], 'fair point', 0, 1)
    _number(row['stressed_upper'], 'stressed upper', point, 1)
    if type(row['quote_allowed']) is not bool:
        raise ValueError('explicit quote guard required')
    if not 0 < _number(row['risk_multiplier'], 'risk multiplier', 0, 1):
        raise ValueError('positive risk multiplier required')
    buckets = row['buckets']
    if set(buckets) != {'contract', 'fixture', 'combo'}:
        raise ValueError('all canonical risk bucket families required')
    if any(not isinstance(values, (list, tuple)) or not values or
           any(not isinstance(k, str) or not k for k in values) for values in buckets.values()):
        raise ValueError('nonempty canonical risk buckets required')
    settled, value = row.get('settled_at'), row.get('yes_settlement')
    if (settled is None) != (value is None):
        raise ValueError('settlement time and value must be paired')
    if settled is not None:
        if _number(settled, 'settlement time') <= at:
            raise ValueError('settlement precedes or equals decision')
        _number(value, 'settlement value', 0, 1)
    # Sampling weights are provenance, never synthetic trades or funding.
    if row.get('sampling_weight', 1) != 1:
        raise ValueError('portfolio backtest requires an unweighted observed cohort')


def daily_statistics(fills, start_at, end_at, config, attribution='settlement'):
    """Full local calendar days; zero-activity days included. No MTM is inferred.

    Returns are daily attributed P&L / fixed reporting capital in both regimes.
    Trade cohorts use [midnight, next midnight); settlement accounting retains
    (midnight, next midnight]. Partial days are excluded. Retrospective trade
    cohorts include supplied outcomes after the trading window, never in cash.
    """
    tz = ZoneInfo(config.timezone)
    if attribution not in ('trade', 'settlement'):
        raise ValueError('invalid P&L attribution')
    resolved = [f for f in fills if f.get('settled_at') is not None and
                (attribution == 'settlement' or config.outcome_as_of is None or f['settled_at'] <= config.outcome_as_of)]
    day = datetime.fromtimestamp(start_at, tz).date()
    rows = []
    while True:
        left = datetime.combine(day, time(), tz).timestamp()
        right = datetime.combine(day + timedelta(days=1), time(), tz).timestamp()
        if right > end_at:
            break
        if left >= start_at:
            settled = [f for f in resolved if left <= f['filled_at'] < right] if attribution == 'trade' else [
                f for f in resolved if left < f['settled_at'] <= right]
            pnl = sum(f['quantity'] * (f['yes_price'] - f['yes_settlement']) - f['maker_fee'] for f in settled)
            rows.append({'date': day.isoformat(), 'pnl_dollars': pnl,
                         'return_on_reporting_capital': pnl / config.capital_dollars,
                         'attributed_outcomes': len(settled), 'attribution': attribution})
        day += timedelta(days=1)
    returns = [r['return_on_reporting_capital'] for r in rows]
    var = variance(returns) if len(returns) >= 2 else None
    sharpe = mean(returns) / math.sqrt(var) * math.sqrt(config.annualization_days) if var and var > 0 else None
    return rows, {'full_calendar_days': len(rows), 'active_pnl_days': sum(r['attributed_outcomes'] > 0 for r in rows),
                  'pnl_attribution': attribution,
                  'daily_return_variance': var, 'daily_return_variance_bp2': var * 1e8 if var is not None else None,
                  'daily_pnl_variance_dollars2': var * config.capital_dollars**2 if var is not None else None,
                  'annualized_sharpe': sharpe,
                  'sharpe_unavailable_reason': None if sharpe is not None else 'fewer than two days or zero variance',
                  'statistics_basis': f'{attribution}-attributed daily P&L / fixed reporting capital; sample variance ddof=1; risk-free=0',
                  'annualization_days': config.annualization_days,
                  'interpretation': 'Descriptive attribution statistic; sparse activity and shared fixtures limit inference. Not spendable equity.'}


def attribute_trade_performance(curves, fills, config):
    """Add retrospective outcome P&L and ex-ante accepted edge at fill time.

    Do not modify realized_pnl, equity, available_cash or committed_cash: these
    fields describe the causal settlement ledger used for funding and limits.
    """
    changes = defaultdict(lambda: defaultdict(float))
    for fill in fills:
        d = changes[fill['filled_at']]
        d['accepted_point_edge'] += fill['point_edge']
        d['accepted_stressed_edge'] += fill['stressed_edge']
        d['accepted_selected_edge'] += fill['selected_edge']
        known = fill['settled_at'] is not None and (config.outcome_as_of is None or fill['settled_at'] <= config.outcome_as_of)
        fill['pnl_attributed_at'] = fill['filled_at'] if known else None
        fill['eventual_net_pnl'] = fill['quantity']*(fill['yes_price']-fill['yes_settlement'])-fill['maker_fee'] if known else None
        if known:
            d['trade_attributed_pnl'] += fill['eventual_net_pnl']
            d['resolved_outcomes'] += 1
        else:
            d['unresolved_outcomes'] += 1
    totals = {key: 0. for key in ('accepted_point_edge', 'accepted_stressed_edge', 'accepted_selected_edge',
                                 'trade_attributed_pnl', 'resolved_outcomes', 'unresolved_outcomes')}
    peak = config.capital_dollars
    drawdown = 0.
    for row in curves:
        for key, delta in changes[row['at']].items():
            totals[key] += delta
        row.update(totals)
        row['trade_attributed_equity'] = config.capital_dollars + totals['trade_attributed_pnl']
        row['point_edge_equity'] = config.capital_dollars + totals['accepted_point_edge']
        row['selected_edge_equity'] = config.capital_dollars + totals['accepted_selected_edge']
        peak = max(peak, row['trade_attributed_equity'])
        drawdown = max(drawdown, peak-row['trade_attributed_equity'])
    return drawdown


def run_backtest(opportunities, start_at, end_at, config=None, constrained=True):
    config = config or BacktestConfig()
    _number(start_at, 'start'); _number(end_at, 'end')
    if end_at <= start_at:
        raise ValueError('invalid reporting window')
    seen = set()
    for row in opportunities:
        validate_opportunity(row, start_at, end_at)
        key = (row['model'], row['evaluation_id'])
        if key in seen:
            raise ValueError('duplicate model opportunity')
        seen.add(key)
    all_fills, all_decisions, all_curves, all_daily, summaries = [], [], [], [], []
    for model in sorted({r['model'] for r in opportunities}):
        store = EventStore(':memory:')
        ledger = RiskLedger(store, {k: getattr(config, k) for k in
                            ('capital_dollars', 'per_contract_dollars', 'per_combo_dollars', 'per_fixture_dollars')})
        pending, fills, decisions, evaluations = [], [], [], []
        try:
            for row in sorted((r for r in opportunities if r['model'] == model), key=lambda r: (r['at'], r['evaluation_id'])):
                at, identifier = row['at'], row['evaluation_id']
                # Cash is released only when actual settlement is available.
                while pending and pending[0][0] <= at:
                    settled_at, old_id, payout = heapq.heappop(pending)
                    if constrained:
                        with store.transaction():
                            ledger.transition(old_id, 'simulated_settled', settled_at, 0, payout)
                q, p, fee = row['quantity'], row['yes_price'], row['maker_fee']
                point_edge = q * (p - row['fair_point']) - fee
                stressed_edge = q * (p - row['stressed_upper']) - fee
                edge = point_edge if config.entry_basis == 'point' else stressed_edge
                edge_units = 1
                if config.minimum_net_edge_unit == 'leg_contract':
                    edge_units = row.get('source', {}).get('nlegs')
                    if type(edge_units) is not int or not 2 <= edge_units <= 4:
                        raise ValueError('verified_two_through_four_leg_count_required')
                required_edge = q * config.minimum_net_edge_per_share * edge_units
                evaluations.append({'model': model, 'evaluation_id': identifier, 'at': at, 'quantity': q,
                                    'yes_price': p, 'point_edge': point_edge, 'stressed_edge': stressed_edge})
                decision = {**row, 'entry_basis': config.entry_basis, 'selected_net_edge': edge,
                            'required_net_edge': required_edge if config.entry_filter == 'minimum_edge' else None,
                            'entry_filter': config.entry_filter, 'minimum_net_edge_unit': config.minimum_net_edge_unit,
                            'observed_yes_premium': q * p,
                            'accepted': False, 'reason': 'insufficient_edge'}
                if (config.maximum_yes_premium_dollars is not None and
                        Decimal(str(q)) * Decimal(str(p)) > Decimal(str(config.maximum_yes_premium_dollars))):
                    decision['reason'] = 'yes_premium_limit'
                elif not row['quote_allowed']:
                    decision['reason'] = 'quote_guard'
                elif config.entry_filter == 'all_priced' or edge >= required_edge:
                    decision.update(accepted=True, reason='accepted')
                    if constrained:
                        with store.transaction():
                            risk = ledger.reserve(identifier, 'historical_creator_unknown', q * (1-p) + fee,
                                                  row['buckets'], at + 1, {'quantity': q}, row['risk_multiplier'])
                            decision.update(accepted=risk['allowed'], reason=risk.get('reason', 'accepted'), risk=risk)
                            if risk['allowed']:
                                ledger.transition(identifier, 'simulated_filled', at, 0)
                    if decision['accepted']:
                        settled = row.get('settled_at')
                        settled = settled + config.settlement_delay_seconds if settled is not None else None
                        fill = {'model': model, 'fill_id': identifier, 'filled_at': at, 'quantity': q,
                                'yes_price': p, 'maker_fee': fee, 'settled_at': settled,
                                'yes_settlement': row.get('yes_settlement'), 'basis': 'simulated_execution',
                                'point_edge': point_edge, 'stressed_edge': stressed_edge, 'selected_edge': edge}
                        fills.append(fill)
                        if settled is not None:
                            heapq.heappush(pending, (settled, identifier, q * (1-row['yes_settlement'])))
                decisions.append(decision)
        finally:
            store.close()
        curves = build_curves(evaluations, fills, start_at, end_at)
        peak, max_drawdown = config.capital_dollars, 0.
        for row in curves:
            equity = config.capital_dollars + row['realized_pnl']
            peak = max(peak, equity); max_drawdown = max(max_drawdown, peak-equity)
            row.update(equity=equity, available_cash=equity-row['committed_cash'])
        attributed_drawdown = attribute_trade_performance(curves, fills, config)
        daily, stats = daily_statistics(fills, start_at, end_at, config, attribution='trade')
        for row in daily:
            row['model'] = model
        last = curves[-1]
        summaries.append({'model': model, **stats, 'evaluations': len(evaluations), 'fills': len(fills),
                          'accepted_point_edge': sum(d['quantity']*(d['yes_price']-d['fair_point'])-d['maker_fee'] for d in decisions if d['accepted']),
                          'accepted_stressed_edge': sum(d['quantity']*(d['yes_price']-d['stressed_upper'])-d['maker_fee'] for d in decisions if d['accepted']),
                          'settled_fills': int(last['settled_fills']), 'open_fills': len(fills)-int(last['settled_fills']),
                          'realized_pnl': last['realized_pnl'], 'ending_equity': last['equity'],
                          'trade_attributed_pnl': last['trade_attributed_pnl'],
                          'ending_trade_attributed_equity': last['trade_attributed_equity'],
                          'resolved_outcomes': int(last['resolved_outcomes']),
                          'unresolved_outcomes': int(last['unresolved_outcomes']),
                          'outcome_attribution_complete': last['unresolved_outcomes'] == 0,
                          'yes_premium': last['filled_yes_premium'], 'payout_notional': last['filled_payout_notional'],
                          'maker_cash_spent': last['maker_cash_spent'], 'ending_committed_cash': last['committed_cash'],
                          'max_settled_equity_drawdown_dollars': max_drawdown,
                          'max_trade_attributed_drawdown_dollars': attributed_drawdown,
                          'peak_committed_cash': max(r['committed_cash'] for r in curves),
                          'minimum_starting_funding_for_path': max(0., max(r['committed_cash']-r['realized_pnl'] for r in curves)),
                          'additional_funding_above_reporting_base': max(0., -min(r['available_cash'] for r in curves)),
                          'decisions': dict(Counter(d['reason'] for d in decisions))})
        all_fills.extend(fills); all_decisions.extend(decisions); all_curves.extend(curves); all_daily.extend(daily)
    return {'configuration': asdict(config), 'constrained': constrained,
            'execution_assumption': 'Hypothetical full fill at each eligible observed YES-taker public print. No RFQ win/queue model.',
            'equity_basis': 'Retrospective: starting capital + eventual known settlement P&L attributed at trade time. Not spendable capital.',
            'cash_basis': 'Cash, allocation and exposure release use actual settlement time; attributed P&L and expected edge cannot fund trades.',
            'edge_basis': 'Cumulative accepted-trade net edge at trade time; dollars are summed at simulated sizes, not reinvested before settlement.',
            'outcome_basis': 'All supplied known settlements, including after trading-window end' if config.outcome_as_of is None else f'Settlements observed by {config.outcome_as_of}',
            'funding_basis': f'Funded ${config.capital_dollars:g} account' if constrained else 'Unlimited funding; fixed capital is a reporting normalization only',
            'summaries': summaries, 'decisions': all_decisions, 'fills': all_fills, 'curves': all_curves, 'daily': all_daily}

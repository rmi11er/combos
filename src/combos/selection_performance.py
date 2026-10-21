"""Compare selected prints with their entire priceable seller cohort.

Unfiltered and rejected curves have unlimited funding and are retrospective
outcome benchmarks. Their P&L is not the actual market-making industry's P&L.
"""
from collections import defaultdict
from decimal import Decimal

from .backtest import daily_statistics


def selection_performance(opportunities, decisions, start_at, end_at, config):
    accepted = {(d['model'], d['evaluation_id']) for d in decisions if d['accepted']}
    grouped = defaultdict(list)
    for r in opportunities:
        if (config.maximum_yes_premium_dollars is not None and
                Decimal(str(r['quantity'])) * Decimal(str(r['yes_price'])) >
                Decimal(str(config.maximum_yes_premium_dollars))):
            continue
        grouped[r['model']].append(r)
    curves, summaries = [], []
    for model in sorted({r['model'] for r in opportunities}):
        rows = grouped[model]
        for group in ('all_priced', 'selected', 'rejected'):
            candidates = [r for r in rows if group == 'all_priced' or
                          ((model, r['evaluation_id']) in accepted) == (group == 'selected')]
            changes = defaultdict(lambda: {'pnl': 0., 'prints': 0, 'unresolved': 0})
            fills = []
            for r in candidates:
                d = changes[r['at']]; d['prints'] += 1
                settled = r['settled_at']
                if settled is not None:
                    settled += config.settlement_delay_seconds
                known = settled is not None and (config.outcome_as_of is None or settled <= config.outcome_as_of)
                if known:
                    d['pnl'] += r['quantity'] * (r['yes_price'] - r['yes_settlement']) - r['maker_fee']
                else:
                    d['unresolved'] += 1
                fills.append({**r, 'filled_at': r['at'], 'settled_at': settled})
            total = {'pnl': 0., 'prints': 0, 'unresolved': 0}
            for at in sorted({start_at, end_at, *changes}):
                for key, v in changes[at].items():
                    total[key] += v
                curves.append({'model': model, 'group': group, 'at': at, **total,
                               'equity': config.capital_dollars + total['pnl']})
            _, stats = daily_statistics(fills, start_at, end_at, config, attribution='trade')
            summaries.append({'model': model, 'group': group, **total, **stats})
    return {'curves': curves, 'summaries': summaries,
            'basis': 'All priceable observed YES-taker prints within the premium limit. Selected follows portfolio decisions; all/rejected have unlimited exposure. Known outcomes at trade time.'}

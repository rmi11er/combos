#!/usr/bin/env python3
"""Descriptive exposure and residual audit of frozen historical accepted fills.

The <=$50 YES-premium subset is a post-hoc cohort filter of observed prints,
not a portfolio replay or a reconstruction of original RFQ ticket sizes.
No API calls. No independent-trade assumptions are used to produce confidence
intervals; naive and collapsed-combo standard deviations are explicitly diagnostic.
"""
import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime
import hashlib
import json
from pathlib import Path
from statistics import median
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
FULLGAME = {'KXNCAAFGAME', 'KXNCAAFSPREAD', 'KXNCAAFTOTAL'}


def dump_csv(path, rows):
    if not rows:
        path.write_text('')
        return
    keys = list(dict.fromkeys(k for row in rows for k in row))
    with path.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, keys)
        writer.writeheader()
        writer.writerows(rows)


def load_fills(folder, regime):
    accepted = {}
    for line in (folder / f'{regime}_decisions.jsonl').open():
        row = json.loads(line)
        if row['accepted']:
            accepted[(row['model'], row['evaluation_id'])] = row
    result = []
    for fill in csv.DictReader((folder / f'{regime}_fills.csv').open()):
        row = dict(accepted.pop((fill['model'], fill['fill_id'])))
        q, price = float(fill['quantity']), float(fill['yes_price'])
        legs = row['source_context']['legs']
        outcome = None if fill['yes_settlement'] == '' else float(fill['yes_settlement'])
        pnl = None if fill['eventual_net_pnl'] == '' else float(fill['eventual_net_pnl'])
        if outcome is None:
            assert pnl is None
        else:
            assert abs(pnl - (q * (price - outcome) - float(fill['maker_fee']))) < 1e-7
        row.update(quantity=q, yes_price=price, yes_premium=q * price,
                   pnl=pnl, outcome=outcome, point_edge=float(fill['point_edge']),
                   leg_count=len(legs),
                   scope='fullgame_only' if all(x['market_ticker'].split('-')[0] in FULLGAME for x in legs) else 'includes_extended_nonplayer',
                   signature=json.dumps(sorted((x['market_ticker'], x['side']) for x in legs), separators=(',', ':')),
                   date=datetime.fromtimestamp(float(fill['filled_at']), ZoneInfo('America/Chicago')).strftime('%Y-%m-%d'),
                   hour=datetime.fromtimestamp(float(fill['filled_at']), ZoneInfo('America/Chicago')).strftime('%Y-%m-%d %H:00'),
                   size_bucket='<=10' if q * price <= 10 else '10-50' if q * price <= 50 else '>50')
        row['combo'] = row['source_context']['combo_ticker']
        result.append(row)
    assert not accepted
    return result


def stats(rows):
    resolved = [r for r in rows if r['outcome'] is not None]
    winners = [r for r in resolved if r['pnl'] > 0]
    losers = [r for r in resolved if r['pnl'] < 0]
    q = sum(r['quantity'] for r in resolved)
    return {'fills': len(rows), 'resolved': len(resolved), 'open': len(rows)-len(resolved),
            'winning_fills': len(winners), 'losing_fills': len(losers),
            'winning_pnl': sum(r['pnl'] for r in winners), 'losing_pnl': sum(r['pnl'] for r in losers),
            'mean_winning_pnl': sum(r['pnl'] for r in winners)/len(winners) if winners else None,
            'mean_losing_pnl': sum(r['pnl'] for r in losers)/len(losers) if losers else None,
            'median_resolved_pnl': median(r['pnl'] for r in resolved) if resolved else None,
            'unweighted_fair_yes': sum(r['fair_point'] for r in resolved)/len(resolved) if resolved else None,
            'unweighted_actual_yes': sum(r['outcome'] for r in resolved)/len(resolved) if resolved else None,
            'contract_weighted_fair_yes': sum(r['quantity']*r['fair_point'] for r in resolved)/q if q else None,
            'contract_weighted_actual_yes': sum(r['quantity']*r['outcome'] for r in resolved)/q if q else None,
            'yes_premium': sum(r['yes_premium'] for r in rows),
            'payout_notional': sum(r['quantity'] for r in rows),
            'point_edge_all': sum(r['point_edge'] for r in rows),
            'point_edge_resolved': sum(r['point_edge'] for r in resolved),
            'pnl_resolved': sum(r['pnl'] for r in resolved),
            'residual_resolved': sum(r['pnl'] - r['point_edge'] for r in resolved),
            'combo_tickers': len({r['combo'] for r in rows}),
            'selected_leg_signatures': len({r['signature'] for r in rows}),
            'fixtures': len({x for r in rows for x in r['buckets']['fixture']}),
            'canonical_contract_buckets': len({x for r in rows for x in r['buckets']['contract']}),
            'trade_dates': len({r['date'] for r in rows})}


def effective_count(weights):
    weights = list(weights)
    return sum(weights)**2 / sum(x*x for x in weights) if weights and sum(x*x for x in weights) else 0


def concentration(rows):
    resolved = [r for r in rows if r['outcome'] is not None]
    combos = defaultdict(list)
    fixtures = set()
    parent = {}
    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for row in resolved:
        combos[row['combo']].append(row)
        fs = row['buckets']['fixture']
        fixtures.update(fs)
        for f in fs:
            parent[find(f)] = find(fs[0])
    components = defaultdict(list)
    for row in resolved:
        components[find(row['buckets']['fixture'][0])].append(row)
    combo_sizes = [sum(r['quantity'] for r in rs) for rs in combos.values()]
    naive_variance = sum(r['quantity']**2 * r['fair_point'] * (1-r['fair_point']) for r in resolved if r['outcome'] in (0, 1))
    combo_variance = 0
    for rs in combos.values():
        outcomes = {r['outcome'] for r in rs}
        if len(outcomes) != 1:
            raise ValueError('Inconsistent outcome for combo ' + rs[0]['combo'])
        if outcomes <= {0, 1}:
            q = sum(r['quantity'] for r in rs)
            p = sum(r['quantity'] * r['fair_point'] for r in rs) / q
            combo_variance += q*q*p*(1-p)
    return {'resolved_prints': len(resolved), 'resolved_combos': len(combos),
            'resolved_fixtures': len(fixtures), 'fixture_overlap_components': len(components),
            'largest_overlap_component_print_fraction': max((len(rs) for rs in components.values()), default=0)/len(resolved) if resolved else 0,
            'largest_overlap_component_notional_fraction': max((sum(r['quantity'] for r in rs) for rs in components.values()), default=0)/sum(r['quantity'] for r in resolved) if resolved else 0,
            'print_notional_hhi_effective_count': effective_count(r['quantity'] for r in resolved),
            'combo_notional_hhi_effective_count': effective_count(combo_sizes),
            'naive_independent_print_sd_diagnostic': naive_variance**.5,
            'independent_combo_sd_diagnostic': combo_variance**.5,
            'uncertainty_warning': 'Neither SD is a calibrated standard error: prints repeat outcomes and distinct combos share fixtures; weighted combo probabilities are descriptive frozen forecasts. No p-values or confidence intervals.'}


def grouped(rows, key):
    groups = defaultdict(list)
    for row in rows:
        groups[key(row)].append(row)
    return groups


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--backtests', type=Path, default=ROOT/'runs/cfb_full_week_20260907/backtests_settlement_refreshed')
    p.add_argument('--out', type=Path, default=ROOT/'runs/cfb_performance_audit_20260907/concentration')
    p.add_argument('--premium50-backtests', type=Path, default=ROOT/'runs/cfb_performance_audit_20260907')
    a = p.parse_args(); a.out.mkdir(parents=True, exist_ok=True)
    summaries, breakdowns, clusters, uncertainty, forecast_bins = [], [], [], [], []
    manifests = []
    folders = [(run, a.backtests/run) for run in ('point_diagnostic', 'common_point_diagnostic')]
    folders += [(run, a.premium50_backtests/run) for run in ('point_premium50', 'common_point_premium50')
                if (a.premium50_backtests/run/'manifest.json').exists()]
    for run, folder in folders:
        manifests.append({'path': str(folder/'manifest.json'), 'sha256': hashlib.sha256((folder/'manifest.json').read_bytes()).hexdigest()})
        for regime in ('constrained', 'unconstrained'):
            for suffix in ('fills.csv', 'decisions.jsonl'):
                source = folder / f'{regime}_{suffix}'
                manifests.append({'path': str(source), 'sha256': hashlib.sha256(source.read_bytes()).hexdigest()})
            fills = load_fills(folder, regime)
            for model, model_rows in grouped(fills, lambda r:r['model']).items():
                for cohort, rows in [('all_frozen_fills', model_rows), ('frozen_fills_yes_premium_le50', [r for r in model_rows if r['yes_premium'] <= 50])]:
                    context = dict(run=run, regime=regime, model=model, cohort=cohort)
                    summaries.append(dict(context, **stats(rows)))
                    uncertainty.append(dict(context, **concentration(rows)))
                    for dimension, key in [('size', lambda r:r['size_bucket']), ('legs', lambda r:r['leg_count']),
                                           ('scope', lambda r:r['scope']), ('date', lambda r:r['date']),
                                           ('hour', lambda r:r['hour'])]:
                        for value, bucket in grouped(rows, key).items():
                            breakdowns.append(dict(context, dimension=dimension, group=value, **stats(bucket)))
                    for value, bucket in grouped(rows, lambda r:'0.3-0.5c' if r['point_edge']/r['quantity'] < .005 else '0.5-1c' if r['point_edge']/r['quantity'] < .01 else '1-3c' if r['point_edge']/r['quantity'] < .03 else '3c+').items():
                        resolved = [r for r in bucket if r['outcome'] is not None]
                        q = sum(r['quantity'] for r in resolved)
                        forecast_bins.append(dict(context, net_edge_bin=value, **stats(bucket)))
                    for dimension in ('combo', 'fixture', 'contract'):
                        buckets = defaultdict(list)
                        for r in rows:
                            keys = [r['combo']] if dimension=='combo' else r['buckets'][dimension]
                            for key in keys:
                                buckets[key].append(r)
                        for key, bucket in buckets.items():
                            record = dict(context, dimension=dimension, group=key, **stats(bucket))
                            # Equal-leg attribution is an accounting allocation, not causation.
                            record['equal_leg_allocated_pnl'] = sum((r['pnl'] or 0)/(1 if dimension=='combo' else len(r['buckets'][dimension])) for r in bucket)
                            clusters.append(record)
    for name, rows in [('summary', summaries), ('breakdowns', breakdowns), ('clusters', clusters), ('uncertainty_diagnostics', uncertainty), ('forecast_bins', forecast_bins)]:
        dump_csv(a.out/(name+'.csv'), rows)
    manifest={'source_backtests':str(a.backtests),'inputs':manifests,
              'audit_script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'filter':'Observed trade-print YES premium = quantity * YES price <= $50; no clipping. Parent RFQ IDs and total RFQ quantities unavailable. The second cohort is a post-hoc filter of frozen accepted fills; run folders named premium50 contain separately replayed official capped portfolios.',
              'outcome_comparison':'PnL residual uses only outcome-resolved fills and their matching ex-ante point edge. Unresolved fills remain separately reported.',
              'cluster_caveat':'Distinct fixtures/combo tickers are counts, not guaranteed independent trials. A connected fixture-overlap graph prevents a defensible iid-trade confidence interval.',
              'top_cluster_caveat':'Fixture/contract participation PnL overlaps across groups. Equal-leg allocated PnL sums to total but is not causal attribution.'}
    (a.out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps({'summary_rows':len(summaries),'cluster_rows':len(clusters),'out':str(a.out)}))


if __name__=='__main__':main()

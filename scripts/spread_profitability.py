#!/usr/bin/env python3
"""Unfiltered payout-weighted seller profitability versus summed leg spreads."""
import argparse
from bisect import bisect_right
from collections import defaultdict
import gzip
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EDGES = [0., 2., 4., 6., 10., 20.]
LABELS = ['0–<2', '2–<4', '4–<6', '6–<10', '10–<20', '20+']


def aggregate(rows):
    known = [r for r in rows if r['yes_settlement'] is not None and r['settled_at'] is not None]
    unknown = [r for r in rows if r['yes_settlement'] is None or r['settled_at'] is None]
    q = sum(r['quantity'] for r in rows)
    kq = sum(r['quantity'] for r in known)
    pnl = sum(r['quantity']*(r['yes_price']-r['yes_settlement'])-r['maker_fee'] for r in known)
    lo, hi = (pnl+sum(r['quantity']*(r['yes_price']-outcome)-r['maker_fee'] for r in unknown) for outcome in (1., 0.))
    return {'prints': len(rows), 'known_prints': len(known), 'unknown_prints': len(unknown),
            'payout_notional': q, 'known_payout_notional': kq, 'unknown_payout_notional': q-kq,
            'yes_premium': sum(r['quantity']*r['yes_price'] for r in rows),
            'known_net_pnl': pnl, 'known_net_cents_per_contract': 100*pnl/kq if kq else None,
            'loose_final_pnl_bounds': [lo, hi],
            'final_cents_bounds': [100*lo/q, 100*hi/q] if q else [None, None]}


def bucket(width):
    # Native cents sum with floating-point noise; round only bin assignment.
    return bisect_right(EDGES, round(width, 8))-1


def inputs(root, sport):
    path = root/sport/'features.jsonl.gz'
    with gzip.open(path, 'rt') as f:
        features = {r['evaluation_id']: r for r in map(json.loads, f)}
    replay = (ROOT/'runs/cfb_full_week_20260907/replay_settlement_refreshed/opportunities.json' if sport == 'cfb'
              else ROOT/'runs/mlb_historical_20260907/replay/opportunities.json')
    data = json.loads(replay.read_text())
    rows, seen = [], set()
    for r in data['opportunities']:
        # One price/outcome record per print. No model-based eligibility,
        # quote guard, edge, liquidity, premium or capital filter is applied.
        if r['model'] != 'kalshi' or r['evaluation_id'] not in features:
            continue
        if r['evaluation_id'] in seen:
            raise ValueError('duplicate_print')
        seen.add(r['evaluation_id']); f = features[r['evaluation_id']]
        rows.append({**r, 'nlegs': len(f['legs']),
                     'raw_width_sum_cents': sum(p['raw_width_cents'] for p in f['pairs']),
                     'fee_width_sum_cents': 100*sum(p['width'] for p in f['pairs'])})
    if seen != set(features):
        raise ValueError('feature_trade_join_incomplete')
    return rows, {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in (path, replay)}


def plot(results, out, measure):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FuncFormatter
    fig, axes = plt.subplots(3, 2, figsize=(14, 11), sharex=True)
    colors = {'all': '#222222', '2': '#0072B2', '3': '#D55E00', '4': '#009E73'}
    x = list(range(len(LABELS)))
    fmt = FuncFormatter(lambda v, _: f'${v/1e6:.1f}m' if abs(v)>=1e6 else f'${v/1000:.0f}k' if abs(v)>=1000 else f'${v:.0f}')
    for col, sport in enumerate(('cfb', 'mlb')):
        r = results[sport][measure]
        allbins = r['all']
        for n in ('all', '2', '3', '4'):
            bs = r[n]
            y = [b['known_net_cents_per_contract'] if b['known_payout_notional'] else float('nan') for b in bs]
            supported = [v if b['known_prints'] >= 30 else float('nan') for v, b in zip(y, bs)]
            axes[0, col].plot(x, supported, marker='o', ls='-' if n=='all' else '--', color=colors[n],
                              lw=2 if n=='all' else 1, label='All leg counts' if n=='all' else n+' legs')
            sparse = [(i, v) for i, (v, b) in enumerate(zip(y, bs)) if 0 < b['known_prints'] < 30]
            if sparse:
                axes[0, col].scatter([i for i, v in sparse], [v for i, v in sparse],
                                     facecolors='none', edgecolors=colors[n], s=35, zorder=5)
        axes[0, col].set_title(f"{sport.upper()} · {results[sport]['overall']['prints']:,} prints", fontsize=12)
        axes[0, col].set_ylabel('Net P&L / known payout contracts (cents)')
        axes[0, col].legend(fontsize=9)
        cum = r['cumulative']
        axes[1, col].plot(x, [b['known_net_pnl'] for b in cum], color=colors['all'], marker='o', label='Known net P&L')
        axes[1, col].fill_between(x, [b['loose_final_pnl_bounds'][0] for b in cum],
                                [b['loose_final_pnl_bounds'][1] for b in cum], color='#999999', alpha=.25, label='Unresolved-outcome bounds')
        axes[1, col].set_ylabel('Cumulative P&L, narrow → wide ($)')
        axes[1, col].yaxis.set_major_formatter(fmt)
        axes[1, col].legend(fontsize=8)
        axes[2, col].bar(x, [b['known_payout_notional'] for b in allbins], color='#7EA7BE', label='Known outcomes')
        axes[2, col].bar(x, [b['unknown_payout_notional'] for b in allbins],
                        bottom=[b['known_payout_notional'] for b in allbins], color='#BBBBBB', hatch='//', label='Unknown outcomes')
        axes[2, col].set_ylabel('Payout notional in bucket ($)')
        axes[2, col].yaxis.set_major_formatter(fmt)
        axes[2, col].legend(fontsize=8)
        for i, b in enumerate(allbins):
            axes[2, col].annotate(f"n={b['prints']:,}", (i, b['payout_notional']), xytext=(0, 4), textcoords='offset points', ha='center', fontsize=7)
        axes[2, col].margins(y=.18)
        for ax in axes[:, col]:
            ax.axhline(0, color='#777777', lw=.7)
            ax.grid(axis='y', alpha=.2)
            ax.set_xticks(x, LABELS)
        axes[2, col].set_xlabel('Sum of underlying leg spreads (cents) · bucket widths differ')
    kind = 'Raw opposite-team ask spreads' if measure == 'raw_width_sum_cents' else 'Fee-expanded opposite-team spreads'
    fig.suptitle(f'{kind} · unfiltered seller profitability', fontsize=15)
    fig.text(.055, .025,
             'Top: size-weighted outcome P&L = 100 × sum(net dollar P&L) / sum(payout contracts with known outcomes). Maker fees included.\n'
             'All covered 2–4 distinct-game pregame moneylines; no edge/capital filters. Hollow points: <30 known prints; descriptive buckets, not a fitted rule.\n'
             'Middle is ordered by spread, not time. Bottom shows exposure support; sparse tails and repeated fixture outcomes limit inference.\n'
             'CFB: retained week, incomplete outside Saturday. MLB: September 5 census. Existing historical fee assumptions retained; no depth proxy.', fontsize=9)
    fig.tight_layout(rect=(0, .115, 1, .95))
    for ext in ('png', 'svg'):
        fig.savefig(out/(measure+'.'+ext), dpi=160)
    plt.close(fig)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input', type=Path, default=ROOT/'runs/opposite_moneyline_20260907')
    p.add_argument('--out', type=Path, default=ROOT/'runs/spread_profitability_20260907')
    args = p.parse_args(); args.out.mkdir(parents=True, exist_ok=True)
    results, hashes = {}, {}
    for sport in ('cfb', 'mlb'):
        rows, source_hashes = inputs(args.input, sport); hashes.update(source_hashes)
        result = {'overall': aggregate(rows)}
        for measure in ('raw_width_sum_cents', 'fee_width_sum_cents'):
            bins = defaultdict(list)
            for r in rows:
                bins[bucket(r[measure])].append(r)
            result[measure] = {n: [aggregate([r for r in bins[i] if n=='all' or r['nlegs']==int(n)]) for i in range(len(EDGES))]
                               for n in ('all', '2', '3', '4')}
            result[measure]['cumulative'] = [aggregate([r for j in range(i+1) for r in bins[j]]) for i in range(len(EDGES))]
            if sum(b['prints'] for b in result[measure]['all']) != len(rows):
                raise ValueError('bucket_partition_does_not_reconcile')
        results[sport] = result
    (args.out/'summary.json').write_text(json.dumps(results, indent=2, allow_nan=False)+'\n')
    (args.out/'manifest.json').write_text(json.dumps({'input_sha256': hashes,
        'code_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'bin_left_edges_cents': EDGES, 'bin_labels': LABELS, 'weight': 'payout_contract_quantity',
        'scope': 'Entire prior paired-moneyline population, no model/quote/edge/risk filters; cross-source duplicates removed by selecting the single Kalshi record per print.',
        'unknowns': 'Exclude from known ratio numerator AND denominator; retain notional and final PnL bounds.',
        'spread': 'Sum of leg-level opposite-team bands; descriptive uncertainty proxy, not executable combo spread.',
        'orders_enabled': False}, indent=2)+'\n')
    for measure in ('raw_width_sum_cents', 'fee_width_sum_cents'):
        plot(results, args.out, measure)
    print(json.dumps({sport: result['overall'] for sport, result in results.items()}, indent=2))


if __name__ == '__main__':
    main()

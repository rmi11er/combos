"""Descriptive historical trade premium versus native Kalshi leg bid/ask widths.

Run from the repository root with .venv/bin/python. Only retained pricing
contexts are read; no exchange requests, outcome selection, or policy changes.
"""
import argparse
from collections import Counter
from datetime import datetime
import gzip
import hashlib
import json
import math
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]


def extract(folder, sport):
    paths = [folder/'opportunities.json', folder/'pricing_context.jsonl.gz']
    hashes = {}
    for path in paths:
        with path.open('rb') as f:
            hashes[str(path.relative_to(ROOT))] = hashlib.file_digest(f, 'sha256').hexdigest()
    with paths[0].open() as f:
        data = json.load(f)
    selected = [r for r in data['opportunities'] if r['model'] == 'kalshi']
    trades = {r['evaluation_id']: r for r in selected}
    assert len(selected) == len(trades), 'duplicate Kalshi trade identity'
    del data, selected
    rows, counts, seen = [], Counter(), set()
    with gzip.open(paths[1], 'rt') as f:
        for line in f:
            ctx = json.loads(line)
            key = ctx['evaluation_id']
            assert key not in seen, 'duplicate context identity'
            seen.add(key)
            r = trades.get(key)
            if r is None:
                counts['context_without_kalshi_trade'] += 1
                continue
            counts['joined'] += 1
            legs = ctx['legs']
            if not 2 <= len(legs) <= 4 or any(not l['market_ticker'].startswith('KX'+sport+'GAME-') for l in legs):
                counts['outside_moneyline_2_4'] += 1
                continue
            fixtures = {l['event_ticker'] for l in legs}
            if len(fixtures) != len(legs):
                counts['same_fixture'] += 1
                continue
            sources = ctx.get('sources', ctx.get('context'))
            assert len(sources) == len(legs)
            bids, asks, ages = [], [], []
            for leg, source in zip(legs, sources):
                k = source['kalshi']
                if 'ticker' in source:
                    assert source['ticker'] == leg['market_ticker']
                bid, ask = float(k['yes_bid']), float(k['yes_ask'])
                assert 0 <= bid <= ask <= 1
                assert float(k['available_at']) <= r['at']
                assert math.isclose(ctx['at'], r['at'], abs_tol=1e-5)
                if leg['side'] == 'no':
                    bid, ask = 1-ask, 1-bid
                else:
                    assert leg['side'] == 'yes'
                bids.append(bid); asks.append(ask)
                ages.append(r['at']-float(k['source_at']))
            mids = [(a+b)/2 for a,b in zip(asks,bids)]
            fair = math.prod(mids)
            assert math.isclose(fair, r['fair_point'], abs_tol=1e-8), 'native midpoint product mismatch'
            hours = (r['source']['start_at']-r['at'])/3600
            if hours <= 0:
                counts['not_pregame'] += 1
                continue
            rows.append(dict(id=key, sport=sport,
                day=datetime.fromtimestamp(r['at'], ZoneInfo('America/Chicago')).date().isoformat(),
                quantity=r['quantity'], price=r['yes_price'], mid=fair, nlegs=len(legs),
                edge=100*(r['yes_price']-fair),
                sum_width=100*sum(a-b for a,b in zip(asks,bids)),
                propagated=100*(math.prod(asks)-fair),
                max_age=max(ages), hours=hours, fixtures='|'.join(sorted(fixtures))))
    counts['included'] = len(rows)
    counts['trades_without_context'] = len(set(trades)-seen)
    return rows, dict(counts), hashes


def regression(frame, width, weighted, adjusted):
    w = frame.quantity.to_numpy() if weighted else np.ones(len(frame))
    x = frame[width].to_numpy()
    y = frame.edge.to_numpy()
    cols = [np.ones(len(frame))]
    if adjusted:
        p = frame.mid.to_numpy()
        cols += [p, p*p, p*p*p, np.log1p(frame.hours), np.log1p(frame.max_age), np.log1p(frame.quantity)]
        for key in ('nlegs', 'day'):
            for value in sorted(frame[key].unique())[1:]:
                cols.append((frame[key] == value).to_numpy().astype(float))
    controls = np.column_stack(cols)
    sw = np.sqrt(w/w.mean())
    # Residualize both variables on controls: the coefficient and partial R²
    # equal the full regression with the spread column added.
    targets = np.column_stack([x,y])
    coef = np.linalg.lstsq(controls*sw[:,None], targets*sw[:,None], rcond=None)[0]
    residual = targets-controls@coef
    rx, ry = residual.T
    xx, yy, xy = np.sum(w*rx*rx), np.sum(w*ry*ry), np.sum(w*rx*ry)
    slope = xy/xx if xx > 1e-12 else None
    corr = xy/math.sqrt(xx*yy) if xx*yy > 1e-12 else None
    return {'slope': slope, 'partial_correlation' if adjusted else 'correlation': corr,
            'incremental_partial_r2' if adjusted else 'r2': corr*corr if corr is not None else None}, rx, ry


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args(); args.out.mkdir(parents=True, exist_ok=True)
    jobs = [('NFL', ROOT/'runs/nfl_moneyline_replay_20260907/jan5_18')]
    jobs += [('MLB', p) for p in sorted((ROOT/'runs/mlb_historical_20260907/dated_fee_primary').glob('2026-07-*/replay'))]
    rows, coverage, hashes = [], {}, {}
    for sport, folder in jobs:
        rs, cs, hs = extract(folder, sport)
        rows.extend(rs); coverage[str(folder.relative_to(ROOT))] = cs; hashes.update(hs)
        print(sport, folder.parent.name, cs, flush=True)
    df = pd.DataFrame(rows)
    assert not df.duplicated(['sport','id']).any()
    df.to_csv(args.out/'observations.csv.gz', index=False, compression='gzip')
    report = {'definition': '100 * (combo YES trade price - product of selected-leg native Kalshi mids), before fees',
        'scope': 'Retained priceable 2–4-leg distinct-fixture pregame moneyline YES-taker prints; July MLB and January NFL',
        'controls': 'Cubic midpoint product, categorical leg count and trade date, log1p hours to first game, maximum leg age, quantity. No traded-price control.',
        'limitations': ['Prior candle books with archived 60-second publication-delay convention; not tick-synchronous executable books.',
                       'Product of mids assumes distinct-game independence.',
                       'Replay coverage requires external price availability; not all native combo trades.',
                       'Equal-print and contract-weighted descriptive association; overlapping fixtures invalidate IID significance.',
                       'Leave-one-day-out ranges are sensitivity ranges, not confidence intervals.',
                       'July 13 and unsaved July dates absent. August held-out data not used.'],
        'coverage': coverage, 'hashes': hashes, 'results': {}}
    fig, axes = plt.subplots(2, 2, figsize=(12,8), layout='constrained')
    for i, sport in enumerate(['MLB','NFL']):
        f = df[df.sport == sport].copy()
        result = {'prints':len(f), 'days':sorted(f.day.unique()), 'fixtures':len(set('|'.join(f.fixtures).split('|'))),
                  'contracts':float(f.quantity.sum()), 'regressions':[], 'daily':[]}
        for width in ['sum_width','propagated']:
            for weighted in [False,True]:
                for adjusted in [False,True]:
                    fit, rx, ry = regression(f,width,weighted,adjusted)
                    entry = dict(width=width, weighting='contracts' if weighted else 'prints', adjusted=adjusted, **fit)
                    slopes = [regression(f[f.day != day],width,weighted,adjusted)[0]['slope'] for day in f.day.unique()]
                    entry['leave_day_out_slope_range'] = [min(s for s in slopes if s is not None),max(s for s in slopes if s is not None)]
                    result['regressions'].append(entry)
        for day, part in f.groupby('day'):
            result['daily'].append(dict(day=day, prints=len(part), **regression(part,'sum_width',True,False)[0]))
        for j, adjusted in enumerate([False, True]):
            fit, rx, ry = regression(f,'sum_width',True,adjusted)
            b = pd.DataFrame({'x':rx,'y':ry,'w':f.quantity.to_numpy()})
            b['bin'] = pd.qcut(b.x, 10, duplicates='drop')
            bins = []
            for _, part in b.groupby('bin', observed=True):
                bins.append({'x':float(np.average(part.x,weights=part.w)), 'y':float(np.average(part.y,weights=part.w)), 'prints':len(part)})
            ax=axes[i,j]
            ax.scatter([r['x'] for r in bins],[r['y'] for r in bins],s=[25+80*r['prints']/len(f) for r in bins])
            lim=np.array([b.x.min(), b.x.max()])
            ax.plot(lim,lim*fit['slope'],alpha=.6)
            ax.axhline(0,color='gray',linewidth=.7)
            ax.set_title(f'{sport} · '+('adjusted' if adjusted else 'unadjusted')+f' · slope {fit["slope"]:.3f}')
            ax.set_xlabel('Residual summed leg spread (¢)' if adjusted else 'Centered summed leg spread (¢)')
            ax.set_ylabel('Residual combo premium (¢)' if adjusted else 'Centered combo premium (¢)')
            result['adjusted_bins' if adjusted else 'unadjusted_bins'] = bins
        report['results'][sport] = result
    fig.suptitle('Combo trade premium versus native leg spreads\nContract-weighted bins; prior candle mids; positive premium benefits YES sellers')
    fig.savefig(args.out/'association.png',dpi=170)
    (args.out/'results.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(json.dumps(report['results'],indent=2),flush=True)


if __name__ == '__main__':
    main()

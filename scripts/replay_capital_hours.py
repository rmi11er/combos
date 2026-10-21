#!/usr/bin/env python3
"""Measure historical cash occupancy from a replay ledger, without repricing."""
import argparse
import gzip
import hashlib
import json
import math
from pathlib import Path


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1048576), b''):
            h.update(block)
    return h.hexdigest()


def measure(ledger):
    results = []
    for summary in ledger['summaries']:
        model = summary['model']
        rows = [r for r in ledger['curves'] if r['model'] == model]
        if len(rows) < 2:
            raise ValueError('missing reporting endpoints')
        start, end = rows[0]['at'], rows[-1]['at']
        if end <= start:
            raise ValueError('invalid reporting window')
        area = 0.
        for left, right in zip(rows, rows[1:]):
            if right['at'] <= left['at']:
                raise ValueError('curve timestamps must strictly increase per model')
            cash = left['committed_cash']
            if not math.isfinite(cash) or cash < -1e-7:
                raise ValueError('invalid committed cash')
            area += max(0., cash) * (right['at'] - left['at']) / 3600
        fill_area = 0.
        for fill in ledger['fills']:
            if fill['model'] != model:
                continue
            at = fill['filled_at']
            settled = fill.get('settled_at')
            if not start <= at <= end or (settled is not None and settled < at):
                raise ValueError('invalid fill times')
            stop = min(end, settled) if settled is not None else end
            cost = fill['quantity'] * (1 - fill['yes_price']) + fill['maker_fee']
            fill_area += cost * (stop - at) / 3600
        if not math.isclose(area, fill_area, rel_tol=1e-10, abs_tol=1e-6):
            raise ValueError('curve/fill capital-hours mismatch')
        hours = (end - start) / 3600
        pnl = summary['trade_attributed_pnl']
        complete = not summary.get('open_fills', 0) and not summary.get('unresolved_outcomes', 0)
        results.append(dict(model=model, start_at=start, end_at=end,
            reporting_hours=hours, committed_dollar_hours=area,
            independent_fill_dollar_hours=fill_area, average_committed_cash=area/hours,
            peak_committed_cash=summary['peak_committed_cash'],
            trade_attributed_net_pnl=pnl, capital_cycle_complete=complete,
            net_pnl_per_1000_committed_dollar_hours=(1000*pnl/area if area and complete else None),
            ratio_unavailable_reason=None if area and complete else 'zero exposure or incomplete capital cycle'))
    return results


def run(source, out):
    if out.exists():
        raise ValueError('use a new output path')
    before = digest(source)
    with gzip.open(source, 'rt') as f:
        ledger = json.load(f)
    result = dict(source=str(source.resolve()), source_sha256=before,
                  script_sha256=digest(__file__), results=measure(ledger),
                  interpretation='Descriptive occupied-cash efficiency, not an annualized return or RFQ fill forecast. Includes maker fee in cash cost, matching replay accounting. Integrates all elapsed hours, including overnight; unknown future occupancy is not extrapolated. Eventual P&L ratio withheld for incomplete capital cycles.')
    if digest(source) != before:
        raise ValueError('source changed')
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open('x') as f:
        json.dump(result, f, indent=2)
        f.write('\n')
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--ledger', required=True, type=Path)
    p.add_argument('--out', required=True, type=Path)
    args = p.parse_args()
    run(args.ledger, args.out)

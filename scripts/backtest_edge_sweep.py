#!/usr/bin/env python3
"""In-sample entry-threshold diagnostics at observed prices, never synthetic quotes."""
import argparse
import csv
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from combos.backtest import BacktestConfig, run_backtest


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input', required=True, type=Path)
    p.add_argument('--config', required=True, type=Path)
    p.add_argument('--out', required=True, type=Path)
    p.add_argument('--net-edge-cents', type=float, nargs='+', default=[.3, 1., 2., 5.])
    args = p.parse_args()
    data = json.loads(args.input.read_text())
    base = BacktestConfig(**json.loads(args.config.read_text()))
    identity = {'input_sha256': hashlib.sha256(args.input.read_bytes()).hexdigest(),
                'config_sha256': hashlib.sha256(args.config.read_bytes()).hexdigest(),
                'net_edge_cents': args.net_edge_cents,
                'interpretation': 'In-sample sensitivity at observed executions; not quote acceptance or held-out tuning.'}
    args.out.mkdir(parents=True, exist_ok=True)
    path = args.out/'manifest.json'
    if path.exists() and json.loads(path.read_text())['experiment'] != identity:
        raise ValueError('experiment differs; choose a new output directory')
    results = []
    for cents in args.net_edge_cents:
        config = replace(base, minimum_net_edge_per_share=cents/100)
        for constrained in (True, False):
            result = run_backtest(data['opportunities'], data['start_at'], data['end_at'], config, constrained)
            for s in result['summaries']:
                results.append({'net_edge_cents': cents, 'regime': 'constrained' if constrained else 'unconstrained', **s})
            print(json.dumps({'net_edge_cents': cents, 'constrained': constrained,
                              'models': [{k:s[k] for k in ('model','fills','trade_attributed_pnl')} for s in result['summaries']]}), flush=True)
    (args.out/'summary.json').write_text(json.dumps(results, indent=2, allow_nan=False)+'\n')
    with (args.out/'summary.csv').open('w') as f:
        fields = ['net_edge_cents','regime','model','evaluations','fills','accepted_point_edge',
                  'trade_attributed_pnl','unresolved_outcomes','peak_committed_cash','annualized_sharpe']
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore'); writer.writeheader(); writer.writerows(results)
    files = [Path(__file__), ROOT/'src/combos/backtest.py', ROOT/'src/combos/risk.py',
             ROOT/'src/combos/performance.py', ROOT/'src/combos/event_store.py']
    path.write_text(json.dumps({'experiment': identity, 'code_sha256': {
        str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}}, indent=2)+'\n')


if __name__ == '__main__':
    main()

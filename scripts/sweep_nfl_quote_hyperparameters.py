#!/usr/bin/env python3
"""Replay NFL RFQs over edge/risk policy candidates without submitting orders."""
import argparse
import hashlib
import json
import time
from collections import Counter
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from combos.event_store import EventStore
from combos.rfq_scenario_consumer import RFQScenarioConsumer
from combos.research_quote_consumer import ResearchQuoteConsumer
from combos.weighted_fair import WeightPolicy


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def replay(capture, runtime, catalog, weights, edge, cap):
    pricing = RFQScenarioConsumer(runtime, catalog, WeightPolicy(**weights))
    policy = {
        'reserve_fraction': 0,
        'edge_per_combo': edge,
        'native_stake_usd_scale': 1,
        'capacity_mode': 'all_admitted_fill_no_release',
        'capital_dollars': 10000,
        'caps': {'contract': cap, 'combo': cap, 'fixture': cap},
    }
    consumer = ResearchQuoteConsumer(pricing, runtime, policy)
    counts = Counter(); seq = 0; rfqs = 0
    store = EventStore(capture / 'events.sqlite')
    try:
        while True:
            events = store.read(seq, 1000)
            if not events:
                break
            for event in events:
                seq = event['seq']
                row = consumer.consume(event)
                if row is None:
                    continue
                rfqs += 1
                pricing_status = row.get('status', 'unknown')
                counts['pricing:' + pricing_status] += 1
                policy_row = row.get('research_policy') or {}
                counts[policy_row.get('reason', policy_row.get('status', 'policy_unknown'))] += 1
    finally:
        store.close()
    return {
        'edge_per_combo': edge,
        'cap_dollars': cap,
        'rfqs_with_decisions': rfqs,
        'counts': dict(counts),
        'scenario_priced': counts['pricing:scenario_priced'],
        'reserved': counts['reserved_scenario'],
        'risk_rejected': counts['risk_rejected'],
        'peak_reserved_dollars': consumer.risk.peak / 10000,
        'last_seq': seq,
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--capture', type=Path, required=True)
    p.add_argument('--runtime', type=Path, required=True)
    p.add_argument('--catalog', type=Path, required=True)
    p.add_argument('--weights', type=Path, default=None)
    p.add_argument('--out', type=Path, required=True)
    args = p.parse_args()
    if args.out.exists():
        raise SystemExit(f'output_exists: {args.out}')
    runtime = json.loads(args.runtime.read_text())
    catalog = json.loads(args.catalog.read_text())
    weights_path = args.weights or (args.capture / 'weighting.json')
    weights = json.loads(Path(weights_path).read_text())
    args.out.mkdir(parents=True)
    started = time.time()
    reports = []
    for edge in (.001, .003, .005):
        for cap in (250, 500, 1000):
            report = replay(args.capture, runtime, catalog, weights, edge, cap)
            reports.append(report)
            print(json.dumps(report), flush=True)
    summary = {
        'runtime': str(args.runtime),
        'capture': str(args.capture),
        'input_hashes': {str(p): digest(p) for p in (args.runtime, args.catalog, Path(weights_path))},
        'reports': reports,
        'elapsed_seconds': time.time() - started,
        'orders_enabled': False,
        'interpretation': 'Observed RFQ replay; no customer acceptance, fill selection, or settlement PnL.',
    }
    (args.out / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')


if __name__ == '__main__':
    main()

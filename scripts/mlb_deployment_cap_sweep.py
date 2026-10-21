"""Continuous July candidate portfolios with a fixed outstanding-cash ceiling."""
import argparse
from dataclasses import dataclass, asdict, replace
import json
from pathlib import Path
import sqlite3
import time
from combos.backtest import BacktestConfig
from combos.deployment_risk import DeploymentCappedRiskLedger
from mlb_disk_index import file_digest, iter_model
from mlb_streaming_longitudinal import evaluate_one
from run_mlb_streaming_snapshot import atomic, source_hashes


@dataclass(frozen=True)
class DeploymentConfig(BacktestConfig):
    maximum_committed_dollars: float = 10000.


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--index', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    with sqlite3.connect(a.index.resolve().as_uri() + '?mode=ro', uri=True) as db:
        meta = {k: json.loads(v) for k, v in db.execute('SELECT key,value FROM metadata')}
    plan, coverage = meta['plan'], meta['coverage']
    assert set(plan['dates'].values()) == {'development'}
    assert len(coverage['observed_dates']) == 15
    assert {v['date'] if isinstance(v, dict) else v for v in coverage['missing_dates']} == {'2026-07-13'}
    base = DeploymentConfig(entry_basis='point', minimum_net_edge_per_share=.003,
                            timezone=plan['timezone'], **plan['baseline_limits'])
    scenarios = [('balanced1000', replace(base, per_contract_dollars=1000, per_combo_dollars=1000, per_fixture_dollars=1000)),
                 ('fixture2000', replace(base, per_contract_dollars=10000, per_combo_dollars=10000, per_fixture_dollars=2000))]
    a.out.mkdir(parents=True, exist_ok=False)
    hashes, index_hash, began = source_hashes(), file_digest(a.index), time.time()
    atomic(a.out/'started.json', {'source_hashes': hashes, 'index_sha256': index_hash,
        'index': str(a.index.resolve()), 'scenarios': {k: asdict(c) for k, c in scenarios},
        'started_at': began, 'funding': '$10k initial capital; fixed $10k outstanding reservations/fills ceiling; only actual settlements release funds.'})
    records = []
    for model in plan['primary_models']:
        for name, config in scenarios:
            print('running', model, name, flush=True)
            record, _ = evaluate_one(iter_model(a.index, model), model, name, name,
                config, True, coverage, plan, a.out/(model+'__'+name), artifact_codec='zstd',
                ledger_factory=DeploymentCappedRiskLedger)
            assert record['portfolio']['peak_committed_cash'] <= 10000.01
            records.append(record)
            atomic(a.out/'progress.json', {'records': records})
            print('complete', model, name, record['portfolio']['trade_attributed_pnl'], flush=True)
    assert hashes == source_hashes() and index_hash == file_digest(a.index)
    atomic(a.out/'summary.json', {'records': records, 'coverage': coverage,
        'source_hashes': hashes, 'index_sha256': index_hash, 'elapsed_seconds': time.time()-began})
    atomic(a.out/'complete.json', {'portfolios': len(records), 'summary_sha256': file_digest(a.out/'summary.json'),
                                 'independent_admission_audit': 'pending'})


if __name__ == '__main__':
    main()

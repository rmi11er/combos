"""Compare explicit marginal-reserve fractions on one certified July cohort."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sqlite3
import time
from combos.deployment_risk import DeploymentCappedRiskLedger
from mlb_deployment_cap_sweep import DeploymentConfig
from mlb_disk_index import file_digest, iter_model
from mlb_streaming_longitudinal import evaluate_one
from run_mlb_streaming_snapshot import atomic, source_hashes


def with_reserve(rows, feature_db, model, fraction, reference):
    if not 0 <= fraction <= 1:
        raise ValueError('reserve_fraction_out_of_range')
    for row in rows:
        value = feature_db.execute('SELECT point,independent_upper FROM features WHERE evaluation_id=? AND model=?',
                                   (row['evaluation_id'], model)).fetchone()
        if value is None or abs(value[0]-row['fair_point']) > 1e-9:
            raise ValueError('missing_or_mismatched_causal_feature')
        upper = row['fair_point']+fraction*(value[1]-row['fair_point'])
        if not row['fair_point']-1e-9 <= upper <= row['stressed_upper']+1e-9:
            raise ValueError('reserve_outside_recorded_bounds')
        yield {**row, 'stressed_upper': max(row['fair_point'], upper),
               'source': {**row['source'], 'quote_reserve_candidate': {
                   'fraction': fraction, 'original_joint_upper': row['stressed_upper'],
                   'independent_marginal_upper': value[1], 'feature_reference': reference,
                   'assumption': 'independent leg payoff reference; partial reserve is a pricing-policy hypothesis, not a probability confidence bound'}}}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--index', type=Path, required=True)
    p.add_argument('--features', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    feature_cert = json.loads((a.features/'complete.json').read_text())
    index_hash, feature_hash = file_digest(a.index), file_digest(a.features/'features.sqlite')
    assert feature_cert['complete'] and feature_cert['index_sha256'] == index_hash
    assert feature_hash == feature_cert['database_sha256']
    with sqlite3.connect(a.index.resolve().as_uri()+'?mode=ro', uri=True) as db:
        meta = {k: json.loads(v) for k, v in db.execute('SELECT key,value FROM metadata')}
    plan, coverage = meta['plan'], meta['coverage']
    assert set(plan['dates'].values()) == {'development'}
    config = DeploymentConfig(entry_basis='stressed_upper', minimum_net_edge_per_share=.003,
        timezone=plan['timezone'], capital_dollars=10000, maximum_committed_dollars=10000,
        per_contract_dollars=1000, per_combo_dollars=1000, per_fixture_dollars=1000)
    fractions = [0., .25, 1.]
    a.out.mkdir(parents=True, exist_ok=False)
    hashes, began = source_hashes(), time.time()
    atomic(a.out/'started.json', {'source_hashes': hashes, 'index_sha256': index_hash,
        'feature_database_sha256': feature_hash, 'feature_certificate_sha256': file_digest(a.features/'complete.json'),
        'fractions': fractions, 'configuration': asdict(config), 'started_at': began,
        'scope': 'Development comparison only; no August outcomes. Hypothetical public-print prices/sizes, no execution model. Unlimited variants ignore funding/risk limits.'})
    feature_db = sqlite3.connect((a.features/'features.sqlite').resolve().as_uri()+'?mode=ro', uri=True)
    feature_db.execute('PRAGMA cache_size=-32768')
    records = []
    for model in plan['primary_models']:
        for fraction in fractions:
            name = 'marginal_'+str(fraction).replace('.', '_')
            for constrained in (True, False):
                regime = 'funded' if constrained else 'unlimited'
                print('running', model, fraction, regime, flush=True)
                rows = with_reserve(iter_model(a.index, model), feature_db, model, fraction, 'sha256:'+feature_hash)
                r, _ = evaluate_one(rows, model, name, name, config, constrained, coverage, plan,
                    a.out/(model+'__'+name+'__'+regime), artifact_codec='zstd', ledger_factory=DeploymentCappedRiskLedger)
                r['marginal_reserve_fraction'] = fraction
                records.append(r)
                atomic(a.out/'progress.json', {'records': records})
                print('complete', model, fraction, regime, r['portfolio']['trade_attributed_pnl'], flush=True)
    feature_db.close()
    assert hashes == source_hashes() and index_hash == file_digest(a.index) and feature_hash == file_digest(a.features/'features.sqlite')
    atomic(a.out/'summary.json', {'records': records, 'coverage': coverage, 'source_hashes': hashes,
        'index_sha256': index_hash, 'feature_database_sha256': feature_hash, 'elapsed_seconds': time.time()-began})
    atomic(a.out/'complete.json', {'portfolios': len(records), 'summary_sha256': file_digest(a.out/'summary.json'),
                                 'independent_policy_and_admission_audit': 'pending'})


if __name__ == '__main__':
    main()

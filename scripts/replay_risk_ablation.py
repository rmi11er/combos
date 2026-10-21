#!/usr/bin/env python3
"""Fixed one-factor risk experiments on a retained common-cohort replay.

Research only: preserve causal fair values, observed prices/full quantities and
actual settlement funding. No live configuration or outcome-based optimization.
"""
import argparse
from dataclasses import asdict, replace
import gzip
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from combos.backtest import BacktestConfig, run_backtest
from mlb_risk_capacity import exposure_audit
from replay_artifact_io import text_writer

FIELDS = ('evaluation_id', 'at', 'quantity', 'yes_price', 'maker_fee',
          'settled_at', 'yes_settlement', 'buckets', 'quote_allowed',
          'risk_multiplier', 'source', 'model', 'fair_point', 'stressed_upper')
PAIRED = ('at', 'quantity', 'yes_price', 'maker_fee', 'settled_at',
          'yes_settlement', 'buckets', 'source')


def scenarios(base):
    """Isolate each cap; repeat fixture tests with the other caps relaxed."""
    yield 'baseline', base
    for cap in (100, 250, 500, 1000, 2000):
        yield f'fixture_{cap}_baseline_others', replace(base, per_fixture_dollars=cap)
        yield f'fixture_{cap}_relaxed_others', replace(
            base, per_fixture_dollars=cap, per_contract_dollars=10000,
            per_combo_dollars=10000)
    for cap in (50, 100, 250, 500, 1000):
        yield f'underlying_{cap}_baseline_others', replace(base, per_contract_dollars=cap)
        yield f'underlying_{cap}_relaxed_others', replace(
            base, per_contract_dollars=cap, per_combo_dollars=10000,
            per_fixture_dollars=10000)


def opportunities(ledger):
    if ledger['constrained']:
        raise ValueError('requires_unlimited_input_to_avoid_inventory_selection')
    rows = [{k: r[k] for k in FIELDS} for r in ledger['decisions']]
    by_model = {}
    for row in rows:
        if row['source'].get('sampling_method') != 'census':
            raise ValueError('requires_census_input')
        group = by_model.setdefault(row['model'], {})
        if row['evaluation_id'] in group:
            raise ValueError('duplicate_model_evaluation')
        group[row['evaluation_id']] = row
    if len(by_model) < 2:
        raise ValueError('requires_multiple_paired_models')
    reference = next(iter(by_model.values()))
    for group in by_model.values():
        if group.keys() != reference.keys():
            raise ValueError('incomplete_common_cohort')
        for key, row in group.items():
            if any(row[field] != reference[key][field] for field in PAIRED):
                raise ValueError('inconsistent_paired_economics')
    return rows


def digest(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def read(path):
    opener = gzip.open if str(path).endswith('.gz') else open
    with opener(path, 'rt') as f:
        return json.load(f)


def save(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')


def concentration(decisions):
    known = [r for r in decisions if r['accepted'] and r['yes_settlement'] is not None]
    def pnl(r):
        return r['quantity']*(r['yes_price']-r['yes_settlement'])-r['maker_fee']
    largest = max(known, key=pnl) if known else None
    fixtures = sorted({f for r in known for f in r['buckets']['fixture']})
    return {'largest_winning_print': None if largest is None else {
                'evaluation_id': largest['evaluation_id'], 'quantity': largest['quantity'],
                'net_pnl': pnl(largest), 'yes_price': largest['yes_price'],
                'fixtures': largest['buckets']['fixture']},
            'pnl_without_largest_print': sum(map(pnl, known))-(pnl(largest) if largest else 0),
            'fixture_omission_pnl': {f: sum(pnl(r) for r in known if f not in r['buckets']['fixture'])
                                     for f in fixtures},
            'interpretation': 'Descriptive omissions of selected prints; funded portfolio is not reallocated after omission.'}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--ledger', type=Path, required=True)
    p.add_argument('--study-summary', type=Path, required=True)
    p.add_argument('--baseline-ledger', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    # Require a new output path; retain interrupted experiments for diagnosis.
    a.out.mkdir(parents=True, exist_ok=False)
    inputs = {str(x.resolve()): digest(x) for x in
              (a.ledger, a.study_summary, a.baseline_ledger)}
    study, ledger, baseline = read(a.study_summary), read(a.ledger), read(a.baseline_ledger)
    rows = opportunities(ledger)
    config = BacktestConfig(**ledger['configuration'])
    if config != BacktestConfig(**baseline['configuration']) or not baseline['constrained']:
        raise ValueError('baseline_configuration_mismatch')
    start, end = study['start_at'], study['end_at']
    code = {str(Path(m.__file__).resolve()): digest(m.__file__)
            for m in list(sys.modules.values()) if getattr(m, '__file__', None)
            and (Path(m.__file__).resolve().is_relative_to(ROOT/'src')
                 or Path(m.__file__).resolve().is_relative_to(ROOT/'scripts'))
            and str(m.__file__).endswith('.py')}
    grid = list(scenarios(config))
    save(a.out/'started.json', {'inputs': inputs, 'code': code,
         'scenarios': {name: asdict(c) for name, c in grid},
         'start_at': start, 'end_at': end, 'live_policy_changed': False,
         'interpretation': 'Exploratory existing historical data; full observed print size, no acceptance model. No partial sizing in this experiment. Fees and source assumptions inherited.'})
    summaries = []
    for name, c in grid:
        result = run_backtest(rows, start, end, c, constrained=True)
        # The NFL archive appends this diagnostic after the core replay.
        # Reproduce it as well instead of discarding fields during parity checks.
        if all('concentration' in s for s in baseline['summaries']):
            for s in result['summaries']:
                s['concentration'] = concentration(
                    [r for r in result['decisions'] if r['model'] == s['model']])
        if name == 'baseline':
            for field in ('summaries', 'decisions', 'fills', 'curves', 'daily'):
                if result[field] != baseline[field]:
                    raise ValueError('baseline_reproduction_failed:'+field)
        for s in result['summaries']:
            audit = exposure_audit([r for r in result['decisions'] if r['model']==s['model']], c)
            summaries.append({**s, 'scenario': name, 'configuration': asdict(c), **audit})
        for field in ('decisions', 'fills', 'curves', 'daily'):
            with text_writer(a.out/f'{name}.{field}.jsonl.zst') as f:
                for row in result[field]:
                    f.write(json.dumps(row, allow_nan=False)+'\n')
        print(json.dumps({'scenario': name, 'models': len(result['summaries']),
                          'baseline_exact': name == 'baseline'}), flush=True)
    for path, h in {**inputs, **code}.items():
        if digest(path) != h:
            raise RuntimeError('source_changed_during_experiment:'+path)
    save(a.out/'summary.json', summaries)
    hashes = {x.name: digest(x) for x in a.out.iterdir() if x.is_file()}
    save(a.out/'complete.json', {'baseline_exact': True, 'independent_risk_audits': True,
         'scenario_count': len(grid), 'portfolios': len(summaries), 'outputs': hashes})


if __name__ == '__main__':
    main()

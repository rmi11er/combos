#!/usr/bin/env python3
"""Audit source disagreement on a retained continuous replay, without changing it."""
import argparse
import hashlib
import json
from pathlib import Path
from model_disagreement_report import pair_rows, summarize, metrics
from replay_artifact_io import text_reader


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for part in iter(lambda: f.read(1024 * 1024), b''):
            h.update(part)
    return h.hexdigest()


def analyze(version, variant):
    summary_path = version / 'summary.json'
    summary = json.loads(summary_path.read_text())
    records = [r for r in summary['records'] if r['model'] in ('kalshi', 'polymarket')
               and r['regime'] == 'unlimited' and r['variant'] == variant]
    if len(records) != 2 or {r['model'] for r in records} != {'kalshi', 'polymarket'}:
        raise ValueError('requires_two_unlimited_source_records')
    if records[0]['configuration'] != records[1]['configuration']:
        raise ValueError('inconsistent_source_policies')
    codec = summary.get('artifact_codec', {'name': 'gzip'})['name']
    if codec not in ('gzip', 'zstd'):
        raise ValueError('unsupported_artifact_codec')
    suffix = 'gz' if codec == 'gzip' else 'zst'
    paths = [version / f'{model}__{variant}__unlimited.decisions.jsonl.{suffix}'
             for model in ('kalshi', 'polymarket')]
    before = {str(p.resolve()): digest(p) for p in [summary_path, *paths]}
    def rows():
        for path in paths:
            with text_reader(path) as f:
                for line in f:
                    yield json.loads(line)
    pairs, counts = pair_rows(rows())
    if not pairs or counts['kalshi'] != len(pairs) or counts['polymarket'] != len(pairs):
        raise ValueError('expected_complete_common_source_cohort')
    result = summarize(pairs)
    result['selection_fixture_sensitivity'] = {}
    for name, chosen in (
        ('polymarket_only', [(k,p) for k,p in pairs if p['accepted'] and not k['accepted']]),
        ('kalshi_only', [(k,p) for k,p in pairs if k['accepted'] and not p['accepted']]),
    ):
        fixtures = sorted({f for k,p in chosen for f in k['buckets']['fixture']})
        result['selection_fixture_sensitivity'][name] = [
            {'removed_fixture': f, **metrics([(k,p) for k,p in chosen if f not in k['buckets']['fixture']])}
            for f in fixtures]
    after = {str(p.resolve()): digest(p) for p in [summary_path, *paths]}
    if before != after:
        raise ValueError('input_changed_during_analysis')
    result['provenance'] = dict(input_hashes=before, observed_dates=summary['coverage']['observed_dates'],
        missing_dates=summary['coverage']['missing_dates'], configuration=records[0]['configuration'],
        variant=variant, source_counts=counts, script_sha256=digest(Path(__file__)),
        dependency_sha256=digest(Path(__file__).with_name('model_disagreement_report.py')),
        artifact_codec=codec,
        artifact_io_sha256=digest(Path(__file__).with_name('replay_artifact_io.py')))
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--version', type=Path, required=True)
    p.add_argument('--variant', choices=('edge_0_3c', 'edge_0_3c_per_leg'), default='edge_0_3c')
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    result = analyze(a.version, a.variant)
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out/'results.json').write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')
    lines = ['# Longitudinal source disagreement', '',
             'Dates: '+', '.join(result['provenance']['observed_dates'])+'. Variant: '+a.variant+'.', '',
             'Identical common public-print cohort; unlimited price-only selections. Fee scenarios retained. '
             'Combo probability disagreement is not a leg-level sharpness test. Shared fixtures make prints dependent. '
             'Fixture deletions are sensitivity checks, not confidence intervals. No RFQ fill probability is inferred.', '',
             '| Selection | Prints | Net seller P&L | PM minus Kalshi quantity-Brier |',
             '|---|---:|---:|---:|']
    for r in result['groups']:
        if r['dimension'] == 'selection':
            difference = r['pm_minus_kalshi_brier_quantity_weighted']
            score = 'N/A (unresolved)' if difference is None else f'{difference:+.6f}'
            lines.append(f"| {r['value']} | {r['prints']:,} | ${r['known_net_seller_pnl']:,.2f} | {score} |")
    lines += ['', 'Negative Brier difference favors PM on these same known outcomes. Selection P&L alone does not establish calibration or independence. '
              'See results.json for disagreement directions, premium/leg cuts, individual fixture omissions and hashed inputs.']
    (a.out/'REPORT.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps({'out':str(a.out), 'prints':result['all_common']['prints']}))


if __name__ == '__main__':
    main()

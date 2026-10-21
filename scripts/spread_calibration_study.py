#!/usr/bin/env python3
"""Versioned spread/compensation/calibration decomposition and descriptive WLS."""
import argparse
from collections import defaultdict
import csv
import gzip
import hashlib
import json
import math
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
from spread_profitability import bucket, LABELS
COMPONENTS = ('compensation', 'residual', 'realized')


def components(row):
    q, p, fair, fee = (float(row[k]) for k in ('quantity', 'yes_price', 'fair_point', 'maker_fee'))
    if not all(math.isfinite(v) for v in (q, p, fair, fee)) or q <= 0 or not 0 <= p <= 1 or not 0 <= fair <= 1 or fee < 0:
        raise ValueError('invalid_price_quantity_fair_or_fee')
    compensation = 100*(p-fair-fee/q)
    y = row.get('yes_settlement')
    if y is None or row.get('settled_at') is None:
        return {'compensation': compensation, 'residual': None, 'realized': None}
    if not math.isfinite(y) or not 0 <= y <= 1:
        raise ValueError('invalid_outcome')
    residual, realized = 100*(fair-y), 100*(p-y-fee/q)
    if not math.isclose(compensation+residual, realized, abs_tol=1e-9):
        raise ValueError('decomposition_identity_failed')
    return dict(compensation=compensation, residual=residual, realized=realized)


def summarize(rows):
    known = [r for r in rows if r['values']['realized'] is not None]
    q = sum(r['quantity'] for r in rows); kq = sum(r['quantity'] for r in known)
    means = {c: sum(r['quantity']*r['values'][c] for r in known)/kq if kq else None for c in COMPONENTS}
    if kq and not math.isclose(means['compensation']+means['residual'], means['realized'], abs_tol=1e-8):
        raise ValueError('aggregate_identity_failed')
    return {'prints': len(rows), 'known_prints': len(known), 'known_quantity': kq, 'unknown_quantity': q-kq,
            'quantity': q, 'components_cents': means,
            'all_priced_compensation_cents': sum(r['quantity']*r['values']['compensation'] for r in rows)/q if q else None,
            'known_net_pnl': (means['realized']*kq/100) if kq else 0.}


def fit(x, y, w):
    sw = np.sqrt(w / w.mean())
    coefficients, _, rank, _ = np.linalg.lstsq(x*sw[:, None], y*sw[:, None], rcond=None)
    if rank < x.shape[1]:
        return None
    residual = y-x@coefficients
    means = np.average(y, axis=0, weights=w)
    sse = np.sum(w[:, None]*residual**2, axis=0)
    sst = np.sum(w[:, None]*(y-means)**2, axis=0)
    r2 = [float(1-a/b) if b > 1e-20 else None for a, b in zip(sse, sst)]
    return coefficients, r2


def regression(rows, measure, spec):
    rs = [r for r in rows if r['values']['realized'] is not None]
    if not rs:
        return {'status': 'no_known_outcomes'}
    names = ['intercept', 'spread_cents']
    columns = [np.ones(len(rs)), np.array([r[measure] for r in rs])]
    if spec == 'price_and_leg_count':
        names.append('yes_price_per_10c'); columns.append(np.array([10*r['yes_price'] for r in rs]))
        counts = sorted({r['nlegs'] for r in rs})
        for count in counts[1:]:
            names.append(f'legs_{count}_vs_{counts[0]}')
            columns.append(np.array([float(r['nlegs']==count) for r in rs]))
    x = np.column_stack(columns)
    y = np.array([[r['values'][c] for c in COMPONENTS] for r in rs])
    w = np.array([r['quantity'] for r in rs])
    fitted = fit(x, y, w)
    if fitted is None:
        return {'status': 'rank_deficient', 'terms': names}
    coefficients, r2 = fitted
    if not np.allclose(coefficients[:, 0]+coefficients[:, 1], coefficients[:, 2], atol=1e-7):
        raise ValueError('regression_identity_failed')
    fixtures = sorted({f for r in rs for f in r['buckets']['fixture']})
    # Every print containing the held-out fixture is removed. Overlapping
    # fixture groups are not disjoint clusters; ranges are influence, not CIs.
    slopes, failures = [], 0
    for fixture in fixtures:
        keep = np.array([fixture not in r['buckets']['fixture'] for r in rs])
        if keep.sum() <= x.shape[1]:
            failures += 1; continue
        result = fit(x[keep], y[keep], w[keep])
        if result is None:
            failures += 1; continue
        slopes.append(result[0][1])
    output = {'status': 'descriptive_only', 'known_prints': len(rs), 'unique_fixtures': len(fixtures),
              'terms': names, 'effective_weighted_print_count_not_independent': float(w.sum()**2/np.sum(w*w)),
              'leave_one_fixture_out_refits': len(slopes), 'leave_one_fixture_out_failures': failures,
              'standard_errors': None, 'p_values': None,
              'inference': 'No IID standard errors. Overlapping fixtures and short history; deletion ranges measure influence, not statistical confidence.',
              'components': {}}
    for j, component in enumerate(COMPONENTS):
        values = [float(s[j]) for s in slopes]
        output['components'][component] = {'coefficients': dict(zip(names, map(float, coefficients[:, j]))),
            'weighted_r_squared': r2[j], 'spread_slope_fixture_deletion_range': [min(values), max(values)] if values else None}
    return output


def load_dataset(dataset, hashes):
    paths = {k: ROOT/dataset[k] for k in ('opportunities', 'features')}
    for p in paths.values():
        hashes[str(p)] = hashlib.sha256(p.read_bytes()).hexdigest()
    with gzip.open(paths['features'], 'rt') as f:
        fs = {}
        for feature in map(json.loads, f):
            key = feature['evaluation_id']
            if key in fs:
                raise ValueError('duplicate_feature')
            fs[key] = feature
    data = json.loads(paths['opportunities'].read_text())
    rows, ids, reference_rows = [], set(), {}
    for row in data['opportunities']:
        key = row['evaluation_id']; pair = (row['model'], key)
        if key not in fs:
            continue
        if pair in ids:
            raise ValueError('duplicate_model_print')
        fields = ('at','quantity','yes_price','maker_fee','yes_settlement','settled_at','buckets')
        reference = {k: row.get(k) for k in fields}
        if key in reference_rows and reference != reference_rows[key]:
            raise ValueError('inconsistent_cross_model_print')
        reference_rows[key] = reference
        ids.add(pair); feature = fs[key]
        if not math.isclose(feature['at'], row['at'], abs_tol=1e-6, rel_tol=0):
            raise ValueError('feature_timestamp_mismatch')
        rows.append({**row, 'values': components(row), 'nlegs': len(feature['legs']),
            'raw': sum(p['raw_width_cents'] for p in feature['pairs']),
            'fee_expanded': 100*sum(p['width'] for p in feature['pairs'])})
    if {r['evaluation_id'] for r in rows} != set(fs):
        raise ValueError('incomplete_feature_join')
    by_model = defaultdict(set)
    for r in rows:
        by_model[r['model']].add(r['evaluation_id'])
    common = set.intersection(*by_model.values()) if by_model else set()
    return rows, common, {m: len(v) for m, v in by_model.items()}


def write_report(records, out):
    lines = ['# Spread compensation and calibration workflow', '',
        'Every covered print remains included; no edge, quote, spread, premium or capital filter is applied. Available-cohort comparisons use each model’s coverage. Common-cohort comparisons require all supplied models and identical trade prices, sizes, fees, outcomes and risk identities.', '',
        'All plotted components use the same known outcomes and payout quantities. In cents per payout contract: `realized = compensation + residual`, where `compensation = 100 × (price − fair − maker_fee/quantity)` and `residual = 100 × (fair − settlement)`. Negative residuals hurt a combo seller. Unknown outcomes are excluded from every plotted component equally; their notional and all-priced compensation are retained separately.', '',
        'Sum of underlying opposite-team spreads is a descriptive width measure, not an executable combo spread. Both raw and fee-expanded widths are analyzed. There are no depth assumptions or extra charges. The fee scenarios and causal pricing coverage are inherited from the input replays.', '',
        '## Overall decomposition on available data', '',
        '| Dataset / model | Known prints | Compensation (c) | Residual (c) | Realized net (c) |',
        '|---|---:|---:|---:|---:|']
    for r in records:
        if r['measure']=='raw' and r['cohort']=='available':
            s=r['overall']; v=s['components_cents']
            if s['known_prints']:
                lines.append(f"| {r['dataset']} / {r['model']} | {s['known_prints']:,} | {v['compensation']:+.3f} | {v['residual']:+.3f} | {v['realized']:+.3f} |")
    lines += ['', '## Raw-spread regression slopes', '',
        'Each coefficient is the change in the component’s net cents per contract associated with a 1c increase in summed leg spread. WLS uses payout quantity. The adjusted specification adds traded YES price (per 10c) and categorical leg count. Conditioning on traded price can create mechanical or selection associations; these are not causal estimates.', '',
        '| Dataset / model | Specification | Compensation slope | Residual slope | Net slope | Net slope fixture-deletion range |',
        '|---|---|---:|---:|---:|---|']
    for r in records:
        if r['measure']!='raw' or r['cohort']!='available':
            continue
        for spec, reg in r['regressions'].items():
            if reg['status']!='descriptive_only':
                continue
            cs=reg['components']; vals=[cs[c]['coefficients']['spread_cents'] for c in COMPONENTS]
            bounds=cs['realized']['spread_slope_fixture_deletion_range']
            lines.append(f"| {r['dataset']} / {r['model']} | {spec} | {vals[0]:+.3f} | {vals[1]:+.3f} | {vals[2]:+.3f} | {bounds[0]:+.3f} to {bounds[1]:+.3f} |")
    lines += ['', 'Regression component coefficients also add exactly because the design, observations and weights are identical. Both raw-spread and fee-expanded specifications, full coefficients, weighted R² and coverage are available in `results.json`; a flat slope table is in `regressions.csv`.', '',
        'Removing a fixture removes every combo containing it and refits the model. These overlapping-group deletion ranges measure influence, not confidence intervals. No IID standard errors or p-values are reported. Rank-deficient specifications are explicitly unavailable. Shared fixtures, small numbers of dates and imbalanced quantity weights prevent interpreting print counts as independent observations.', '',
        '## Figures', '']
    for dataset in sorted({r['dataset'] for r in records}):
        for cohort in ('available','common'):
            lines.append(f'- [{dataset}: {cohort}, raw spread]({dataset}_{cohort}_raw.png) · [fee-expanded spread]({dataset}_{cohort}_fee_expanded.png)')
    lines += ['', '## Reuse', '',
        'Run `scripts/spread_calibration_study.py --config config/spread_calibration_study.json --out <new-output-directory>`. Add dataset entries with opportunity replay JSON and opposite-moneyline feature JSONL.gz paths; paths resolve relative to the repository, and absolute paths are supported. No dates are hard-coded into this workflow. Feature generation and source collection remain prerequisites; this script does not fetch data or modify running frozen batches.', '',
        'Feature rows require evaluation_id, at, legs and pairs, with raw_width_cents and fee-expanded width in probability units for each pair. Existing opportunity rows provide per-model fair points, prices, quantities, fees, settlement information and fixture buckets. One dataset entry is one analysis window; supply a deduplicated combined replay/features pair to analyze a longer period jointly. Do not combine sports silently.', '',
        'The initial small-sample configuration covered CFB August 31–September 6, 2026 (incomplete non-Saturday tape) and the September 5 MLB census. Other runs use the dataset paths and identities recorded in their manifest; the initial dates are not imposed on this workflow. No coefficient is promoted to quoting. Use held-out dates, distinct fixtures, market-family/time-to-start controls and later markouts for future validation; negative settlement residuals alone cannot distinguish toxicity, miscalibration and common game-outcome luck.']
    (out/'REPORT.md').write_text('\n'.join(lines)+'\n')


def plot(records, out, dataset, cohort, measure):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FuncFormatter
    rs = [r for r in records if r['dataset']==dataset and r['cohort']==cohort and r['measure']==measure]
    if not rs:
        return
    fig, axes = plt.subplots(2, len(rs), figsize=(6*len(rs), 7), squeeze=False, sharex=True)
    colors = {'compensation': '#0072B2', 'residual': '#D55E00', 'realized': '#222222'}
    labels = {'compensation': 'Price − fair − maker fee', 'residual': 'Fair − outcome', 'realized': 'Realized net P&L (sum)'}
    for col, r in enumerate(rs):
        bins = r['bins']; x = list(range(len(bins)))
        for c in COMPONENTS:
            y = [b['components_cents'][c] if b['known_prints']>=30 else float('nan') for b in bins]
            axes[0, col].plot(x, y, marker='o', color=colors[c], label=labels[c])
            for i, b in enumerate(bins):
                if 0 < b['known_prints'] < 30:
                    axes[0, col].scatter(i, b['components_cents'][c], facecolors='none', edgecolors=colors[c])
        axes[0, col].axhline(0, color='#888888', lw=.7)
        axes[0, col].set_title(f"{r['model']} · {r['overall']['prints']:,} prints")
        axes[0, col].set_ylabel('Quantity-weighted cents / contract')
        axes[0, col].legend(fontsize=8)
        axes[1, col].bar(x, [b['known_quantity'] for b in bins], color='#7EA7BE', label='Known outcomes')
        axes[1, col].bar(x, [b['unknown_quantity'] for b in bins], bottom=[b['known_quantity'] for b in bins], color='#BBBBBB', hatch='//', label='Unknown outcomes')
        axes[1, col].set_ylabel('Payout notional ($)')
        axes[1, col].yaxis.set_major_formatter(FuncFormatter(lambda v, _: f'${v/1e6:.1f}m' if abs(v)>=1e6 else f'${v/1000:.0f}k'))
        axes[1, col].set_xticks(x, LABELS)
        axes[1, col].set_xlabel('Sum of leg spreads (cents) · unequal buckets')
        axes[1, col].legend(fontsize=8)
        for ax in axes[:, col]:
            ax.grid(axis='y', alpha=.2)
    fig.suptitle(f'{dataset} · {cohort} · {measure.replace("_", " ")} spread decomposition', fontsize=13)
    fig.text(.04, .025, 'No edge, quote or capital filter. All three top components use identical known-outcome prints and quantity weights. Hollow points: <30 known prints.\n'
             'Negative fair − outcome hurts sellers; it does not establish toxicity. Realized P&L = compensation + residual. No spread reserve is charged.\n'
             'Short retained periods; shared outcomes, historical fee assumptions and incomplete CFB weekdays limit inference. Unknown outcomes shown below.', fontsize=9)
    fig.tight_layout(rect=(0, .13, 1, .94))
    for ext in ('png', 'svg'):
        fig.savefig(out/f'{dataset}_{cohort}_{measure}.{ext}', dpi=150)
    plt.close(fig)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', type=Path, default=ROOT/'config/spread_calibration_study.json')
    p.add_argument('--out', type=Path, required=True)
    args = p.parse_args(); config = json.loads(args.config.read_text())
    if config['schema_version'] != 1 or config['weight'] != 'payout_quantity' or config['minimum_edge_filter'] is not None or config['orders_enabled'] is not False:
        raise ValueError('unsupported_research_configuration')
    if set(config['spread_measures'])-{'raw','fee_expanded'} or set(config['regression_specs'])-{'spread_only','price_and_leg_count'}:
        raise ValueError('unsupported_measure_or_spec')
    args.out.mkdir(parents=True, exist_ok=True)
    # Completion attestation must not survive a failed rerun.
    (args.out/'manifest.json').unlink(missing_ok=True)
    hashes = {str(args.config): hashlib.sha256(args.config.read_bytes()).hexdigest()}
    records, coverage = [], {}
    for dataset in config['datasets']:
        rows, common, counts = load_dataset(dataset, hashes)
        coverage[dataset['name']] = {'model_rows': counts, 'common_prints': len(common)}
        for cohort in ('available', 'common'):
            for model in sorted(counts):
                rs = [r for r in rows if r['model']==model and (cohort=='available' or r['evaluation_id'] in common)]
                for measure in config['spread_measures']:
                    record = {'dataset': dataset['name'], 'sport': dataset['sport'], 'cohort': cohort, 'model': model, 'measure': measure,
                        'overall': summarize(rs), 'bins': [summarize([r for r in rs if bucket(r[measure])==i]) for i in range(len(LABELS))],
                        'regressions': {spec: regression(rs, measure, spec) for spec in config['regression_specs']}}
                    records.append(record)
            print(json.dumps({'dataset': dataset['name'], 'cohort': cohort, 'complete': True}), flush=True)
    (args.out/'results.json').write_text(json.dumps(records, indent=2, allow_nan=False)+'\n')
    with (args.out/'regressions.csv').open('w') as f:
        writer = csv.writer(f); writer.writerow(['dataset','cohort','model','measure','spec','component','spread_slope_cents_per_1c','fixture_deletion_min','fixture_deletion_max','known_prints','fixtures','weighted_r2'])
        for r in records:
            for spec, reg in r['regressions'].items():
                for component, v in reg.get('components', {}).items():
                    writer.writerow([r[k] for k in ('dataset','cohort','model','measure')]+[spec,component,v['coefficients']['spread_cents'],*(v['spread_slope_fixture_deletion_range'] or [None,None]),reg['known_prints'],reg['unique_fixtures'],v['weighted_r_squared']])
    hashes.update({str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in (Path(__file__), ROOT/'scripts/spread_profitability.py')})
    manifest = {'config':config,'input_and_code_hashes':hashes,'coverage':coverage,
        'regression': 'Descriptive payout-quantity WLS; raw slope and conditional slope controlling YES price and categorical leg count. Same known cohort for every component; coefficients add exactly.',
        'causality': 'Conditioning on traded price can introduce selection/mechanical associations; no causal toxicity estimate or production coefficient.',
        'uncertainty': 'Leave-one-fixture-out slopes are overlapping-group influence diagnostics, NOT confidence intervals. No p-values or IID standard errors.',
        'output_complete': True}
    for dataset in config['datasets']:
        for cohort in ('available','common'):
            for measure in config['spread_measures']:
                plot(records,args.out,dataset['name'],cohort,measure)
    write_report(records, args.out)
    (args.out/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')


if __name__ == '__main__':
    main()

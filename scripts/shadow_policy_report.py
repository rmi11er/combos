#!/usr/bin/env python3
"""Summarize logged candidate policies without inventing acceptance or fill P&L."""
import argparse
from collections import Counter, defaultdict
import gzip
import hashlib
import json
from pathlib import Path


def summarize(events):
    baseline = Counter()
    statuses = Counter()
    reasons = Counter()
    variants = defaultdict(Counter)
    disagreements = Counter()
    configs = Counter()
    count = 0
    for event in events:
        if event['kind'] != 'decision':
            continue
        count += 1
        decision = event['payload']
        baseline[decision['status'] + ':' + str(decision.get('reason'))] += 1
        configs[decision['config_version']] += 1
        study = decision.get('shadow_policy_study')
        if study is None:
            statuses['not_instrumented'] += 1
            continue
        statuses[study['status']] += 1
        if study.get('reason'):
            reasons[study['reason']] += 1
        context = study.get('source_disagreement')
        if context:
            difference = context['polymarket_minus_kalshi_combo_cents']
            disagreements['polymarket_higher' if difference > 1e-8 else 'kalshi_higher' if difference < -1e-8 else 'equal'] += 1
        for variant in study.get('variants', []):
            key = study['sport_model_version'] + ':' + variant['name']
            evaluated = variant['evaluation']
            row = variants[key]
            row['evaluated_requests'] += 1
            row['requests_with_feasible_floor'] += evaluated['floor'] is not None
            row['candidate_prices_logged'] += len(evaluated['candidates'])
            row['baseline_had_no_feasible_floor'] += decision.get('reason') == 'no_price_with_required_edge'
            row['baseline_risk_blocked'] += decision.get('risk', {}).get('allowed') is False
            row['selected_candidates'] += evaluated['selected'] is not None
    return {'schema_version': 1, 'decision_count': count, 'runtime_config_versions': dict(configs),
            'baseline_outcomes': dict(baseline), 'study_statuses': dict(statuses), 'study_reasons': dict(reasons),
            'disagreement_directions': dict(disagreements),
            'variants': {key: dict(value) for key, value in variants.items()},
            'candidate_counts_are_not_fills': True, 'acceptance_labels_available': False,
            'realized_candidate_pnl': None, 'orders_enabled': False}


def archived_events(directory, manifest):
    if manifest.get('complete') is not True:
        raise ValueError('complete_archive_required')
    for chunk in manifest['chunks']:
        path = directory / chunk['file']
        with path.open('rb') as handle:
            digest = hashlib.file_digest(handle, 'sha256').hexdigest()
        if digest != chunk['sha256']:
            raise ValueError('archive_chunk_hash_mismatch:' + chunk['file'])
        count = 0
        with gzip.open(path, 'rt') as handle:
            for line in handle:
                count += 1
                yield json.loads(line)
        if count != chunk['rows']:
            raise ValueError('archive_chunk_count_mismatch:' + chunk['file'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    manifest_path = args.archive / 'manifest.json'
    manifest = json.loads(manifest_path.read_text())
    summary = summarize(archived_events(args.archive, manifest))
    summary.update(archive=str(args.archive), archive_manifest_sha256=hashlib.sha256(manifest_path.read_bytes()).hexdigest())
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open('x') as handle:
        json.dump(summary, handle, indent=2)
        handle.write('\n')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()

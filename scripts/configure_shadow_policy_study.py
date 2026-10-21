#!/usr/bin/env python3
"""Copy a runtime config with a frozen, logging-only quote study embedded."""
import argparse
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from combos.shadow_policy_study import ShadowPolicyStudy


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime', type=Path, required=True)
    parser.add_argument('--study', type=Path, default=ROOT / 'config/shadow_policy_study.json')
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--balance-precision', choices=('.0001', '.01'), required=True,
                        help='Verified account cash precision; not inferred by this script')
    parser.add_argument('--fee-terms-available-at', type=float, required=True,
                        help='UTC Unix time at which configured combo maker fee terms were available')
    parser.add_argument('--policy-available-at', type=float, default=None,
                        help='Defaults to current UTC time; do not backdate newly chosen policies')
    args = parser.parse_args()
    runtime = json.loads(args.runtime.read_text())
    if runtime.get('mode') != 'shadow':
        raise ValueError('only_shadow_runtime_supported')
    study = json.loads(args.study.read_text())
    study.update(balance_precision=args.balance_precision,
                 fee_terms_available_at=args.fee_terms_available_at,
                 policy_available_at=time.time() if args.policy_available_at is None else args.policy_available_at)
    instance = ShadowPolicyStudy(study, runtime, None)
    runtime['shadow_policy_study'] = study
    args.out.parent.mkdir(parents=True, exist_ok=True)
    # Preserve initialized experiments and source configs; write a new snapshot.
    with args.out.open('x') as output:
        json.dump(runtime, output, indent=2)
        output.write('\n')
    print(json.dumps({'runtime': str(args.out), 'sport': runtime['sport'],
                      'study_config_sha256': instance.manifest()['config_sha256'],
                      'orders_enabled': False, 'status': 'prepared_not_started'}))


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Start a bounded, read-only shadow runtime with one command.

The runtime supervisor owns the Kalshi, creator, shadow, and Pinnacle child
services.  This wrapper only handles repeatable setup, environment loading,
preflight, and useful failure reporting.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


def load_env(path):
    """Load simple KEY=VALUE lines without evaluating shell syntax."""
    if not path:
        return
    try:
        lines = Path(path).read_text().splitlines()
    except OSError as exc:
        raise ValueError(f"cannot read env file: {path}") from exc
    for line in lines:
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        key, value = key.strip(), value.strip()
        if key and key not in os.environ:
            os.environ[key] = value.strip('"\'')


def run(command, *, capture=False):
    return subprocess.run(command, cwd=ROOT, env=os.environ.copy(),
                          check=False, text=True,
                          stdout=subprocess.PIPE if capture else None,
                          stderr=subprocess.STDOUT if capture else None)


def service_logs(db):
    paths = sorted(db.parent.glob(db.name + '.*.log'))
    if not paths:
        return 'No adjacent service logs were created.'
    chunks = []
    for path in paths:
        try:
            text = path.read_text(errors='replace')
        except OSError as exc:
            text = f'<unable to read: {exc}>'
        chunks.append(f'--- {path.name} ---\n{text[-4000:]}')
    return '\n'.join(chunks)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', default='config/runtime_nfl_authorized_shadow_20260910.json')
    parser.add_argument('--weights', default='config/weighting.json')
    parser.add_argument('--polling', default='config/oddspapi_polling.json')
    parser.add_argument('--pinnacle-cache', default='data/raw/oddspapi_live')
    parser.add_argument('--run-dir', help='directory for this run; defaults to a timestamped directory')
    parser.add_argument('--seconds', type=float, default=14400)
    parser.add_argument('--max-db-gb', type=float, default=8.0,
                        help='maximum database plus WAL size before a clean stop (default: 8 GB)')
    parser.add_argument('--env-file', default=str(Path.home() / '.codex' / '.env'),
                        help='simple KEY=VALUE credential file (default: ~/.codex/.env)')
    parser.add_argument('--skip-preflight', action='store_true')
    parser.add_argument('--resume', action='store_true',
                        help='reuse an already initialized database instead of creating a new one')
    parser.add_argument('--hedge-floor-cents',type=float,choices=(0.05,0.10),
                        help='shadow inventory hedge floor comparison; default uses configured 0.10 cents')
    args = parser.parse_args()

    load_env(args.env_file)
    if args.max_db_gb <= 0:
        raise ValueError('--max-db-gb must be positive')
    os.environ['COMBOS_MAX_EVENT_DB_BYTES'] = str(int(args.max_db_gb * 1024**3))
    config = ROOT / args.config
    fallback=json.loads(config.read_text()).get('source_fallback',{}).get('enabled',False)
    if not fallback and not os.environ.get('ODDSPAPI_API_KEY'):
        raise ValueError('ODDSPAPI_API_KEY is not configured; use --env-file or export it')

    weights = ROOT / args.weights
    polling = ROOT / args.polling
    if args.run_dir:
        run_dir = ROOT / args.run_dir
    else:
        run_dir = ROOT / 'runs' / ('shadow_' + time.strftime('%Y%m%d_%H%M%S'))
    db = run_dir / 'events.sqlite'
    run_dir.mkdir(parents=True, exist_ok=True)
    if args.hedge_floor_cents is not None:
        resolved=json.loads(config.read_text())
        if resolved.get('mode')!='shadow' or not resolved.get('inventory_fitting',{}).get('enabled'):
            raise ValueError('--hedge-floor-cents requires an inventory-enabled shadow config')
        resolved['inventory_fitting']['minimum_net_edge_per_share']=args.hedge_floor_cents/100
        config=run_dir/'shadow_policy.json'
        if config.exists():
            if json.loads(config.read_text())!=resolved:raise ValueError('existing shadow policy differs; use a fresh run directory')
        else:
            if args.resume:raise ValueError('comparison policy missing; cannot resume with a different policy')
            config.write_text(json.dumps(resolved,indent=2)+'\n')

    if not args.skip_preflight:
        preflight = [sys.executable, str(ROOT / 'scripts/nfl_preflight.py'),
                     '--config', str(config), '--weights', str(weights), '--polling', str(polling)]
        result = run(preflight)
        if result.returncode:
            raise SystemExit(result.returncode)

    if not args.resume:
        result = run([sys.executable, str(ROOT / 'scripts/runtime.py'), '--db', str(db),
                      '--config', str(config), '--weights', str(weights), 'init'])
        if result.returncode:
            raise SystemExit(result.returncode)

    command = [sys.executable, str(ROOT / 'scripts/runtime.py'), '--db', str(db),
               '--config', str(config), '--weights', str(weights), 'run',
               '--seconds', str(args.seconds), '--polling', str(polling),
               '--pinnacle-cache', str(ROOT / args.pinnacle_cache)]
    print(f'Shadow runtime starting; database: {db}', flush=True)
    result = run(command, capture=True)
    if result.returncode:
        print(result.stdout or '', file=sys.stderr, end='')
        print('\nShadow runtime stopped early. Service logs:', file=sys.stderr)
        print(service_logs(db), file=sys.stderr)
        print(f'\nResume with: {Path(sys.argv[0]).name} --run-dir {run_dir.relative_to(ROOT)} --resume',
              file=sys.stderr)
        return result.returncode
    print(result.stdout or '', end='')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)

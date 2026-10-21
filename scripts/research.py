#!/usr/bin/env python3
"""Reusable acquisition/import/replay/record entry points, separate from the frozen study."""
import argparse
import asyncio
from collections import Counter
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from combos.oddspapi import OddsPapi
from combos.research_store import ObservationStore
from combos.replay import replay_decision
from combos.weighted_fair import WeightPolicy


def jsonl(path):
    with Path(path).open() as f:
        for number, line in enumerate(f, 1):
            if line.strip():
                try: yield json.loads(line)
                except ValueError as exc: raise ValueError(f'invalid JSON at line {number}') from exc


def sha(path):
    with Path(path).open('rb') as f: return hashlib.file_digest(f, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    fetch = sub.add_parser('odds-fetch')
    fetch.add_argument('endpoint', choices=sorted(OddsPapi.ENDPOINTS))
    fetch.add_argument('--params', default='{}', help='JSON request parameters; never credentials')
    fetch.add_argument('--cache', default=str(ROOT/'data/raw/oddspapi'))
    fetch.add_argument('--refresh', action='store_true')
    ingest = sub.add_parser('import-observations')
    ingest.add_argument('input'); ingest.add_argument('--db', required=True)
    replay = sub.add_parser('replay')
    replay.add_argument('decisions'); replay.add_argument('--db', required=True)
    replay.add_argument('--out', required=True)
    replay.add_argument('--policy', default=str(ROOT/'config/weighting.json'))
    capture = sub.add_parser('record-rfqs')
    capture.add_argument('--out', required=True)
    capture.add_argument('--seconds', type=float, default=60)
    creators = sub.add_parser('profile-creators')
    creators.add_argument('journals', nargs='+', help='closed journals, in chronological order')
    creators.add_argument('--out', required=True)
    args = parser.parse_args()
    if args.command == 'odds-fetch':
        data = OddsPapi(args.cache).get(args.endpoint, json.loads(args.params), args.refresh)
        print(json.dumps({'request': data['request'], 'retrieved_at': data['retrieved_at'], 'cache': args.cache}))
    elif args.command == 'import-observations':
        store = ObservationStore(args.db); counts = Counter()
        try:
            with store.db:
                for row in jsonl(args.input): counts['inserted' if store.add(row) else 'duplicate'] += 1
        finally: store.close()
        print(json.dumps({'input_sha256': sha(args.input), 'counts': dict(counts)}))
    elif args.command == 'replay':
        if not Path(args.db).exists(): raise ValueError('observation database does not exist')
        policy = WeightPolicy(**json.loads(Path(args.policy).read_text()))
        out = Path(args.out); out.mkdir(parents=True, exist_ok=False)
        store = ObservationStore(args.db)
        # Keep a consistent SQLite read snapshot throughout this replay.
        store.db.execute('BEGIN')
        digest = hashlib.sha256()
        for (record,) in store.db.execute('SELECT record FROM observations ORDER BY market_key,venue,available_at'):
            digest.update(record.encode()+b'\n')
        manifest = {'complete': False, 'started_at': time.time(), 'decision_sha256': sha(args.decisions),
                    'observation_content_sha256': digest.hexdigest(), 'policy': asdict(policy),
                    'code_sha256': {str(p.relative_to(ROOT)): sha(p) for p in [*sorted((ROOT/'src/combos').glob('*.py')), Path(__file__).resolve()]}}
        (out/'manifest.json').write_text(json.dumps(manifest, indent=2))
        counts = Counter(); exclusions = Counter()
        try:
            with (out/'comparisons.jsonl').open('w') as f:
                for decision in jsonl(args.decisions):
                    result = replay_decision(store, decision, policy)
                    counts[result['status']] += 1
                    if result['status'] == 'excluded': exclusions[result['reason']] += 1
                    f.write(json.dumps(result, allow_nan=False)+'\n')
        finally: store.close()
        summary = {'counts': dict(counts), 'exclusions': dict(exclusions),
                   'cohort': 'all three venues, valid depth and freshness on both legs',
                   'fills_assumed': False, 'capital_allocation_applied': False}
        (out/'summary.json').write_text(json.dumps(summary, indent=2))
        manifest.update(complete=True, completed_at=time.time(), output_sha256=sha(out/'comparisons.jsonl'))
        (out/'manifest.json').write_text(json.dumps(manifest, indent=2))
        print(json.dumps(summary))
    elif args.command == 'record-rfqs':
        from combos.shadow import record
        print(json.dumps(asyncio.run(record(args.out, args.seconds))))
    elif args.command == 'profile-creators':
        from combos.creator_profile import profile
        print(json.dumps(profile(args.journals, args.out)))


if __name__ == '__main__':
    try: main()
    except KeyboardInterrupt: pass
    except (ValueError, RuntimeError, KeyError) as exc:
        print(str(exc), file=sys.stderr); sys.exit(1)

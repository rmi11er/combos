#!/usr/bin/env python3
"""Read-only sniffer observations; export age is not causal policy freshness."""
import argparse
import json
from pathlib import Path
import sqlite3
import subprocess
import time


def observe(database, manifest_path, summary_path, pid=None, now=None, query_seconds=2):
    now = time.time() if now is None else now
    manifest = json.loads(Path(manifest_path).read_text())
    result = {'observed_at': now, 'capture_closed_cleanly': manifest.get('closed_cleanly'),
              'capture_started_at': manifest.get('started_at'),
              'capture_updated_at': manifest.get('updated_at'),
              'manifest_counts': manifest.get('counts', {}),
              'causal_policy_freshness': 'unproven',
              'limitations': 'Manifest counts are not deduplicated fills. Latest request time is not a durable cursor. Export generation time does not prove evidence freshness.'}
    if pid is not None:
        proc = subprocess.run(['ps', '-p', str(pid), '-o', 'pid=,lstart=,etime=,pcpu=,stat=,comm='], capture_output=True, text=True)
        result['process_observation'] = {'pid': pid, 'present': proc.returncode == 0 and bool(proc.stdout.strip()), 'ps': proc.stdout.strip()}
    path = Path(database).resolve()
    result['storage_bytes'] = {suffix or 'database': Path(str(path)+suffix).stat().st_size if Path(str(path)+suffix).exists() else 0 for suffix in ('', '-wal', '-shm')}
    try:
        # No writer initialization, checkpoint, full-table count or immutable=1:
        # the latter would ignore committed data in a live WAL.
        with sqlite3.connect(path.as_uri()+'?mode=ro', uri=True, timeout=query_seconds) as db:
            deadline = time.monotonic()+query_seconds
            db.set_progress_handler(lambda: int(time.monotonic() > deadline), 1000)
            db.execute('PRAGMA query_only=ON')
            row = db.execute('SELECT at FROM requests INDEXED BY requests_time ORDER BY at DESC LIMIT 1').fetchone()
            result['latest_committed_request_at'] = row[0] if row else None
            result['request_age_seconds'] = now-row[0] if row else None
    except sqlite3.Error as exc:
        result['database_observation_error'] = str(exc)
    try:
        summary = json.loads(Path(summary_path).read_text())
        generated = summary.get('generated_at')
        result['export'] = {'generated_at': generated, 'age_seconds': now-generated if isinstance(generated, (int, float)) else None,
                            'unique_requests': summary.get('unique_requests'), 'active_blacklist_ids': summary.get('active_blacklist_ids')}
    except (OSError, ValueError) as exc:
        result['export_observation_error'] = str(exc)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ('database', 'manifest', 'summary', 'out'):
        parser.add_argument('--'+field, required=True)
    parser.add_argument('--pid', type=int)
    args = parser.parse_args()
    result = observe(args.database, args.manifest, args.summary, args.pid)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    temp = out.with_suffix(out.suffix+'.tmp')
    temp.write_text(json.dumps(result, indent=2)+'\n')
    temp.replace(out)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()

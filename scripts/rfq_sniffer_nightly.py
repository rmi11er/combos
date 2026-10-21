#!/usr/bin/env python3
"""Launchd dispatcher: one passive capture per Central calendar day."""
from datetime import datetime
import fcntl
import json
from pathlib import Path
import shutil
import subprocess
import sys
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / 'runs/rfq_sniffer_nightly'
CENTRAL = ZoneInfo('America/Chicago')


def due(now):
    local = now.astimezone(CENTRAL)
    return local.hour == 18 and local.minute < 5


def write_json(path, value):
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(value, indent=2) + '\n')
    temp.replace(path)


def main():
    now = datetime.now(CENTRAL)
    if not due(now):
        return 0
    STATE.mkdir(parents=True, exist_ok=True)
    with (STATE / 'dispatcher.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return 0
        directory = STATE / now.date().isoformat()
        # A failed/interrupted attempt remains inspectable, never silently doubled.
        if directory.exists():
            return 0
        directory.mkdir()
        status = {'started_at': now.isoformat(), 'status': 'running',
                  'timezone': 'America/Chicago', 'capture_seconds': 3600}
        write_json(directory / 'status.json', status)
        try:
            if shutil.disk_usage(ROOT).free < 10 * 1024**3:
                raise RuntimeError('Less than 10 GiB free; capture skipped')
            with (directory / 'run.log').open('w') as log:
                command = ['/usr/bin/caffeinate', '-i', '/bin/zsh',
                           str(ROOT / 'scripts/scheduling/rfq_sniffer_nightly.sh'),
                           str(directory)]
                subprocess.run(command, cwd=ROOT, stdout=log,
                               stderr=subprocess.STDOUT, check=True)
            status['status'] = 'complete'
        except Exception as exc:
            status.update(status='failed', error=str(exc))
        status['finished_at'] = datetime.now(CENTRAL).isoformat()
        write_json(directory / 'status.json', status)
        write_json(STATE / 'latest_status.json', status | {'directory': str(directory)})
        return 0 if status['status'] == 'complete' else 1


if __name__ == '__main__':
    sys.exit(main())

"""Collect one bounded fill window. No orders, quotes or cash mutations."""
import argparse
import json
import os
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from combos.execution_journal import ExecutionJournal
from combos.fill_collection import FillCollector
from combos.kalshi_readonly import ReadOnlyClient, ReadSigner

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--initial-start', required=True, type=int)
    parser.add_argument('--until', required=True, type=int)
    parser.add_argument('--subaccount', type=int, default=0)
    parser.add_argument('--max-pages', type=int, default=5)
    args = parser.parse_args()
    os.umask(0o077)
    args.database.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    journal = ExecutionJournal(args.database)
    try:
        result = FillCollector(journal, ReadOnlyClient(ReadSigner.from_environment())).poll(
            subaccount=args.subaccount, initial_start=args.initial_start, until=args.until,
            out=args.out, max_pages=args.max_pages)
        print(json.dumps(result))
    finally:
        journal.close()

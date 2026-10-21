#!/usr/bin/env python3
"""Capture and screen RFQs without pricing or placing any orders."""
import argparse
import asyncio
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    cap = sub.add_parser('capture')
    cap.add_argument('--out', required=True)
    cap.add_argument('--seconds', type=float, default=600)
    run = sub.add_parser('run', help='capture, then update the persistent behavioral blacklist')
    run.add_argument('--root', default=str(ROOT/'runs/rfq_sniffer'))
    run.add_argument('--db', default=str(ROOT/'data/derived/rfq_sniffer/evidence_v2.sqlite'))
    run.add_argument('--out', default=str(ROOT/'output/rfq_sniffer'))
    run.add_argument('--seconds', type=float, default=600)
    run.add_argument('--policy')
    run.add_argument('--mappings', action='append', default=[])
    scan = sub.add_parser('scan')
    scan.add_argument('journals', nargs='+')
    scan.add_argument('--db', required=True)
    scan.add_argument('--out', required=True)
    scan.add_argument('--policy')
    scan.add_argument('--mappings', action='append', default=[])
    export = sub.add_parser('export')
    export.add_argument('--db', required=True)
    export.add_argument('--out', required=True)
    args = parser.parse_args()
    if args.command in ('capture','run'):
        from combos.rfq_sniffer_capture import capture
        directory = args.out if args.command=='capture' else str(Path(args.root)/time.strftime('capture_%Y%m%d_%H%M%S'))
        result = asyncio.run(capture(directory, args.seconds))
        if args.command=='run':
            from combos.rfq_sniffer import scan_journals
            policy = json.loads(Path(args.policy).read_text()) if args.policy else None
            result = {'capture':result,'blacklist':scan_journals([directory],args.db,args.out,policy,args.mappings)}
    else:
        from combos.rfq_sniffer import scan_journals, export_database
        if args.command == 'scan':
            policy = json.loads(Path(args.policy).read_text()) if args.policy else None
            result = scan_journals(args.journals, args.db, args.out, policy, args.mappings)
        else:
            result = export_database(args.db, args.out)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('Capture interrupted; closed journal chunks are retained for a later scan.',file=sys.stderr)

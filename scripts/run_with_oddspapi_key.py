#!/usr/bin/env python3
"""Run a child command with the user's key handoff; never evaluate shell text."""
import argparse
import os
from pathlib import Path
import subprocess


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--key-file',type=Path,required=True)
    parser.add_argument('command',nargs=argparse.REMAINDER)
    args=parser.parse_args()
    command=args.command[1:] if args.command[:1]==['--'] else args.command
    if not command:parser.error('a child command is required after --')
    try:key=args.key_file.read_text().strip()
    except (OSError,UnicodeError):parser.error('cannot read key handoff file')
    if not key or any(c.isspace() for c in key):parser.error('key handoff must contain one nonempty token')
    environment=dict(os.environ);environment['ODDSPAPI_API_KEY']=key
    # The key appears only in the child environment, never its command line.
    return subprocess.run(command,env=environment,check=False).returncode


if __name__=='__main__':raise SystemExit(main())

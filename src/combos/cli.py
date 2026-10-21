"""Installed command entry point.

The historical scripts remain available during migration.  This entry point is
intentionally conservative until workflows are moved into ``combos.workflows``.
"""

import argparse


def main() -> int:
    parser = argparse.ArgumentParser(prog="combos-runtime")
    parser.add_argument("--version", action="version", version="combos-shadow 0.1.0")
    parser.parse_args()
    parser.error("choose an explicit workflow script while the migration is in progress")
    return 2

#!/usr/bin/env python3
"""Convert certified daily replay JSON to compact, queryable Parquet.

The original JSON is never modified. Each output records the source SHA256,
row count, schema and output SHA256 so a later archival/removal decision can be
made without losing provenance. This is for derived replay data; raw source
evidence and certified fee inputs remain untouched.
"""
import argparse
import hashlib
import json
import os
import shutil
import time
from pathlib import Path

import duckdb


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def convert(source: Path, target: Path, connection) -> dict:
    if target.exists():
        raise FileExistsError(f"refusing_to_overwrite:{target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    if temporary.exists():
        raise FileExistsError(f"stale_temporary_output:{temporary}")
    source_hash = sha256(source)
    escaped = str(source.resolve()).replace("'", "''")
    escaped_out = str(temporary.resolve()).replace("'", "''")
    relation = (
        f"select unnest(opportunities) as row from "
        f"read_json('{escaped}', format='unstructured', "
        f"maximum_object_size=1000000000)"
    )
    count = connection.execute(f"select count(*) from ({relation})").fetchone()[0]
    schema = [tuple(row) for row in connection.execute(f"describe select * from ({relation})").fetchall()]
    connection.execute(
        f"copy ({relation}) to '{escaped_out}' "
        "(format parquet, compression zstd, row_group_size 100000)"
    )
    os.replace(temporary, target)
    return {
        "source": str(source),
        "source_sha256": source_hash,
        "output": str(target),
        "output_sha256": sha256(target),
        "source_bytes": source.stat().st_size,
        "output_bytes": target.stat().st_size,
        "rows": count,
        "schema": schema,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--date", action="append", dest="dates")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    dates = set(args.dates or [])
    sources = sorted(args.batch_root.glob("*/replay/opportunities.json"))
    if dates:
        sources = [p for p in sources if p.parent.parent.name in dates]
    if not sources:
        raise SystemExit("no_replay_sources")
    manifest = {
        "format": "parquet",
        "compression": "zstd",
        "duckdb_version": duckdb.__version__,
        "created_at": time.time(),
        "batch_root": str(args.batch_root),
        "records": [],
    }
    connection = duckdb.connect()
    connection.execute("set preserve_insertion_order=false")
    try:
        for source in sources:
            date = source.parent.parent.name
            target = args.out / f"{date}.parquet"
            record = convert(source, target, connection)
            record["date"] = date
            manifest["records"].append(record)
            print(json.dumps({"date": date, "rows": record["rows"],
                              "source_bytes": record["source_bytes"],
                              "output_bytes": record["output_bytes"]}), flush=True)
    finally:
        connection.close()
    manifest["total_rows"] = sum(r["rows"] for r in manifest["records"])
    manifest["source_bytes"] = sum(r["source_bytes"] for r in manifest["records"])
    manifest["output_bytes"] = sum(r["output_bytes"] for r in manifest["records"])
    temporary = args.out / "manifest.json.tmp"
    temporary.write_text(json.dumps(manifest, indent=2) + "\n")
    os.replace(temporary, args.out / "manifest.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# Closed NFL capture archived with byte-exact restoration

The September6 capture's SQLite database and existing WAL/SHM sidecars were confirmed
closed with lsof, compressed together, and independently read back from the archive.
Each member's SHA256 and byte count matched the original. Source hashes and mtimes
were rechecked before removing the uncompressed copies. The4.670GB database and
sidecars are preserved in a3.206GB tar.gz bundle, reclaiming about1.47GB of allocated
space. Archive and manifest were fsynced; the reusable replacement path now also
fsyncs them and rechecks closure immediately before removing originals.

The archive is runs/nfl_capture_20260906_2234/sqlite_archive_20260909/bundle.tar.gz.
Its manifest records the exact member bytes, hashes, timestamps and permissions.
Raw event archives, reviews and code snapshots remain where they were. The exact
archiving implementation used is saved beside the archive as archive_source.py.

Older workflows opening that capture's events.sqlite require restoration first:

```
.venv/bin/python scripts/archive_closed_sqlite_bundle.py restore --out runs/nfl_capture_20260906_2234/sqlite_archive_20260909
```

Restoration verifies the complete archive before writing, rejects unknown members
and conflicting targets, and reconstructs missing members without overwriting
matching originals. Allow4.67GB free for restoration. A small database/WAL fixture
passed a complete archive-remove-restore byte comparison; the large production
bundle passed streaming member verification rather than a second full on-disk
restore, which would consume the reclaimed space.

Free space after maintenance was9.33GiB. Historical collection and validation
supervisors were verified live; four August dates remain pending. No active
historical collection input was moved. This creates operating headroom but does
not solve long-term market-data retention capacity.

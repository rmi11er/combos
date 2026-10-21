# Bounded native compression of completed generated SQLite files

Prepared for root review; **not executed on the real databases by the authoring agent**.

```sh
.venv/bin/python scripts/compress_generated_sqlite.py \
  --manifest config/generated_sqlite_compression_20260908.json \
  --out runs/morning_research_20260908/generated_sqlite_compression
```

The default verifies the pinned identities, evidence, closed files and read-only integrity, but performs no compression. Add `--execute` only for the reviewed maintenance run.

The helper has a hardcoded four-path allowlist: the completed disk and streaming input databases, the completed CFB benchmark native-metadata database, and the earlier MLB cohort metadata index. It refuses all other paths, including retained NFL captures and sniffer evidence. The new manifest pins each database's exact SHA256/length and completed-report evidence hashes. Streaming records/parity, legacy MLB cohort counts, and CFB completion timestamp/count are asserted explicitly. No existing helper or watcher was edited.

For each target:

1. Check all completion references and pinned database identity.
2. Require the DB and any WAL/SHM/journal files to have no `lsof` handles. Reject any nonempty sidecar, symlink or missing DB. Snapshot all file/sidecar fingerprints.
3. Run SQLite `quick_check` through a read-only immutable connection; preserve page/free-page counts for the receipt.
4. Use the existing read-only imported `ditto --hfsCompression` copy helper after a bounded native support probe. Write only a same-directory temporary file, verify exact logical SHA256/length and read-only integrity, and preserve file mode/mtime.
5. Require physical allocated-block savings; otherwise discard only the temporary copy and leave the original unchanged.
6. Recheck completion evidence, DB/WAL/SHM/journal closure and fingerprints, and original SHA256 immediately before the atomic replacement.
7. Verify the original-path SHA256, logical length and SQLite integrity afterward. Record measured allocated bytes before/after and exact hashes.

The operation does not VACUUM, checkpoint, remove journals, rewrite database contents, change file paths or delete records. Native compression is filesystem representation only. Already-native-compressed targets are skipped after validating pinned identity and integrity. The helper is bounded, one-shot and creates no background process.

Seven meaningful tests pass: fixed-path allowlist refusal; nonempty-sidecar/open-file refusal; changed DB hash refusal; real native SQLite compression with subsequent read-only query and exact hash/mode/mtime preservation; and pre-swap rejection when a sidecar, completion reference or original fingerprint changes. The actual macOS native test uses only a small synthetic temporary SQLite database. The prepared real manifest's evidence hashes and assertions were checked read-only.

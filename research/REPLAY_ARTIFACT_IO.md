# Standalone replay artifact I/O adapter

`scripts/replay_artifact_io.py` is a reusable leaf module. It has not been integrated into the streaming replay, index, runner or parity verifier, and no existing artifact was changed. It performs no JSON parsing or serialization.

## Interface

```python
from replay_artifact_io import text_writer, text_reader, export_gzip, zstd_identity

with text_writer(new_output / 'policy.decisions.jsonl.zst') as output:
    output.write(serialized_decision + '\n')

with text_reader(new_output / 'policy.decisions.jsonl.zst') as incoming:
    for line in incoming:
        consume(line)

codec_metadata = zstd_identity()
verification = export_gzip(
    new_output / 'policy.decisions.jsonl.zst',
    export_directory / 'policy.decisions.jsonl.gz',
)
```

Both text contexts accept `.jsonl.gz` and `.jsonl.zst`. They use UTF-8 and preserve line endings. `export_gzip` accepts Zstd input and a **new** gzip destination; it copies decoded bytes without even requiring valid UTF-8 or valid JSON. Its result records SHA-256, decoded byte count and newline count.

Zstd defaults to installed `/opt/homebrew/bin/zstd` with arguments `-q -6 -c`: default window and threading, no `--long` and no extra workers. The identity helper records resolved executable path, SHA-256, byte size, CLI version and arguments. A caller can pin these values in its experiment manifest. There is no dependency installation or implicit upgrade.

## Publication, validation and cleanup

- Writers create a temporary sibling and publish the completed file through an atomic, no-overwrite hard link. Existing paths, dangling symlinks and competing writers are refused. On failure, only the adapter's own temporary file is removed. Parent directories are created if necessary.
- Zstd writes use a 64KiB `BufferedWriter` over the child pipe, supporting large writes correctly. Diagnostics use a temporary file, avoiding stderr-pipe deadlock and unbounded diagnostic RAM; errors expose at most 16KiB of diagnostic text.
- Successful reader exit drains any unread tail and checks the decoder exit code. Gzip tails are likewise consumed to check their CRC/trailer. A caller reading only the first line cannot accidentally certify truncated input.
- A consumer exception aborts the child, waits up to two seconds after termination, then kills and reaps an uncooperative process. The original consumer exception is preserved. Broken compressor pipes become `ArtifactCodecError`; codec nonzero exits also raise that error. Python gzip/UTF-8 errors retain their ordinary exception types.
- Export validates the decoder before the destination writer may publish. A decoder producing partial output and then failing cannot leave a completed export. Export returns only after successful validation and publication.
- Streams belong to their context managers; callers should not manually close/detach them. A normal exit always verifies the entire input; intentionally stopping early therefore still spends the I/O required to validate its tail. A consumer exception prioritizes cleanup and does not certify remaining input.

## Verification

Fifteen tests in `tests/test_replay_artifact_io.py` pass with `ResourceWarning` treated as an error. They cover gzip and Zstd round trips with a multi-megabyte single Unicode/CRLF write; arbitrary-byte export; truncated unread tails; corrupt export; large stderr; early compressor exit; existing and racing outputs; absent executables; consumer exceptions with buffered text; and an uncooperative decoder requiring SIGKILL and reaping. Tests verify that failures publish no output and leave no temporary files or unreaped children.

No large replay was run. Future integration still requires the full 48-policy decoded oracle comparison and corresponding manifest/read compatibility changes. The storage benefit remains the earlier measured estimate; this adapter alone does not resolve the remaining disk-capacity shortfall.

# August 28 exchange catalog recovery

The cohort's second attempt completed after public-request recovery, preserving
its successful caches. Exchange acquisition then failed on Gamma's legacy
`/events` pagination at offset 2100 with HTTP 422, the same migration encountered
on August 24.

Applied the existing explicit keyset-to-cache materializer with the identical
series/date filters. It collected 22 raw pages containing 2,112 unique events,
retaining all 2,100 previously observed IDs. Independent verification confirms
the derived event list equals the raw list exactly and all recorded page hashes
match. Derived cache status is explicitly local materialization success, not a
claim of HTTP success from the old endpoint. Original cache files are preserved.

All frozen validation pins passed before relaunch. Batch, recovery and validation
supervisors resumed under runs/aug28_gamma_keyset_recovery_20260909/resumed;
the exchange stage retains its attempt history. No held-out outcome was inspected
to tune parameters. The remaining August 30 stage may require the same adapter
if its query reaches the retired offset range.

Evidence: runs/aug28_gamma_keyset_recovery_20260909/materialization/manifest.json
and representation_verification.json; resumed/launch.json records process identities.

The resumed exchange stage subsequently exhausted retries on two HTTP429 candle
jobs. An explicit supplemental stage invocation reused the other 753 successful
caches and fetched only those two jobs. All 755 jobs then validated; original
attempts remained at two, with the extra invocation and original state recorded.
Batch/recovery/validation supervision was relaunched under
runs/aug28_rate_limit_recovery_20260909/resumed after verifying every pinned file.

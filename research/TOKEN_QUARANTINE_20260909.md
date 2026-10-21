# Per-market depth quarantine

The opt-in shadow setting polymarket_snapshot_verification.token_quarantine=true
replaces whole-feed reconnects on confirmed REST/WS depth mismatch with immediate
inactive observations for the affected token. Later updates cannot make that token
active while quarantine remains. Other books continue collecting and verifying.

Quarantined tokens receive at most three follow-up verification requests by default
(maximum_token_rechecks). A successful exact full-depth, revision/generation-stable
comparison publishes the restored observation before its verification certificate.
Failed requests consume the attempt budget. After exhaustion the token stays
inactive; there is no blind release, REST overwrite, or whole-feed restart. The
quarantine and attempt counts survive reconnects within the collector process.
They are not persisted across a process restart, whose fresh stream follows the
normal bootstrap checks. The setting is off by default.

Thirty-six tests pass, including mismatch isolation, update suppression, recovery
publication ordering and exhausted-token retention. A 45-second dual-collector
live probe completed both collectors: nine 100-book selections, 893 verifications,
two tokens quarantined, no quarantine recoveries and no mismatch-triggered global
resets. Replay checked 1,587 event/key combinations and found no usable candidate
for a quarantined book. Successful recovery has synthetic coverage, but was not
observed live in this probe. No Pinnacle requests or exchange orders were made.

This preserves healthy-book availability but does not yet actively rebuild a
persistently divergent token. Next add a bounded fresh subscription/rebuild for
quarantined tokens and require full-depth verification before release. A sustained
combined three-source capture remains necessary before declaring feed readiness.

Artifacts: runs/token_quarantine_20260909 (runtime, completion, event stream,
verification and prechange source). Implementation: src/combos/quiet_book_probe.py.

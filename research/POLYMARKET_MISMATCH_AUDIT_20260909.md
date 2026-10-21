# Reconstructed REST/WS mismatches

Replayed every raw Polymarket frame through the existing book reconstructor and
matched all 24 full-ladder rejection events to their saved REST batches. All 24
mismatches reproduced. They involved 12 unique tokens:

- 22 checks had identical best bid/ask prices **and sizes**, with deeper differences.
- Two checks on the same token had identical best prices but different best-ask size:
  REST 3,759.38 contracts versus local WS 3,664.38, a difference of 95 (~2.59%).
- No rejected check had differing best bid or ask prices.
- Twenty checks differed at one depth level; two at two levels; two at six levels.

For the best-ask discrepancy, REST's native timestamp equaled the last processed
WS update timestamp. It persisted in REST checks roughly 22 and 43 seconds after
that update. That is not explained merely by a book update arriving during the
request; those were a separate six rejections. This replay establishes reproducible
divergence, not whether the cause is provider feed semantics, missing messages,
snapshot bootstrap or our reconstruction. Using the same reconstructor is not an
independent proof that reconstruction is correct.

The observed discrepancies do not change these midpoints, but can affect liquidity
weights and depth-based sizing. Keep rejecting full-depth certificates. Next compare
an independent raw-frame reconstruction and fresh subscription snapshots for the
affected tokens, then implement bounded resynchronization with explicit invalidation.
Do not silently trust REST or waive the mismatch because top prices agree.

Reusable workflow: `scripts/audit_snapshot_mismatches.py`.
Artifacts: `runs/polymarket_mismatch_audit_20260909/{summary,rows}.json`, with source
hashes, event references, request times, last WS update references, top of book and
all differing levels. No requests, model changes or orders occurred during this audit.

The MLB recovery supervisor resumed collection under PID 42635; that process and
the frozen validation supervisor were verified live during this review.

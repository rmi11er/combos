# SF–SEA native fixture alias: retrospective concentration overlay

**The retained evidence supports one semantic divisional fixture for `26JAN17SFSEA` and `26JAN18SFSEA`.** A narrowly allowlisted overlay merges only those two tokens for retrospective concentration and structure reporting. The frozen benchmark remains unchanged.

## Evidence and limits

- The retained NFL playoff schedule contains exactly one San Francisco-at-Seattle divisional fixture, January 17 at 20:00 Eastern. Its official-source URL and schedule hash are saved in the overlay.
- The completed January 12 native combo dictionary contains **110 explicit native single-game combo definitions combining both tokens**. A representative native `KXMVENFLSINGLEGAME-26JAN18SFSEA` collection pairs `KXNFLGAME-26JAN18SFSEA-SF` with January 17 Christian McCaffrey/Brock Purdy player-market legs. This is stronger evidence than nearby team/date strings alone.
- Within this retained dictionary, Jan18 SF–SEA appears in moneyline markets; Jan17 appears in moneyline, spreads, totals and player markets. Three complete representative identity extracts and all source hashes are retained.
- This is retrospective fixture identity evidence, **not a claim that the mapping or revised clock was known at trade time**, and not proof that every pair of leg contracts has interchangeable payoff rules. Example native metadata carries a February update timestamp after the study. No pricing map, outcome, schedule cutoff or risk bucket was changed.

## Deduplicated concentration at maker coefficient 0.035

| Mutually exclusive native-token membership | Prints | Net P&L |
|---|---:|---:|
| Jan17_only | 1,699 | $29,878.94 |
| Jan18_only | 1,612 | $-39,517.59 |
| both | 528 | $8,795.19 |
| union | 3,839 | $-843.46 |

The merged semantic fixture has **3,839 unique prints** and **-$843.46** net P&L. Summing the two original fixture contributions would instead give +$7,951.73, incorrectly double-counting the 528 shared prints and their +$8,795.19 P&L.

Excluding all semantic SF–SEA prints produces portfolio P&L **-$387,312.15**, compared with the unchanged overall **-$388,155.61**. The overlay has ten semantic fixtures rather than eleven native tokens. Its fixture contribution/exclusion tables remain overlapping any-leg membership across *different* games; only the three alias-membership partitions are additive. Never sum cross-game fixture contributions into portfolio P&L.

## Semantic structure correction

Exactly **186 prints** previously classified as distinct by native token become same-game under the reviewed identity. These prints contribute **+$2,737.2640** at the 0.035 scenario. No print is added or removed.

| Structure | Frozen native-token prints | Frozen P&L | Semantic-overlay prints | Semantic-overlay P&L |
|---|---:|---:|---:|---:|
| Contains same-game legs | 399,990 | $655,754.50 | 400,176 | $658,491.77 |
| Distinct fixtures | 57,157 | $-1,043,910.12 | 56,971 | $-1,046,647.38 |

All **2,140 baseline schedule-unknown prints remain schedule-unknown**. A retrospective fixture merge does not certify historical availability of the corrected start time. Model eligibility, observed quantities, native settlements, fee scenarios, original ledger and equity curves remain unchanged.

## Artifacts and verification

Final overlay: `runs/nfl_sfsea_semantic_overlay_20260908_v2/summary.json`; independent arithmetic checks: `verification.json`. The first concentration-only overlay is retained separately in `runs/nfl_sfsea_semantic_overlay_20260908`.

The overlay preserves all four fee scenarios (0/.0175/.035/.07), exact Decimal economics, source hashes, explicit identity evidence, mutually exclusive alias partitions, semantic fixture exclusion tables and semantic structure cuts. All partitions reconcile to both original token contributions; structure monetary sums/counts match the unchanged 457,147-print baseline under every fee rate. Nonaliased fixture records are identical. The exact-allowlist unit test passes.

Reusable runner: `scripts/nfl_sfsea_fixture_overlay.py`. It reads cached data only and writes a new output directory; no provider calls, frozen edits or plots. All foreground jobs finished.

# July 15 mapping revision: completed research overlay

The bounded follow-up to [the identity audit](JULY15_MAPPING_AUDIT.md) acquired all seven required public Polymarket token histories with **seven GET attempts, seven HTTP 200 responses, zero paid/provider requests**. Six histories contain points; the over-5.5 total history is empty throughout the requested July 14–16 window. The attempt ledger preserves the 28-total/four-per-token ceiling across resumes.

The implementation is a separate `scripts/july15_mapping_overlay.py` and output directory `runs/july15_mapping_overlay_20260907/`. It permits only the seven explicitly reviewed NYM–PHI contracts, full-game event ID 687903, moneyline ID 2870228 and game ID 10078738, with pinned archived input hashes. Original and revised schedules remain separate; the earlier cutoff is enforced as a conservative retrospective overlay. Official announcement intraday availability remains unknown. It is not asserted to have been known on July 15.

Existing Kalshi histories and other PM captures are reused through read-only input operations via symlinks. Baseline source/configuration/mapping files were not modified. The existing replay is invoked as a bounded subprocess using the separate exchange view. Source hashes were checked before and after execution. Every unchanged common-cohort model point, stressed bound, fee, quantity, price, canonical risk bucket, guard and risk multiplier is asserted identical.

## Actual coverage

The common priced cohort expands from **392 to 734** of the 1,202 eligible July 15 prints, adding **342** prints. The audit's mapping-level ceiling was 343 additions: one candidate using the over-5.5 total has no PM price history and remains excluded. The absent over-8.5 mapping and the independently unresolved TB–BOS Game 1 mappings remain excluded. All included eventual settlement outcomes are known.

## Results after the unchanged fee scenario

These are hypothetical seller P&L at observed public print prices, attributed at trade time. Actual settlement timing controls cash/risk release. The fee scenario is still historically unverified where identified by the baseline; the overlay does not certify fees or exceptional payoff parity. Models remain two-source point diagnostics with no Pinnacle and no RFQ acceptance model.

| Unlimited selected model | Baseline common P&L | Newly priced P&L | Expanded common P&L |
|---|---:|---:|---:|
| Kalshi | −$3,049.19 | +$3,785.02 | +$735.82 |
| Equal blend | −$2,476.79 | +$4,442.39 | +$1,965.60 |
| PM75 blend | −$2,256.46 | −$443.89 | −$2,700.35 |
| Polymarket | −$2,280.94 | −$757.09 | −$3,038.03 |

Unlimited sell-all is **−$3,567.43** on the baseline common cohort, **+$2,862.20** on newly priced prints, and **−$705.22** combined. Expanded sell-all requires **$97,522.64** peak cash. The selected sets also exceed the funded account: expanded unlimited peak cash ranges from $63,039 to $76,588.

| Funded selected model | Baseline common P&L | Expanded common P&L | Expanded fills | Expanded peak cash |
|---|---:|---:|---:|---:|
| Kalshi | −$79.88 | −$37.45 | 39 | $555.12 |
| Equal blend | −$54.48 | −$7.70 | 39 | $557.03 |
| PM75 blend | +$5.90 | +$34.00 | 41 | $595.09 |
| Polymarket | +$5.90 | +$76.64 | 44 | $538.03 |

The funded expanded experiment runs the entire expanded cohort chronologically with the original $10k/$100 underlying/$100 combo/$250 fixture policy and .003 point-edge test. It is not a sum of separately funded baseline and newly priced portfolios. The retained newly priced-only funded run is explicitly an independent diagnostic account.

The model ranking changes materially when a missing fixture is restored. That demonstrates why missing mappings can bias research conclusions. It does not show that the revised ranking generalizes: all newly priced prints share the same recovered fixture, and PM-weighted models still differ substantially in selection and resulting outcome exposure.

## Verification and reuse

Four tests pass for exact allowlist identity, unchanged doubleheader exclusions, conflicting/duplicate event and market clocks, native original-schedule prose, payoff-match failure and the earlier cutoff. The finished subprocess exited zero. All twelve saved portfolio ledgers were reloaded; P&L sums, common pricing invariance, selected settlement completeness, seven new capture hashes, and unchanged source/input hashes were verified.

Outputs: [generated comparison report](../runs/july15_mapping_overlay_20260907/REPORT.md), [summary](../runs/july15_mapping_overlay_20260907/summary.json), `plan.json`, `attempts.jsonl`, `replay/opportunities.json`, per-print pricing contexts and twelve compressed ledgers. The exact command was:

```sh
.venv/bin/python scripts/july15_mapping_overlay.py --out runs/july15_mapping_overlay_20260907 --execute
```

A compatible rerun reuses successful captures, preserving the attempt ledger. A changed code/evidence plan requires a new output directory. This is deliberately an exact one-date/one-fixture research overlay, not a general timestamp tolerance or live mapping approval. Broader adoption requires a reusable versioned schedule-identity layer and an independent audit of any July 16 records between the revised and original start clocks.

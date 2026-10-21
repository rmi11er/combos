# Quant research program — completed research studies

Original deliverables (preserved for the completion audit):

1. Historical NFL markout curves at 1/5/15/60 minutes and pregame close, with coverage, stale-reference sensitivity, price/spread/leg-count/time-to-start cuts, and later-period checks.
2. Daily volume buckets and causal activity-conditioned markouts, separating retrospective full-day labels from information available at entry; assess incremental time-to-kickoff information.
3. Pre-first-kickoff volume intensity and cumulative volume curves using a coverage-audited tape, with sport/slate heterogeneity and a trained-and-tested remaining-volume forecast.
4. Hedge economics: executable-price and fee sensitivities, available depth audit, clear distinction between approximate leg hedges and exact combo payoff replication.
5. Inventory-relief experiment: chronological matched-risk controls, 0.10c reducing-only hurdle, settlement and gross cash, before/after scenario risk, subsequent capacity effects, threshold/fee sensitivities and out-of-period evaluation.
6. Same-game opportunity and portfolio concentration/offset tests using feasible outcome constraints; no independence pricing or automatic production filter relaxation.
7. Reproducible scripts and data provenance, tests covering causal ordering and risk mechanics, verified visualizations, follow-up studies where initial evidence is fragile, and a succinct individual finding for each study.

Round-spend discount testing remains tabled; the feature is retained. No live trading, live policy changes, or new provider subscriptions are authorized by this research program.

Initial inspection: the retained NFL January replay has timestamped leg pricing contexts and archived minute candles, enabling actual underlying-price markouts rather than relying on the weight-driven short forward captures. The raw census, rather than only successfully priced opportunities, is needed for an unbiased scoped volume clock. Public prints support counterfactual allocation, not a causal quote acceptance model.

## Completion evidence

The September 10 research cycle is complete; this does not certify a production pricing policy. Findings and limitations are in `research/RESEARCH_FINDINGS_20260910.md`; the 20-chart atlas is `visualizations/07-research-program/index.html`.

| Original requirement | Authoritative evidence inspected | Result |
| --- | --- | --- |
| 1. NFL marks, coverage, feature cuts, freshness and later period | `extraction.json`, `volume_markouts.json`, `hedge_followup.json`; 110,422 marks independently reconciled, all entry fairs reproduced, balanced and available cohorts contrasted | Completed study |
| 2. Daily and causal volume marks; kickoff increment | `volume_features.jsonl.gz`, `volume_markouts.json`; simultaneous-print exclusion tests; chronological predictive comparisons with initial edge controls | Completed study; predictive improvement small |
| 3. Volume clock and forecast | NFL 14-day census and MLB 31-date manifests, `mlb_volume_clock.json`, `final_analysis.json`; 290 MLB groups and 144 later-period forecast groups, equal-date/volume-weighted views and forecast error bootstrap | Completed study; MLB useful, NFL unstable |
| 4. Hedge price/fee/depth economics | `hedge_followup.json`; zero/.035/.07 fee cases, entry and roundtrip deltas, single-leg superhedge check; retained candle schema has no executable depth | Completed economic and coverage study; not a depth-certified execution result |
| 5. Inventory relief and follow-ups | Default/capacity/conditioned inventory results and ledgers; `inventory_fee_followup.json`, `inventory_repricing.json`; triggers, fees, age gating, settlement transitions, actual-hurdle repricing proxy | Completed historical studies; not robust or production-certified |
| 6. Same-game opportunity and offsets | Wider historical universe, `samegame_history.json`; ten scalar-safe native-market portfolio bounds, chronological fractions and all-YES selection stress | Completed scope and risk study; joint pricing not falsely imputed |
| 7. Reproducibility, verification, visualization, individual summary | Successful 12-step `pipeline_run.json`, 63 passing tests, `audit.json`, `visual_qa.json`, `reproducibility_manifest.json`, findings and atlas | Completed and verified |

Final audit: 62 books, 2,969 independently recomputed fill-risk checks, 110,422 reconciled future marks, and current source/output hashes. All 20 charts render at 736px and 320px without horizontal overflow, missing paths, or runtime exceptions; their exact-value disclosures work. The standalone wrapper was rendered and visually inspected. These are direct artifact checks, not an inference from unit tests alone.

No missing required study is relabeled as a deployment gate. Missing executable depth and causal acceptance evidence are findings of the data/identification audits; no executable-capacity or demand-elasticity claim is made. Live quoting and the same-game production filter remain unchanged.

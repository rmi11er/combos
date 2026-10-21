# Research program progress — initial snapshot, subsequently completed

Completion update: all remaining work listed in this original progress snapshot has been addressed. See `research/RESEARCH_PROGRAM_20260910.md` for requirement-by-requirement evidence and `research/RESEARCH_FINDINGS_20260910.md` for the conclusions. The final audit passes: 63 tests, 62 books, 2,969 independent fill-risk recomputations, 110,422 future marks, and 20 verified charts. Added follow-ups include fee and entry-freshness sensitivities, outcome-conditioned settlement accounting, and fixed-size quotes actually repriced at the requested edge hurdles under an explicit historical-price acceptance proxy. No study process remains running.

The following is retained as historical progress context, not a current task list.

## Completed computations

- `research_program_extract.py`: 23,809 January NFL moneyline prints; fixed-Kalshi 1/5/15/60-minute and pregame-close marks with source age and cutoff flags. Reproduces every archived entry fair exactly. Three unit tests.
- `research_volume_markouts.py`: hash-verified 14-day census; 25,107 scoped moneyline prints, eight first-kickoff cohorts, 1,551 summary cells, train-before-Jan12/test-after predictive comparisons and remaining-volume forecasts. Two unit tests cover simultaneous-print exclusion and timezone. Full-day buckets descriptive; hour-volume causal. Source histories not repriced from forward outcomes.
- `research_inventory_relief.py`: exact 512-state, nine-fixture full-period NFL replay and eight-state later-period replay. Baseline gross settings reproduce 21 fills / -$29.4028. Default limits never activate fixture relief. Additional $1,000 instrument/$250 combo sensitivity creates fixture constraints; 0.10c and 0.20c relief tested at 80/90/100% triggers. Gross cash retained and cash accounting asserted. Three risk-gate tests.
- `research_hedge_followup.py`: balanced all-horizon-fresh cohorts (314 earlier-period, 53 later-period prints), and entry/roundtrip leg-delta hedge cost scenarios at 0/.035/.07 fee coefficients. Entry spreads alone consume the mean later-period edge. No executable depth claim.
- `research_samegame_history.py`: all 14 dates' pure NFL universe scanned. 53,670 same-game-containing versus 40,282 distinct-fixture 2–4-leg fullgame pregame prints. Ten single-game portfolios bounded under native-market scalar-safe complement constraints. Full-period certified payout reductions roughly 29–45%; chronological growth not monotonic. All-YES-selected stress retained. Not a priced joint-model backtest.
- `research_mlb_volume_clock.py`: 31 complete retained cohort dates (includes July13, which lacked the earlier priced replay). 585,691 prints in 290 fully observed final-six-hour kickoff groups. July-trained, August-tested clock forecasts. Must update the initial output's hardcoded '30 dates' limitation by rerunning the corrected script before delivery.

Authoritative results: `runs/research_program_20260910/`. No live configuration changes.

## Remaining work before completion

1. Visualizations for each study, rendered and checked; no chart delivered yet. The visualization skill was read fully. Reload full visualize skill before creating or updating a visualization. Existing project has `visualizations/` reports; no thread-scoped visualization writable directory supplied. Browser skill read fully, but discovery finds neither browser nor Node REPL tools; local headless Chrome is installed and may be used as a fallback, with permissions respected.
2. Audit and strengthen tests for end-to-end replay, cash release, scenario arithmetic, fee precision, and summary denominators. Current passing tests are narrow and do not prove whole-program completion.
3. Compute summarized volume-forecast performance and heterogeneity, not just curves. Add equal-day versus volume weighting and NFL/MLB comparable six-hour views. Consider time-since-listing and active-cohort selection limits.
4. Verify markout cohort-change sensitivity (balanced result exists), volume regression controls (entry edge included), small-slate dependence, and freshness loss. Predictive MAE gains from volume are tiny; no causal or stable-significance claims.
5. Inventory follow-up: late settlement removal can increase the conservative unconditioned scenario risk. Peak metrics were fixed to include settlements. The fixed grid retains both outcomes of resolved fixtures, so apparent post-settlement cap excess is conservative and may be an artifact. Investigate or explicitly quantify this before interpreting capacity safety. Relief gate checks current worst loss and fixture sensitivity but future known game constraints are not narrowed. Do not describe these results as production-safe risk limits.
6. Additional inventory fee/size/slate sensitivity where informative; current capacity scenario is not deployment authorization. At the 90% trigger, full-period .1c relief gives -$30.76 versus +$176.04 net-risk flat .3c; need full later-period comparison and direct versus displaced-flow attribution.
7. Reproducibility manifest with all scripts/input hashes, commands, rendered artifacts, and final report. Summarize each research idea individually and succinctly only after the required verification. Update main program checklist against evidence; leave persistent goal active until all required work is done.

## Process handles

At this note's creation, only inventory re-run handle 22771 may still need final polling. All other launched studies returned terminal successful outputs. Do not restart based on this note; poll the handle or verify authoritative process state first.

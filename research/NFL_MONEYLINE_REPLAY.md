# Offline NFL moneyline replay

`scripts/nfl_moneyline_replay.py` turns the certified completed daily NFL cohorts and existing moneyline exchange histories into compatible backtest inputs and fully retained comparison ledgers. It performs no network requests and changes no runtime/frozen pipeline source.

```sh
.venv/bin/python scripts/nfl_moneyline_replay.py --out runs/nfl_moneyline_replay_20260907/new_complete_dates
```

The default root is `runs/nfl_playoffs_history_20260907`. Use a new output directory for each expanded date set. The runner selects every cohort day marked complete by the existing watcher, checks every output hash and hourly source-manifest hash, verifies 24 contiguous hourly intervals, and requires the completed dates themselves to be contiguous. It never treats an unfinished day or a missing date as zero trading activity.

The entire eligible sample is full-game moneyline YES-taker prints, 2–4 distinct target playoff fixtures, before the earlier verified schedule/capture cutoff minus 60 seconds. Kalshi, PM and fixed per-leg 50/50 and 25/75 blends use an identical common priced cohort. Sources become historically available 60 seconds after their native source clock. Carry-forward is allowed only within successful query coverage and never across gaps. Missing early PM history is excluded explicitly; PM depth is unavailable historically, and its interval borrows Kalshi's raw spread as the historical-only proxy. These fixed point models do not use imputed depth for weights. Pinnacle is absent, not synthesized.

Canonical NFL risk identities aggregate opposite-team complementary moneylines, buying/selling orientation and equivalent combo leg sets using `canonical_leg_risk`. Independent point fair and the existing pairwise-stressed upper bound are retained separately. Point selection charges .003 per payout contract after recomputed maker cash fees. The funded account preserves $10k initial cash, $100 underlying, $100 combo and $250 fixture gross maximum-loss limits, with no ticket cap. One continuous ledger spans all included dates; actual settlement releases cash/risk, whereas known eventual P&L is attributed at the original trade time for diagnostic curves.

The experiment is not live policy: ordinary completed-game payoff equivalence is an assumption, exceptional settlements remain unverified, and no outcome is used for eligibility or sizing. `quote_allowed` signifies offline scope/source checks only, not certified production health, correlation or mapping approval. An observed print does not establish that we would win an RFQ. This runner does not alter live source-disagreement guards.

Fee assumptions remain explicit. Archived January PM metadata says `feesEnabled=false`, but effective historical fee dates were not certified. Kalshi leg taker .07 and combo maker .035 are research scenarios. The runner repeats full/unlimited selection and sell-all at maker coefficients 0/.0175/.035/.07, with exact existing direct-member .0001 cash rounding and zero initial order accumulator. Changing taker interval fees does not change midpoint products or fixed blend point selection. Unverified fees must not be described as actual historical net receipts.

## First completed result

January 5–8: 3,105 primary candidate prints across market families; 2,165 eligible moneyline YES-taker prints; **1,848 common priced prints**. January 5 lacks prior PM prices for 317 candidates. All later included moneyline candidates are priced. All selected outcomes are known, although they settle after the trading window and therefore cannot fund any January 5–8 orders.

At the .035 maker scenario, unlimited sell-all earns **−$191.01** on peak committed cash **$338,849.01**. Kalshi-selected prints show +$20,281.48, PM +$14,886.34, equal blend +$17,443.72 and PM75 +$15,849.72. These headlines are dominated by one real archived 34,803-contract Rams/Eagles YES print at 56.9 cents, settled zero, with net seller P&L **$19,504.18**. Its ID is `8455844c-3f71-55a5-6e7f-adcee0c3b3eb`; the raw tape index and native combo metadata agree on quantity, side, price, legs and settlement. Excluding that print leaves Kalshi +$777.30, PM −$4,617.84, equal −$2,060.46 and PM75 −$3,654.46. Removing all selected trades involving either Rams/Carolina or Eagles/San Francisco makes Kalshi's remaining P&L negative as well.

The funded policies accept only 5–20 trades per model, with peak cash $97–$174. Kalshi returns −$4.86, PM −$128.24, equal +$0.63 and PM75 −$79.79. These are capacity-constrained research results, not actual fills. The four-day sample effectively reuses six underlying Wild Card outcomes and does not establish a stable daily Sharpe or NFL launch edge.

Artifacts: [report](../runs/nfl_moneyline_replay_20260907/jan5_8/REPORT.md), [summary and fee sensitivities](../runs/nfl_moneyline_replay_20260907/jan5_8/summary.json), [compatible opportunities](../runs/nfl_moneyline_replay_20260907/jan5_8/opportunities.json), and sixteen compressed full comparison ledgers. Source availability/context is retained per print in `pricing_context.jsonl.gz`.

Five targeted tests pass for causal source availability, coverage gaps, complementary canonical buckets and combo aliases, NO interval orientation, kickoff cutoff, and fixed per-leg blend construction. All sixteen output ledgers were reloaded and checked for identical four-model cohorts, correct scenario fee provenance, exact known-P&L summation, zero unknown selected outcomes and matching code hashes. No new provider queries were used.


## January 5–11 update and plotting workflow

The new replay at `runs/nfl_moneyline_replay_20260907/jan5_11` includes 16,219 common priced prints. The current comparison and concentration interpretation are in [the morning report](MORNING_REPORT_20260908.md). Earlier dated outputs remain retained.

Render existing ledgers without rerunning pricing or decisions:

```sh
.venv/bin/python scripts/plot_nfl_moneyline_replay.py \
  --run runs/nfl_moneyline_replay_20260907/jan5_11 \
  --out runs/nfl_moneyline_replay_20260907/jan5_11/NEW_PLOT_DIRECTORY
```

The output directory must be new. The default maker-fee coefficient is 0.035; `--fee` selects another already-generated scenario. Source hashes, unchanged curve/summary P&L endpoints and PNG/SVG hashes are retained. Funded and unlimited panels show trade-time eventual P&L, point edge, YES premium/payout face and actual committed cash. Funding captions are read from the ledger configuration. Daily P&L variance uses USD²; Sharpe is explicitly withheld for this short sample of shared fixtures. The no-price-filter funded benchmark still enforces risk limits, so it is not labeled as having filled every print.

Root visually inspected the initial funded/unlimited figures; the second rendering clarifies risk-limited benchmark labels and fills/evaluations without changing any curve. Both versions are retained, with the first plotter source saved alongside its outputs.

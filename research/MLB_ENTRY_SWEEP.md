# Fixed entry thresholds and capital usage

`scripts/mlb_entry_sweep.py --input <opportunities.json> --date YYYY-MM-DD --out <directory>` compares six fixed entry policies on the common available-model intersection of a complete MLB day. It rejects sampled cells, incomplete reporting windows, inconsistent paired execution/settlement fields, shared-fixture combos, non-full-game series and prints inside the 60-second pregame cutoff. Completeness relies on the upstream census attestation; this report does not independently redownload the public tape.

The fixed alternatives are sell every priced print; at least 0, 0.1, 0.3 or 0.5 cents of net edge per **combo contract**; and a separately named 0.3 cents per leg per combo contract. The current default is 0.3 cents per combo contract. For a four-leg combo, the explicit per-leg alternative requires 1.2 cents per combo contract. Maker fees are already subtracted in every threshold test.

`BacktestConfig.entry_filter='all_priced'` bypasses only the edge test. Input validation, source quote guards, any configured premium limit and funded canonical risk checks still apply. `minimum_net_edge_unit='leg_contract'` multiplies the required edge by the recorded verified leg count; it does not modify fair probabilities or the recorded model edge. All original defaults remain unchanged. This is research backtesting code, with no live runtime changes.

Each policy reruns an independent portfolio twice: unlimited funding/concentration and the existing $10,000 capital, $100 per canonical underlying/combo, $250 per fixture policy. It retains full observed quantities and actual settlement-time cash release. Eventual settlement P&L and accepted model edge are attributed to trade time for review, but cannot fund orders before settlement. Selected/rejected P&L, fees, outcome bounds, YES premium, payout notional, cumulative cash, peak/mean simultaneous cash, positive/negative expected edge, overlapping fixture contributions and concentration diagnostics are exported. A public print is an assumed full execution at its observed price, not an observed acceptance of our RFQ quote.

Outputs are `summary.json`, a completion/provenance `manifest.json`, compact decision and curve JSONL archives, and four-panel constrained/unconstrained PNG/SVG plots. Each figure shows known net P&L with unresolved-outcome bounds, peak cash, YES premium and net point-model edge across the fixed alternatives. The original input hash resolves decision IDs back to complete source context. No optimizer selects a threshold or updates production weights. These daily runs reset the $10,000 portfolio; aggregating them is not a continuous multi-day funding simulation with overnight exposure.

## September 5 smoke run

All 21,880 common Kalshi/Polymarket prints were used. This date's outcomes were already inspected; it is exploratory, not an untouched validation set.

| Entry policy | Kalshi funded prints / known P&L / peak cash | Polymarket funded prints / known P&L / peak cash |
|---|---:|---:|
| Sell every priced print | 207 / −$25.64 / $1,792 | 207 / −$25.64 / $1,792 |
| 0 cents | 163 / +$16.38 / $1,575 | 162 / +$33.92 / $1,667 |
| 0.1 cents | 145 / +$59.65 / $1,460 | 159 / +$75.22 / $1,636 |
| Current 0.3 cents | 96 / +$148.99 / $1,334 | 128 / −$44.75 / $1,522 |
| 0.5 cents | 50 / +$100.48 / $899 | 114 / −$85.43 / $1,519 |
| 0.3 cents per leg | 31 / +$228.17 / $730 | 95 / +$54.19 / $1,336 |

Lowering the threshold increases admitted flow but cannot approach $10,000 deployment under the current full-ticket risk constraints on this day: even removing the edge filter peaks at $1,792. Funded sell-all's final unresolved-outcome bounds are −$201.63 to +$20.11. Its net model-edge forecasts are negative: −$4.11 under Kalshi and −$2.42 under Polymarket.

Unlimited sell-all has +$419,528.94 known P&L but $4,112,989.94 peak committed cash. At the current 0.3-cent threshold, unlimited Kalshi has +$39,680.72 known P&L/$215,362.70 peak cash, and Polymarket +$35,703.05/$419,653.76. At 0.1 cents the figures become +$113,036.17/$912,090.04 and +$97,511.15/$1,268,478.29. Larger raw P&L comes with substantially more exposure, so it is not sufficient evidence to lower the threshold.

Known outcomes and single-day results cannot select a stable profitable policy. Every daily plot explicitly marks Sharpe and daily variance unavailable. The frozen alternatives should now run on additional complete dates, with source-specific calibration and risk-capacity studies reviewed separately. Full replay input assumptions—including historical fee metadata, schedule proxies and exchange-only coverage where Pinnacle is unavailable—continue to apply.

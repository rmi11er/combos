# Three-source liquidity-weighted fair scenarios

The actual weighted-fair implementation was run on 1,464 matched captured moneyline
observations across 32 team contracts. Exchange inputs retain observed bid/ask depth,
actual configured taker-fee formulas and causal native/verified freshness. Pinnacle
uses the retained delayed snapshot's two-way odds and native stake-limit values.

Pinnacle limit currency remains unverified. Explicit hypothetical USD-per-native-unit
conversions of 0.1, 1 and 10 bracket sensitivity; none is asserted to be correct.
Each conversion was crossed with tie probability 0/1% and exceptional-settlement
probability upper bound 0/0.5%, giving 12 scenarios / 17,568 computed rows.
These probabilities are sensitivity assumptions, not estimated inputs. The exceptional
payout spans [0,1]; its uncertainty expands endpoints while the point uses no exception.

With zero tie/exception adjustments:

| Assumed USD per native limit unit | Median Pinnacle weight | Median absolute blend–Kalshi gap | Median gap when PM/Pinnacle agree against Kalshi |
|---|---:|---:|---:|
| 0.1 | 15.7% | 0.17c | 0.49c |
| 1 | 31.9% | 0.31c | 0.65c |
| 10 | 59.1% | 0.45c | 0.72c |

The sharp-peer weighting candidate gives PM and Pinnacle a 1.5 score multiplier,
then uses square-root depth divided by fee-expanded width, freshness decay and
venue caps. The table shows why native stake units cannot be silently treated as
USD. A currency-invariant relative-liquidity model would be a different explicit
model requiring separate testing, not a factual substitute for currency evidence.

No hard interval-disagreement halt occurred in these zero-adjustment scenarios.
That is not a live approval: the standalone research calculation bypasses the
production normalizer only to insert labeled hypothetical capacities/payoff bounds.
Live mapping gates remain intact. Repeated heartbeat observations and complementary
team contracts are not independent samples; no settlement profit or calibration
conclusion is drawn. This is leg pricing, not a combo fill backtest.

Every output row independently reconciled point fair to its weights and transformed
source points; weight sums/caps and interval bounds passed. Input and output hashes
are retained in `runs/nfl_three_source_fair_sensitivity_20260909`. Reusable workflows:
`capture_source_agreement.py` exports full pricing inputs;
`three_source_fair_sensitivity.py` runs the assumption grid.

Next apply candidate leg fairs at actual RFQ decision times, including all mapped
non-player families, and compare quote reference/edge/risk scenarios with baseline
decisions. Currency/payoff choices must remain explicit until verified or modeled.

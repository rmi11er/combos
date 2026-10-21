# NFL live fair weight-driver review

Extended the reusable attribution replay with `--weight-drivers`. Each observed
mark retains before/after venue depth, fee-expanded spread, freshness, score
multiplier, score, weight and whether the source reference changed. These are
descriptive input changes, not separately identified causal effects.

Replayed the completed three-minute capture without provider calls. All 65,995
baseline pricing records and all 1,348 observed marks reproduced exactly.
Venue midpoint price contributions remain zero throughout this quiet sample.

Of the 1,348 marks, freshness changed in every mark, depth in 382, fee-expanded
spread in 500, and score multipliers in none. Counts overlap. In 669 marks,
freshness was the only changed score input among those recorded. The remaining
679 also had depth or spread changes. A spread can change with no midpoint
movement, so zero midpoint contribution does not imply an unchanged book.

Absolute combo-fair movement, cents per contract:

| Subset | Count | Median | 99th percentile | Maximum |
|---|---:|---:|---:|---:|
| All observed marks | 1,348 | 0.005575 | 0.068805 | 0.150300 |
| Only freshness input changed | 669 | 0.006217 | 0.100575 | 0.150300 |

None exceeded the current 0.3-cent per-combo-contract research hurdle. This
does not quantify live fill-conditioned loss, independently validate fair
probabilities, or cover unobserved marks. Repeated RFQs share games and are not
independent samples. No weights, edge charges, risk limits or creator sanctions
were changed from these results.

Implication: keep pure model-mixture movement separate from venue-price movement
in creator diagnostics. Do not widen quotes merely because this quiet capture
has nonzero model markouts. Test stable-vs-refreshing weights prospectively in
an active window before deciding whether smoothing improves pricing.

Artifacts: `runs/nfl_weight_driver_attribution_20260909/{summary,rows,magnitudes}.json`.
Workflow: `scripts/replay_fair_change_attribution.py --weight-drivers`.
Three attribution tests pass, including refresh-versus-depth distinction.

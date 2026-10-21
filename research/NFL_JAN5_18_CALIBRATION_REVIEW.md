# NFL January 5–18 calibration and selection disagreement

The matched NFL data does **not** establish Polymarket as sharper than Kalshi. Quantity-weighted Brier is slightly better for Kalshi, but the paired PM-minus-Kalshi difference changes sign under fixture omission. Profitable selections mainly benefit from favorable settlement residuals rather than the modest model-implied compensation, reinforcing the concentration concerns in the independent ledger audit.

## Scope and verification

This diagnostic uses all **23,809 common prints**, **4,897,161 payout contracts**, four exchange-only fair models, and native outcomes from the completed January 5–18 replay. The primary maker coefficient is the **unverified January .035 scenario**. Unlimited selection requires net edge ≥quantity×$0.003 **per combo contract**, not per leg. It compares observed public prints; it does not measure actual RFQ fills or a newly charged quote spread. Pinnacle is absent.

The standalone audit uses the existing paired-row validation/metrics helpers and independently computes four-model weighted squared errors and compensation/residual identities. It records unchanged input/helper hashes and its own source hash. The [independent ledger audit](NFL_JAN5_18_INDEPENDENT_AUDIT.md) separately verified all native outcomes, fees, threshold mechanics and source hashes. No provider requests, frozen source edits or August outcome inspection occurred.

## Common-cohort calibration

Brier is `sum(quantity×(fair−native outcome)²)/sum(quantity)`; lower is better. All models use identical prints, quantities and outcomes.

| Model | Quantity-weighted Brier | Compensation c/contract | Fair-minus-outcome residual c/contract |
|---|---:|---:|---:|
| Kalshi | 0.16276233 | −0.2452 | −5.8867 |
| Equal blend | 0.16282138 | −0.1919 | −5.9400 |
| PM75 blend | 0.16285307 | −0.1653 | −5.9666 |
| Polymarket | 0.16288621 | −0.1388 | −5.9931 |

The paired PM−Kalshi Brier difference is **+0.00012388** (PM worse). Deleting every print touching one fixture gives **[−0.00067104,+0.00072148]**: sign is not stable. The negative endpoint removes PHI–SF; the positive endpoint removes HOU–NE. Nine distinct fixtures occur in this priced cohort; queried fixture inventory is broader. Overlapping fixture deletions are influence diagnostics, not confidence intervals or independent tests.

All four common-cohort realized results are exactly −6.1319c/contract, totaling **−$300,290.32**. Changing the fair model only reallocates this realized result between compensation and residual; it does not change the economics of selling the same prints. Brier also combines calibration and discrimination; this summary is not a reliability-curve proof of calibrated probabilities.

## Selection disagreement

At the fixed 0.3c/combo threshold, the mutually exclusive K/PM groups reconcile to the full universe:

| Acceptance group | Prints | Net seller P&L |
|---|---:|---:|
| Both | 804 | +$41,142.64 |
| Kalshi only | 503 | +$21,606.72 |
| Polymarket only | 1,230 | +$2,386.43 |
| Neither | 21,272 | −$365,426.12 |

Both models avoid much of the losing common cohort. Kalshi-only selections contribute substantially more P&L than PM-only selections, despite fewer prints. This descriptive slice argues against automatically increasing PM weight on disagreement in NFL. It does not establish Kalshi dominance across independent slates, given the omission-sensitive calibration and selection concentration.

## Selection compensation versus outcome luck

Compensation is `quantity×(traded price−fair)−maker fee`, expressed below in cents per contract. Residual is `fair−settlement`, also in cents; compensation plus residual equals realized net.

| Model-selected cohort | Compensation c | Residual c | Realized net c | Total modeled compensation | Actual net P&L |
|---|---:|---:|---:|---:|---:|
| Kalshi | 1.4727 | 15.5188 | 16.9915 | $5,438.80 | $62,749.36 |
| Equal blend | 1.4123 | 11.1881 | 12.6004 | $5,250.87 | $46,846.83 |
| PM75 | 1.2631 | 10.0218 | 11.2848 | $5,465.97 | $48,835.59 |
| Polymarket | 1.0931 | 6.8420 | 7.9350 | $5,996.15 | $43,529.08 |

Average observed compensation exceeds the minimum hurdle because qualifying public prices can be wider than the cutoff. It is not proof we charged these amounts or could capture every print. Most realized profit comes from positive settlement residuals, well above modeled compensation. As the ledger audit shows, removing PHI–SF makes each model's total selected P&L negative.

The evidence JSON also reports selected-cohort Brier, but those values compare different outcome/quantity mixes and must not rank the models' forecasting skill. The matched full-universe Brier comparison above is the appropriate direct comparison.

## Research implication

Keep NFL source weights provisional and separate from MLB findings. Evaluate disagreement direction with matched future cohorts, fixture-purged validation, and stable causal source availability; preserve both quantity-weighted and fixture-level influence evidence. Treat modeled compensation as the pricing expectation and retrospective residual as uncertain calibration/outcome evidence, rather than extrapolating the larger realized profit as repeatable edge. No quoting model or risk limit is promoted here.

[Detailed verification](../runs/morning_research_20260908/nfl_jan5_18_calibration/verification.json) · [Standalone audit](../runs/morning_research_20260908/nfl_jan5_18_calibration/audit.py)

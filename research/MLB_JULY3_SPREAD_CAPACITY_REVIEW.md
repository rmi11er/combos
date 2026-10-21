# July 3 MLB spread, entry hurdle and capacity review

July 3 argues against relaxing hurdles merely to consume capital. Broader participation loses substantially in this development day, and increasing limits does not yield stable improvements. Wider underlying spreads correlate with *less negative* realized results here; most of that association comes from settlement residuals, not additional customer compensation. This does not establish a live liquidity surcharge or justify a hard spread filter.

## Completion and scope

The dated batch marks July 3 complete. Entry sweep and risk capacity stages both completed with exit code 0. Spread calibration has `output_complete: true`. Independently checked 12 recorded completion/input/code SHA256 values against disk, including both summaries/manifests, stage plots, calibration configuration, feature file, replay input and calibration source files. All matched. No pipeline edits, provider calls or August outcome inspection were performed.

Entry/capacity use the **26,176-print common four-model cohort**. The spread study covers **20,660 moneyline prints**, $5,107,128.05 payout quantity, all with known outcomes; it is a narrower cohort. Feature construction lists 20,873 eligible moneyline prints, with 197 uncovered timestamps, five crossed opposite-team pairs, eight missing prior states and three missing histories. The entry study's full common universe loses $1,198,875.69; the spread-covered subset loses $1,071,512.27. Neither is the all-family native MLB universe benchmark.

## Compensation versus calibration

For identical quantities, `realized net cents = compensation cents + settlement residual cents`, where compensation is `(traded price − model fair − fee/quantity)×100` and residual is `(fair − settlement)×100`.

| Model | Compensation c/contract | Residual c/contract | Realized net c/contract |
|---|---:|---:|---:|
| Kalshi | −0.300 | −20.681 | −20.981 |
| Equal exchange blend | −0.186 | −20.795 | −20.981 |
| PM75 blend | −0.129 | −20.852 | −20.981 |
| Polymarket | −0.072 | −20.909 | −20.981 |

The residual dominates the loss, whereas average compensation is modestly negative. Changing the fair model redistributes compensation/residual while observed-price P&L stays identical; the four equal net results are not four independent confirmations.

Raw summed opposite-team spread has a **+5.190c net slope per 1c wider spread**. Only approximately +0.078–0.079c is compensation; +5.11c is residual. After controlling for traded YES price and categorical leg count, the net slope is +3.198c with a fixture-deletion range **[−0.065,+4.286]**. Adjusted compensation is −0.083c (Kalshi), −0.035c (equal), −0.011c (PM75), and +0.013c (PM). Thus the adjusted customer-compensation relationship is weak and model-dependent.

Fee-expanded width also associates positively with net outcomes: +1.909c unadjusted and +3.266c adjusted; the adjusted fixture-deletion range is [+0.488,+4.289]. Width definitions and units differ, so the raw and expanded slopes are not interchangeable quote charges. The effective quantity-weighted print count is about 859, but even this is not an independent sample: only 28 overlapping fixtures underpin the spread cohort. Deletion ranges describe influence, not confidence intervals. Settlement residuals alone cannot distinguish miscalibration, adverse selection and shared game-outcome luck.

## Entry hurdle comparisons

These are filters against historical traded prices, not simulations of charging a new quote markup. The 0.3c **per combo contract** filter requires net edge ≥ quantity×$0.003. The 0.3c **per leg** filter multiplies that threshold by leg count, requiring 0.6–1.2c per combo contract for 2–4 legs. Both include modeled maker fees before comparison.

Unlimited selected net P&L (USD):

| Model | ≥0c | ≥0.3c/combo | ≥0.3c/leg | Per-leg selected prints |
|---|---:|---:|---:|---:|
| Kalshi | −116,839.01 | −30,638.35 | +274.29 | 36 |
| Equal blend | −240,813.06 | −22,867.89 | +174.95 | 49 |
| PM75 | −370,485.28 | −50,843.02 | +162.28 | 58 |
| Polymarket | −534,688.25 | −129,950.09 | −24,557.15 | 161 |

Per-leg filtering sharply reduces participation. Equal/PM75 positive results become negative under at least one fixture omission (ranges [−94.65,+279.75] and [−139.70,+296.32]). Kalshi's range remains [+13.80,+355.33], but only 36 selected prints on one development date do not validate a production rule. Polymarket remains negative for every one-fixture omission. This day does not corroborate a general recommendation to trust PM more aggressively.

## Capacity and risk

Capacity scenarios retain **0.3c per combo**, not the per-leg hurdle. Baseline limits are $10k starting capital, $100 contract, $100 combo and $250 fixture. Risk reserves full observed size; no partial-fill sizing is modeled.

| Model | Baseline P&L / peak cash | Balanced $500 P&L / peak cash | Balanced $1,000 P&L / peak cash | Capital-only P&L / peak cash |
|---|---:|---:|---:|---:|
| Kalshi | −24 / 1,101 | −255 / 4,018 | −355 / 6,858 | −4,570 / 9,999 |
| Equal blend | +46 / 932 | +255 / 4,030 | −948 / 6,086 | −6,303 / 10,000 |
| PM75 | −15 / 1,085 | +262 / 4,579 | −251 / 7,354 | −7,488 / 11,196 |
| Polymarket | +53 / 1,209 | −381 / 4,228 | −63 / 8,527 | −2,636 / 12,591 |

Balanced $500 means contract/combo/fixture limits $500/$500/$1,000; balanced $1,000 means $1,000/$1,000/$2,000. Peak committed cash may exceed $10k after actual settlement gains increase available equity; it is not proof of a starting-capital violation. Loosening only combo limits changes no baseline selections. Other one-limit changes have mixed outcomes. Full-size acceptance and chronological allocation also mean fewer fills need not imply less capital use. No limit should be selected from the best cell in this table.

## Next research step

Retain the prespecified hurdles and capacity scenarios through the larger development set, then test fixed choices on purged held-out dates. Pool exact quantity-weighted sufficient statistics rather than daily slope averages; separate compensation from residual, compare raw/fee-expanded width, and retain fixture-deletion sensitivity. Test liquidity-conditioned quote charges using causal widths and source disagreement only after the compensation relationship and calibration are stable across dates. Investigate partial-size quoting separately from relaxed exposure limits: today's low utilization is not evidence that wider exposure is profitable.

Evidence: `runs/mlb_historical_20260907/dated_fee_primary/2026-07-03/{entry_sweep,risk_capacity}/{manifest,summary}.json`; `runs/morning_research_20260908/spread_v2/2026-07-03/{feature_manifest.json,calibration/manifest.json,calibration/results.json,calibration/REPORT.md}`. All conclusions are development diagnostics and inherit the replay's historical pricing and fee assumptions.

# Archived exchange source-timing sensitivity

`scripts/mlb_timing_sensitivity.py` adds **0, 30, 60 or 120 seconds** to the existing 60-second historical information allowance for both Kalshi and Polymarket. It holds the actual trade timestamp, observed execution price/size, maker fee, fee-effective-date evaluation, pregame scope, eventual outcome and canonical risk identities fixed. No network requests or frozen pipeline edits occur.

```sh
.venv/bin/python scripts/mlb_timing_sensitivity.py \
  --day runs/mlb_historical_20260907/dated_fee_primary/2026-07-01 \
  --out runs/mlb_timing_sensitivity_20260907/july1
```

Use a separate output directory for each immutable date experiment. The current implementation was run on the original July 1 and July 15 baselines; it does not mix the separate NYM–PHI mapping overlay into the July 15 sensitivity.

## Safe clocks

The independent `TimingSourceFairs` adapter changes `KalshiHistory.publication_delay` from 60 to 60+extra. The PM adapter wraps `History.latest` so its as-of boundary becomes `actual_trade_at - 60 - extra`, and checks that boundary against captured query coverage. It preserves latest-inactive-state rejection. Neither adapter shifts the RFQ/public print clock. `SourceFairs` therefore still evaluates dated fee policy at the actual trade time.

Source context records native source time and actual experiment availability time. PM availability is relabeled as native point time+60+extra; the historical baseline helper's +60 label cannot falsely describe an experimentally delayed point as available earlier. A runtime assertion checks each used source was available by the actual trade time. The historical PM spread proxy uses the correspondingly delayed Kalshi raw spread. Fixed model weights, independence point products and joint-stressed bounds retain the same implementation.

Zero extra lag must reproduce the baseline **exactly**, including row identities, fair points/stressed bounds, price/size/fees, trade/settlement clocks, outcomes, guards, risk multiplier, canonical buckets and source metadata. Input and imported pricing-code hashes are verified, and the new script records its source identity. The baseline maker fee is copied unchanged for every extra-lag variant; this is a source-information experiment, not a fee experiment.

## Coverage and comparisons

The sensitivity evaluates every baseline Kalshi-priced eligible print. July 1 has 35,437 scope-eligible prints, of which 35,237 already have usable Kalshi history; the inherited 200 source-unavailable prints are retained as explicit exclusions and are not silently described as priced. The original four models have 129,026 total rows. July 15 has all 1,202 eligible prints Kalshi-priced and 2,378 model rows. No new print/ticket cap is introduced.

Each lag retains its own available per-model rows and missing-leg reasons. The paired comparison uses the intersection of **all four models at all four lags**, preventing apparent performance changes from being mistaken for pricing changes when source coverage shrinks. Separate available-cohort ledgers remain useful coverage diagnostics, but their different model populations are not paired comparisons. Missing-leg occurrences and missing unique prints are distinguished.

Both funded and unlimited replays retain the .003-per-combo point-edge hurdle and all input quote guards/risk multipliers. Funded replays retain $10k initial capital, $100 underlying/$100 combo/$250 fixture limits and the actual settlement-time cash release. Eventual known P&L is attributed at trade time only for retrospective performance. Fair-value changes are quantity-weighted, and threshold acceptance/rejection changes are measured before portfolio allocation; the actual funded selection can differ additionally because earlier changed fills consume risk.

## Interpretation limits

This tests extra delay in the **archived Kalshi and PM sources together**, not the missing Pinnacle feed's nominal 30-second delay. It cannot establish the health, upstream refresh contract, sharpness or adverse selection of that provider. Minute candles and PM history fidelity do not resolve every intraminute quote change or RFQ response latency. Additional delay can occasionally improve realized P&L by changing a few shared outcome exposures; that is not proof stale information is advantageous.

The two dates are development diagnostics. Fee-effective-date and ordinary/exceptional-payoff verification limitations, historical PM spread/depth assumptions, and hypothetical observed-print execution assumptions are unchanged. Do not optimize delay or risk on these outcomes. The larger frozen sample and prospective healthy-source shadow context are still required.

Four tests pass: delayed as-of boundaries and query coverage, preservation of latest inactive state, unchanged trade/maker-fee/outcome/risk inputs, and a fee-schedule boundary where actual trade time must be used despite older source states. Results and full portfolio/source-context artifacts are under `runs/mlb_timing_sensitivity_20260907/{july1,july15}/`.

## Completed July 1 / July 15 results

Both runs passed exact zero-extra-lag parity: **129,026 model rows on July 1**, **2,378 on July 15**. The all-model/all-lag intersections contain **31,194** and **375** prints respectively. These are fixed comparison cohorts, not a newly imposed sample cap. The original zero-lag four-model intersections were 31,263 and 392; removing early source-boundary cases changes the funded baseline portfolio too, so the paired figures below must not be compared directly to earlier full-coverage funded results.

| Date | Model | 0s extra: unlimited P&L | 30s extra: unlimited P&L | 120s extra: unlimited P&L | 30s quantity-weighted absolute fair change |
|---|---|---:|---:|---:|---:|
| July 1 | Kalshi | $18,893 | $18,973 | $18,667 | 0.00401c |
| July 1 | Polymarket | $154,575 | $152,612 | $149,802 | 0.00321c |
| July 1 | Equal blend | $21,707 | $20,832 | $21,436 | 0.00357c |
| July 1 | PM75 blend | $84,620 | $82,853 | $83,746 | 0.00339c |
| July 15 | Kalshi | −$3,191 | −$3,208 | −$3,436 | 0.03176c |
| July 15 | Polymarket | −$2,511 | −$2,511 | −$2,605 | 0.01762c |
| July 15 | Equal blend | −$2,618 | −$2,575 | −$2,610 | 0.02384c |
| July 15 | PM75 blend | −$2,487 | −$2,487 | −$2,612 | 0.02076c |

On July 1, an extra 30 seconds changes threshold decisions on 7 Kalshi prints, 22 PM prints, 4 equal-blend prints and 22 PM75 prints, out of the 31,194 common prints. July 15 changes only 1, 0, 2 and 0 respectively. These threshold counts precede portfolio capacity checks.

On the same July 1 common cohort, funded 0→30-second P&L is Kalshi $13.38→$17.61, PM $245.44→$242.13, equal $51.02→$51.02, PM75 $183.22→$174.67. July 15 funded results are unchanged across the entire lag grid: Kalshi −$28.43, PM −$31.56, equal +$5.48, PM75 +$3.99. All selected eventual outcomes are known in these paired comparisons.

Coverage falls at the longest lag: July 1 available Kalshi rows 35,237→35,074 and each two-exchange model 31,263→31,194; July 15 Kalshi 1,202→1,164 and each two-exchange model 392→375. The historical captures sometimes have no sufficiently early state at their beginning. Those exclusions are a data-coverage consequence, not evidence of live adverse selection.

The bounded finding is that the extra 30 seconds generally makes small probability changes in these retained exchange histories. It does **not** explain the large difference between July 1 and July 15 outcomes or the selection changes caused by restoring the missing NYM–PHI fixture. Longer extra lag changes more selections but the outcome response is not monotone across models. No conclusion about Pinnacle's missing feed follows from this experiment.

Results: [July 1](../runs/mlb_timing_sensitivity_20260907/july1/REPORT.md), [July 15](../runs/mlb_timing_sensitivity_20260907/july15/REPORT.md). Each directory retains source context, four compatible opportunity files, sixteen portfolio ledgers and a verification record. No source weights or delay settings were promoted to live configuration.

# CFB fee and trade accounting audit — September 7, 2026

The losses are present **before fees**. The reviewed YES/NO direction, contract units, maker coefficient, and settlement P&L agree with the primary documentation and the saved executions. No fee-code change is justified by this audit. This does **not** validate the estimated probabilities or the assumption that our quote would have captured a public trade.

These results use the frozen settlement-refreshed reports **before the new $50 YES-premium filter**. The executions stay fixed for the gross-versus-net comparison; removing fees would also change selection in a separate strategy rerun.

| Entry / model, unconstrained | Fills | Known gross P&L | Fees on known outcomes | Known net P&L |
|---|---:|---:|---:|---:|
| Point / Kalshi | 12,915 | −$460,765.85 | $24,181.32 | −$484,947.17 |
| Point / Pinnacle | 3,980 | −$29,143.07 | $4,964.04 | −$34,107.11 |
| Point / blend | 1,880 | −$45,657.31 | $2,470.75 | −$48,128.06 |
| Point / stronger Pinnacle | 2,702 | −$42,610.29 | $3,437.93 | −$46,048.22 |
| Stressed / Kalshi | 123 | −$120,725.01 | $488.64 | −$121,213.65 |

Models above have different eligible coverage; these rows are accounting reconciliations, not a controlled model ranking. The common-cohort Kalshi point result also remains negative before fees: −$19,606.16 gross, $1,562.01 fees, −$21,168.16 net. The constrained blend is −$362.89 gross minus $33.85 fees = −$396.73 net. Unresolved positions' fees are recorded separately in the machine output; unknown outcomes are not counted as zero-P&L completed trades.

## Fee coefficients and units

Kalshi's July 7 schedule gives a general taker coefficient of `0.07`, a maker base coefficient of `0.0175`, and a combo maker multiplier of **2**, excluding its specified uncorrelated NFL exception. Thus the CFB combo maker coefficient is `0.035`, not `0.0175`. There is no settlement fee. The PDF's formula defines price in dollars and describes balance alignment to $0.0001; its illustrative table still displays whole-cent amounts, so that table must not override the formula or precise API rounding documentation. [Official fee schedule, pages 1–2 and 7](https://kalshi.com/docs/kalshi-fee-schedule.pdf).

Native cached `KXMVECROSSCATEGORY-SHARD1` fee-change metadata independently records `quadratic_with_combo_maker_fees`, API multiplier `1`, effective `2026-08-20T09:05:00Z`. That API multiplier multiplies the fee-type coefficient; multiplying by the PDF's combo factor again would double-charge. The reviewed zero-series has separate metadata. Historical code rejects other unreviewed series rather than applying this coefficient to arbitrary combos.

Polymarket's current sports taker fee is `q * 0.05 * p * (1-p)`; makers pay no trading fee. Fees use five decimal places and the market's fee parameters must be read. The forward module does this through `feeSchedule`, rather than assuming every token's fee is identical. Its `HALF_UP` tie convention is explicitly awaiting actual-fill validation because the public page does not specify tie-breaking. [Official Polymarket fees](https://docs.polymarket.com/trading/fees).

At `p = 0.50`, the smooth fee per contract is **0.875 cents** for a CFB combo maker, **1.75 cents** for a standard Kalshi leg taker, and **1.25 cents** for a Polymarket sports taker. Those are not 3.5%, 7%, and 5% of payout notional. There is no factor-of-100 error in the saved calculations.

## Direction, collateral, and edge

Let `q` be $1-payout contracts, `p` the customer's YES price, `f` the estimated YES probability, `y` the eventual YES settlement, and `F` the maker's dollar fee. Our simulated position is the opposite of the YES taker:

```
NO purchase price       = 1 - p
cash committed          = q * (1 - p) + F
settlement payout       = q * (1 - y)
net P&L                 = q * (p - y) - F
model expected net edge = q * (p - f) - F
```

The exact identity explains why small YES premium can conceal large maker losses. At a 4-cent YES price, $50 YES premium represents 1,250 contracts, requiring $1,200 NO principal plus a $1.68 smooth maker fee. A $50 premium filter therefore complements the existing loss limits; it does not replace them.

The official normalized direction fields mean `yes ≡ bid` and `no ≡ ask`; selling NO and buying YES have the same directional exposure. Every one of the 61,205 retained YES prints agrees across normalized and legacy side fields, and all are explicitly non-block trades. All 61,856 cohort prints have YES+NO prices summing exactly to $1. [Official direction semantics](https://docs.kalshi.com/getting_started/order_direction).

Single-leg taker-fee expansion widens the interval used to assess plausible fair probabilities. It is **not** a cash payment by our combo strategy. Combo maker fees are subtracted once in edge and once in the separate realized-P&L calculation; those are two measures of the same trade, not two deductions from a cash balance. No leg trades are simulated. Charging hypothetical hedging fees as realized costs would require an explicit hedge execution model.

## Rounding and reconciliation

The current Kalshi API specifies six-decimal upward rounding of model fees, signed-revenue balance alignment, and a per-order rounding accumulator. Direct-member balances align to $0.0001; non-direct balances to $0.01. `fees.kalshi_fill_fee` implements those steps. [Official rounding mechanics](https://docs.kalshi.com/getting_started/fee_rounding).

Across every saved fill in all 18 nonempty report/model/regime groups, historical `pricing.total_fee` agrees with the current direct-member calculation with a fresh accumulator. The largest difference between independently reconstructed and recorded per-fill P&L is $0.0000000000026. No unexplained fees or P&L errors were found. Using non-direct cent precision with a fresh accumulator would add only $9.48 across all 1,880 blend fills or $64.41 across all 12,915 Kalshi fills, before any per-order rebates. This cannot explain the losses.

Private order identities and accumulator states are unavailable in this public-tape replay; this is a justified standalone-fill convention, not a reconstruction of another trader's account statement. All inspected known settlements are binary. The ledger's generic upward conversion of settlement payouts should be made explicit before supporting sub-grid fractional settlements, but that unexercised path does not explain this dataset.

## What still requires shadow/live verification

RFQ participant role alone does not guarantee the eventual liquidity role. REST `post_only` defaults false; the documented flag cancels the quoter's order if it would take liquidity. For maker-only behavior, explicitly set it and reconcile executions against private `is_taker` and `fee_cost`. REST `no_bid` is our NO purchase price, not the customer's YES price. FIX direction and units differ by message: submitted quote prices use cents, quote notifications dollars, and accepting BUY takes the maker's NO quote. [REST quote fields](https://docs.kalshi.com/api-reference/communications/create-quote), [FIX RFQ semantics](https://docs.kalshi.com/fix/rfq-messages), [private fill fields](https://docs.kalshi.com/api-reference/portfolio/get-fills).

The public tape contains completed transactions, not our quote acceptance probability, queue position, creator behavior, or private fee rebates. The appropriate next diagnosis is conditional probability calibration, stale or incoherent reference prices, repeated fixture exposure, and size concentration. Changing fees cannot repair the negative gross results. For concrete loss examples, see [the full-week forensic note](CFB_FULL_WEEK_DIAGNOSTICS.md).

## Reproduction and evidence

Run `python3 runs/cfb_performance_audit_20260907/fee_audit.py`. It only reads frozen reports and writes independent audit artifacts:

- `runs/cfb_performance_audit_20260907/fee_accounting_metrics.json` and `.csv`: all 18 reconciliations, known/unresolved fees, model edge, rounding sensitivities, original input hashes, and zero detected errors.
- `runs/cfb_performance_audit_20260907/fee_source_evidence.json`: official source URLs, complete cached native fee responses with hashes, side counts, and complement checks.
- Inputs: `runs/cfb_full_week_20260907/backtests_settlement_refreshed/` and the unchanged cohort metadata. No paid API requests or trading operations were performed.

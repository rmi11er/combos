# Liquidity-dependent quote compensation

The user proposes charging more edge when the underlying markets across Kalshi, Polymarket and Pinnacle are thin or wide. This may be especially relevant to CFB, where poor selection could reflect noisy fair estimates or insufficient compensation for uncertainty. This is a proposed explanation for previous losses, not an established finding.

The existing model already weights fair values by spread and depth and propagates fee-expanded uncertainty intervals. Relative weighting alone misses the case where all sources are thin: their normalized weights can remain identical while absolute information quality deteriorates. The new independent research component `src/combos/liquidity_reserve.py` measures absolute depth relative to proposed payout size. Configuration is in `config/liquidity_reserve_research.json`. Neither the running frozen batches nor live pricing import it.

For leg i and source v, let w be the recorded normalized fair weight, s the fee-expanded interval width in cents, D the minimum of its two-sided payout capacities, and q the proposed combo payout contracts. Define an unfitted uncertainty radius in probability units:

`r_i = sum_v w_iv * max(s_iv, 1) / 200 * (1 + beta * sqrt(q / D_iv))`.

The fixed comparisons are the unchanged baseline, a width-only floor (beta=0), and a width/depth floor (beta=1). No coefficient is selected from observed P&L. For Pinnacle the width represents its paired-odds margin band, not an exchange spread or an additional taker fee. Its capacity must be verified USD stake limits converted to payout units. Exchange depth is actual top-of-book size in payout units. These heterogeneous measures are proxies, not interchangeable executable hedge liquidity. q is a conservative size proxy, not a derivative-based hedge requirement; a future joint engine can provide marginal exposures and depth curves.

Each selected-leg interval becomes the union of its existing interval and `[p_i-r_i, p_i+r_i]`, clipped to [0,1]. Point fair stays unchanged. The same dependence engine recomputes the combo upper bound. The additional liquidity reserve is the difference between the new and old stressed upper bounds. Quote construction must replace the original stressed upper or add only this difference, never add both full bounds. Thus existing spread/fee uncertainty receives full credit, and wider intervals or thinner depth cannot reduce the required upper bound under the same model.

Maker cash fees and the commercial minimum edge remain separate. Reserves are pricing allowances, not realized expenses subtracted from settlement P&L. Very poor liquidity may leave no feasible quote; a mathematical interval capped at one is not permission to trade. Existing mapping, timing, pregame, creator, correlation, and capital/risk checks continue to apply. The caller must supply causally validated source context; this leaf transform does not validate raw feeds or authorize live execution. Snapshot age and venue disagreement remain separate existing inputs; do not use last price-change time as snapshot staleness.

Historical missing exchange depth requires an explicit assumption reference. Pinnacle limits cannot be imputed. Historical equal-Kalshi/shared-fixed-depth scenarios can show sensitivity, but cannot identify real liquidity effects when measured depth is absent. A live adapter must prohibit every imputed source. No live adapter is enabled here.

## Evaluation before promotion

Compare fixed variants on the same complete eligible population, retaining all rejection reasons. Cross liquidity/spread bins with sport, market family, leg count, quote size, time to start, source agreement and actual/imputed data status. Evaluate calibration, subsequent price markouts and net seller P&L, with fixture/time clustering, held-out dates, and both funded and unlimited ledgers. Preserve the current 0.3c-per-combo baseline and sell-every-print comparison. Report coverage: thinning a sample can make headline P&L appear better without improving the estimator.

When historical depth is unavailable, test observed spread effects separately and label depth scenarios. Forward logs should save source bid/ask ladders where available, effective fees, Pinnacle limits, snapshot/availability clocks, fair weights, old/new intervals, reserve decomposition, intended size, quote lifecycle and fills. Public prints can test selection at recorded prices; they cannot establish acceptance of a newly widened quote. Shadow quote diagnostics and eventual live acceptance measurements are required to evaluate that tradeoff.

The source-consensus hypothesis and liquidity reserve are complementary: agreement may shift our point estimate toward Pinnacle/Polymarket while weak absolute liquidity still requires more compensation. Agreement between thin sources does not remove uncertainty.

## Completed opposite-moneyline proxy experiment

The user-authorized no-depth test is complete in [the experiment report](../runs/opposite_moneyline_20260907/REPORT.md). It evaluates all covered retained moneyline-only prints: 16,361 CFB and 16,421 on the complete September 5 MLB day. Opposing acquisition asks form a synthetic fee-expanded band; PM paired archived points provide a separately labeled complement-inconsistency sensitivity. Point fairs and maker cash fees remain unchanged. Native spread, opposite spread, point-only, sell-all and correlation-preserving floor comparisons retain funded/unlimited ledgers and coverage diagnostics.

The full half-width charge removes nearly all Kalshi-selected trades and does not establish a profitable CFB rule. CFB point-selection losses concentrate in the narrowest raw-width bucket, so these moneylines do not support a simple wide-market explanation for earlier losses. This does not test actual depth or other market families, and no live parameter was selected from the results.

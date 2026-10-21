# July spread, compensation and realized outcomes

The pooled study covers 365,107 matched prints with opposite-moneyline spread features across all 15 priced July dates, representing $88,955,640.24 payout face. This is a feature-covered subset of the 467,583 priced prints. It retains all covered trades without an edge, capital or premium filter. July 13 remains a missing identity date; no August outcome was loaded.

The plotted decomposition is price minus fair minus maker fee (compensation), plus fair minus settlement (residual), equaling realized net. The same prints and quantity weights are used for all three components. Overall realized net is $238,322.06, or 0.26791c/contract. Modeled compensation remains negative on average for all source models.

## Compensation depends on both spread and the fair model

Coefficients below are cents of additional compensation per contract for each 1c increase in summed underlying spread, controlling for combo traded price and leg count:

| Fair model | Raw spread coefficient | Fixture-omission range | Fee-expanded coefficient | Fixture-omission range |
|---|---:|---:|---:|---:|
| Kalshi | −0.05041 | [−0.05635, −0.04783] | −0.04838 | [−0.05431, −0.04582] |
| Equal blend | +0.00306 | [−0.00162, +0.00571] | +0.00487 | [+0.00027, +0.00802] |
| PM75 | +0.02965 | [+0.02534, +0.03234] | +0.03135 | [+0.02719, +0.03480] |
| Polymarket | +0.05614 | [+0.05181, +0.05914] | +0.05773 | [+0.05369, +0.06149] |

Without price/leg controls, compensation rises with width for all models. Controls expose a material distinction: PM-relative customer compensation still rises, while K-relative compensation falls. This supports testing margins conditional on both liquidity and fair-model disagreement. It does not prove book width causes toxicity or identify how much more a customer would pay for our quote. Price is itself part of compensation, and these associations can be mechanical/endogenous.

Raw-spread adjusted realized net has coefficient +0.48755, with positive fixture-omission range [+0.04739,+0.83357]. The fee-expanded version has coefficient +0.43443 but omission range [−0.05615,+0.72249], crossing zero. Under PM fair, residual slope also crosses zero under fixture omission for both measures. Thus the compensation relationship is more stable than a claim about realized profit or calibration toxicity.

The useful next candidate is a bounded spread-dependent margin tested jointly with PM-heavy fair, rather than an outright wide-market rejection. The coefficient is not a ready-to-use surcharge: observed trades already include customer-paid compensation, and raising our quote changes acceptance. Retain a zero-spread-surcharge benchmark; choose and freeze any slope on development data before held-out testing. No live parameter changed.

## Verification and limitations

All 8 model/measure records and 16 regressions passed checks for weighted bin totals, shared cohorts, compensation-plus-residual identities and regression coefficient identities. Input, dependency and workflow hashes were verified; both plots were visually reviewed. Each regression includes 378 fixture-deletion refits. These are influence ranges, not confidence intervals or causal estimates. No standard errors or p-values are claimed.

The workflow uses pooled sufficient statistics, not averages of daily coefficients. The generic validation-purge flag remains provisional because July 13 lacks priced identities; there are no validation rows in this July-only run. Historical spread proxies are not observed live depth, and fee applicability remains unverified. Pinnacle is absent.

[Raw spread plot](../runs/morning_research_20260908/july_pooled_spread/development_common_raw.png) · [Fee-expanded plot](../runs/morning_research_20260908/july_pooled_spread/development_common_fee_expanded.png) · [Regression verification](../runs/morning_research_20260908/july_pooled_spread_audit/verification.json)

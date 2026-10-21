# July 11 native MLB universe audit

The independent full-row audit passes. The broad seller counterfactual makes **$1,029,408.4145 net**, but removing all prints involving July 11 AZ–LAD turns it into **−$459,143.4470**. The profitable day is materially fixture-dependent and is not evidence that the paused selected-model pipeline would earn this amount.

## Accounting and coverage

Checked all **230,773 native pure-MLB prints**, retaining **203,704 YES-taker prints** and excluding 27,069 NO-taker prints consistently with the seller convention. Verified the complete contiguous census source manifests and native metadata joins, unique trade IDs, quantity/price complements, finalized settlement values/timestamps, leg counts and native fixture-token classifications. No sample or model-pricing availability filter was used.

| Native YES-taker metric | Exact amount |
|---|---:|
| YES premium | $8,044,842.715120 |
| Payout face notional | $129,080,425.30 |
| Native settlement obligation | $6,825,132.817500 |
| Gross seller P&L | $1,219,709.897620 |
| Modeled maker fees | $190,301.483120 |
| Net seller P&L | $1,029,408.414500 |

Every row independently reproduces quadratic maker fee arithmetic with coefficient .035, micro-dollar ceiling and direct-account .0001 cash precision. Fees match archived row values exactly and are deducted once. Archived floating-point P&L and summary totals reconcile within the declared sub-$0.0001 tolerances. All marginal cut totals reconcile exactly using Decimal arithmetic.

Native outcomes comprise 176,799 YES prints settling at zero, 26,904 at one, and **one at 0.75**. The fractional payout is retained; no binary outcome is substituted. No market/event fixture-token discrepancies were found in this day's full-row audit. Settlement is known retrospectively and not used for selection.

## Marginal cuts

These are overlapping dimensions, not mutually exclusive strategies.

| Cut | Prints | Net P&L |
|---|---:|---:|
| 2 legs | 49,563 | $247,159.72 |
| 3 legs | 37,018 | $179,375.77 |
| 4 legs | 28,733 | $92,736.86 |
| 5+ legs | 88,390 | $510,136.06 |
| Distinct fixtures | 153,789 | $602,821.89 |
| Contains same-game legs | 49,915 | $426,586.52 |
| Full-game core | 153,620 | $655,940.31 |
| Known player prop | 41,758 | $338,509.47 |
| Other family | 8,326 | $34,958.63 |
| Pregame schedule proxy | 83,558 | $780,398.95 |
| After schedule proxy | 120,146 | $249,009.46 |

Premium buckets ≤$10/$10–50/$50–250/>$250 earn $190,929/$324,864/$364,772/$148,844 respectively. Positive marginal categories do not establish robustness because they share game outcomes.

## Fixture influence

Largest positive overlapping fixture memberships are AZ–LAD $1,488,551.86, CLE–MIA $888,329.32 and TOR–SD $635,494.11. Removing those memberships leaves −$459,143.45, +$141,079.10 and +$393,914.31 respectively. These omissions remove every print touching the fixture, without reallocating trades; overlapping membership contributions must not be summed as additive attribution. Largest negative memberships are ATH–CWS (−$230,548.56), LAA–MIN (−$142,922.72) and next-day NYY–WSH (−$109,506.54).

## Interpretation and artifacts

This is unlimited observed-public-price seller accounting, not executed RFQ fills, a funded return or a model-selection result. Face notional is maximum contract payout quantity, not customer winnings. Historical maker-fee effective dates and direct-account cash assumptions remain explicitly unverified scenarios. Phase uses the scheduled-time proxy, not a verified actual first pitch. All-Star identity failure affects subsequent cross-venue acquisition, not this complete native benchmark; see [identity review](MLB_JULY11_IDENTITY_REVIEW.md).

[Full verification](../runs/morning_research_20260908/universe_july11_audit/verification.json) includes exact totals, all cuts, fixture omissions, source hashes and maximum arithmetic differences. [Independent audit script](../runs/morning_research_20260908/universe_july11_audit/verify.py) imports no production pricing/classification code. No provider requests, frozen source changes or August outcome inspection were performed.

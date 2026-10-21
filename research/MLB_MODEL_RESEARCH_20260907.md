# MLB historical models, portfolio comparisons and launch fixes

September 7, 2026. The MLB tape and exchange benchmarks are now substantial. **The requested Kalshi/Polymarket/Pinnacle blend remains unavailable because the current key is denied Pinnacle baseball history.** The charts below explicitly show exchange-only benchmarks. They do not substitute another book for Pinnacle or label missing data as zero model fills.

## Actual data and scope

The retained August 31–September 6 universe contains **318,536 pure-MLB combo prints**, drawn from the complete September 5 census and fully paginated sampled cells on the other days. The underlying source scan covered 1,565,981 combo prints. All 1,825 native underlying definitions required by the broader full-game pregame candidate cohort were recovered.

For model pricing, we retained distinct-fixture, full-game moneyline and half-point run-line/total combinations, 2–4 legs, YES-taker public prints, at least 60 seconds before the earliest originally scheduled start. **26,417 prints** satisfy that scope across the retained week; every one has a Kalshi historical fair, and **24,646** also have a matched historical Polymarket price. The acquisition finished all **1,155 Kalshi candle jobs and 935 Polymarket token-history jobs** successfully, after repairing six rate-limited requests. No underlying or fixture sample cap remains within this scope.

September 5 is the only complete observed calendar day, so it is the funded portfolio evaluation day. Its source-specific coverage is 23,456 Kalshi-priced prints and 21,880 Polymarket-priced prints. The main paired comparison reruns both portfolios on the **same 21,880 prints**. It does not merely filter fills from portfolios that traded different off-intersection opportunities.

The original 23,713-print native pregame 2–4-leg distinct-game benchmark used `trade < scheduled start`; the modeled 23,456-print scope additionally removes the final 60 seconds. This explains that coverage difference without a new game sample.

In `replay/coverage.json`, `priced_by_model` counts prints. The detailed `pricing_exclusions` counters count failed leg occurrences within combo/model evaluations, so several missing legs can contribute several reasons for one unpriced print. Across the retained modeled week, Kalshi has zero unpriced prints, Polymarket has 1,771, and each Pinnacle-dependent model lacks all 26,417. These are coverage failures, not rejected quote or fill counts.

## Results on the common exchange cohort

All P&L is hypothetical selling at somebody else's observed YES execution price, after combo maker fees. Known eventual settlement P&L is attributed to trade time. The constrained ledger releases spendable cash only at the recorded settlement time. No RFQ response wins, partial fills, creator history or quote queue position are inferred.

| Strategy on the common 21,880-print cohort | Selected prints | Known net P&L | Loose final P&L bounds including unknown settlements |
|---|---:|---:|---:|
| Sell every priced print, unlimited | 21,880 | +$419,528.94 | +$394,960.52 to +$424,525.62 |
| Kalshi point selection, unlimited | 755 | +$39,680.72 | +$33,020.91 to +$42,001.49 |
| Polymarket point selection, unlimited | 2,183 | +$35,703.05 | +$31,819.12 to +$36,766.91 |
| Kalshi point selection, constrained | 96 | +$148.99 | −$123.56 to +$257.14 |
| Polymarket point selection, constrained | 128 | −$44.75 | −$314.77 to +$53.27 |

The point-entry rule is the existing **minimum 0.3 cents net expected edge per contract** at the observed print, with no premium cap. The constrained portfolio uses $10,000 capital, $100 per canonical underlying and combo, and $250 per fixture. Opposing moneyline contracts from the same fixture share the same gross-risk bucket; no cross-ticket hedge credit is invented. Each leg-count facet attributes fills from this one portfolio, without granting each subgroup an additional $10,000.

Peak committed cash is only **$1,334 for Kalshi and $1,522 for Polymarket** in the constrained common-cohort runs. The dominant additional rejection is the $100 underlying limit: 645 Kalshi and 2,010 Polymarket point-qualified prints fail that check. The few `capital_exhausted` reasons are requests whose individual full size exceeds available cash, not evidence that the account's aggregate capital was deployed. Unlimited paths require approximately **$215k and $417k** minimum starting funding, respectively. Their dollar profits cannot be scaled into a funded $10,000 result without a new sizing simulation.

There is also a structural capital-utilization constraint: the current ledger charges a combo's full NO cash to every constituent fixture. With $250 per fixture and at least two distinct fixtures per combo, total simultaneous cash is bounded by `number of fixture buckets × $250 / 2`, before the tighter underlying/size checks. Even all 46 fixture identities present in September 5's priced cohort provide only a $5,750 loose ceiling. For an isolated 16-game NFL slate, that ceiling is $2,000. Deploying the full $10,000 is therefore not a feasible target under those conditions. This deserves an explicit risk-policy review; no limit was raised here.

Daily Sharpe and daily variance are **N/A** in the legends because there is only one complete day. Incomplete sampled days are not turned into zero-activity calendar days to manufacture a multi-day statistic.

Source-specific portfolios also exist: Kalshi selects 947 unlimited prints for +$41,594.96 known P&L, or 123 constrained prints for −$27.13. Polymarket's source-specific cohort already equals the common intersection. The change in constrained Kalshi results is a reminder that changing available opportunities changes capital and concentration allocation; compare models on the common cohort first.

## Plots and cuts

- [Constrained portfolios on their own vertical scale](../runs/mlb_historical_20260907/common_model_report/constrained.png).
- [Unlimited portfolios, with edge, premium and committed cash](../runs/mlb_historical_20260907/common_model_report/unconstrained.png).
- [Kalshi: every priced print versus selections, split into 2, 3 and 4 legs](../runs/mlb_historical_20260907/common_model_report/kalshi_selection.png).
- [Polymarket: the same comparison](../runs/mlb_historical_20260907/common_model_report/polymarket_selection.png).
- [Entire MLB universe, including 5+ legs and same-game combinations](../runs/mlb_historical_20260907/universe_report/census_sep5.png).

Every chart has a corresponding SVG. `strata.json` provides the selected and overall contributions by leg count, customer premium, moneyline-only versus line/total combinations, and time to start. These are descriptive cuts of the same portfolios, not separately optimized strategies.

For unlimited common-cohort selections:

| Customer YES premium | Kalshi known P&L | Polymarket known P&L |
|---|---:|---:|
| At most $10 | +$1,077.24 | +$745.74 |
| Above $10 through $50 | +$3,546.84 | −$1,711.98 |
| Above $50 | +$35,056.63 | +$36,669.29 |

The larger tickets dominate these selected dollar profits. Removing them is a different sizing/cohort experiment, not proof that large flow is intrinsically better. The small constrained results also remain sensitive to unknown outcomes.

The complete-day entire-universe benchmark contains **262,584 YES-taker prints** and has **+$1,642,760.86** known seller P&L, bounded at approximately **+$1.60m to +$1.65m** including unknown outcomes. One shared fixture, Milwaukee–Cincinnati, appears in prints contributing +$1.033m; removing every such combo leaves +$609,840. The [universe report](MLB_UNIVERSE_PERFORMANCE_20260907.md) supplies all-leg/phase/prop cuts, concentration and full exposure accounting. This broad population is not the control for a model restricted to pregame 2–4 distinct-game combos.

## Fair values, fee and timing conventions

Kalshi candles and Polymarket history points both have the previously declared 60-second historical publication allowance; future records cannot enter the fair. Missing PM depth is imputed from the same historical Kalshi depth scenario, while its missing historical bid/ask spread uses the corresponding Kalshi raw spread. PM history points are not certified book midpoints. These are historical-only hypotheses; forward pricing still requires real depth.

The [MLB mapping review](MLB_EXCHANGE_MAPPING_REVIEW.md) checks native team ordering, exact timezone-aware schedule, doubleheaders, full-game text, line, selected side and fee metadata. All 916 comparable binary outcome checks agree, with 19 nonbinary/unresolved PM prices excluded from that corroboration. Outcome agreement did not select the mappings.

Kalshi's public fee-change records retrieved for this study establish the 0.5 individual-leg multiplier effective August 7 for GAME, SPREAD and TOTAL, supporting the **0.035 taker parameter** over this retained week. The combo shard's historical record establishes its combo-maker fee type and multiplier effective August 20. Raw evidence is in `exchange/series/changes_*.json`. This corroborates the parameters used; no fee adjustment was made after seeing P&L. Most matched PM markets report **0.05**, while 12 report **0.03**; the individual market schedule is preserved. PM historical effective dates remain unverified.

The replay's optional `--pinnacle-bundle` supplies native, reviewed per-leg YES/NO histories with explicit complete request-coverage intervals and mapping references. With such data, it evaluates Pinnacle-only, the existing three-source spread/depth blend, and the stronger-Pinnacle variant through the shared pricing implementation. The configured 30-second archive-delay convention is retained and recorded. The interface is not a substitute for the missing entitlement, verified native data or a correct MLB mapping. Current outputs have **zero available three-source evaluations**, explicitly labeled an access/coverage issue.

Normal-completed-game mapping does not certify cancellation, postponement, shortened-game or push basis. Original schedule text is an historical proxy, not proof of the schedule actually available to our process at every decision. Model inputs are causally indexed by their declared publication conventions, but complete point-in-time feed health and schedule receipts are not present. These limitations also apply to interpreting the positive outcomes.

## OddsPapi access: documentation versus the actual response

Both the [English](https://oddspapi.io/en/docs/get-historical-odds) and [US](https://oddspapi.io/us/docs/get-historical-odds) v4 pages describe the same endpoint, historical availability since January 2026, and a five-second cooldown. The [quota page](https://oddspapi.io/en/docs/requests-and-quota) says historical calls are always free and never increment monthly usage. It states no separate historical request allowance.

A fresh four-call check (account, both bookmaker history variants, account) consumed **zero quota**. It returned:

- `pinnacle`: HTTP 403, restricted bookmaker.
- `pinnacle+30`: HTTP 403, no access to sport 13, baseball.

The documentation's free accounting and the API's access denial are separate observations. This study does not establish that a paid upgrade is necessary. OddsPapi must clarify or enable access, or another historical source must be provided. Evidence is retained in `runs/mlb_research_20260907/access_recheck/` with credentials redacted. No subscription mutation or additional entitlement probe was made after the repeated denial.

## Runtime work completed in parallel

The [runtime optimization](RUNTIME_THROUGHPUT.md) preserves every input envelope, raw/decision log, creator evidence ordering, atomic checkpoint and maintenance event. All 185,443 archived inputs reproduce exactly the same 69,093 decisions, creator transitions and durable state; both benchmark orders show approximately fivefold faster processing.

The subsequent real 100-second capture recorded 85,147 RFQs. Lag p95 fell from 4.687 seconds to 0.189 seconds; only 1/965 basic-scope RFQs exceeded the unchanged two-second limit, versus 307/946 previously. Four Pinnacle requests moved reconciled usage from 23 to 27. No orders were sent. Both exchanges supplied actual two-sided depth for all 454 configured keys, but Pinnacle pricing blocks still correctly prevent three-source quoting.

The [Pinnacle review](PINNACLE_MAPPING_REVIEW.md) fixed false rejection of 45 benign native identifier revisions and reviewed 65 full-game spreads, 83 totals and 32 moneylines. Moneylines need tie-basis handling; exceptional settlement, stake currency and effective information time remain unresolved before those mappings can become executable.

There is no evidence here that the 30-second delay broadly explains adverse selection. It remains a measured sensitivity and data-quality concern, not the assumed cause of the CFB losses. A successful MLB three-source comparison requires the missing history before that hypothesis can be tested directly.

## Reproduction and expansion

The [larger validation run](MLB_EXPANSION_20260907.md) is now collecting 31 complete July/August dates and automatically running fixed entry/risk comparisons as each date becomes complete. It includes the user's sell-every-print benchmark and defers risk-limit selection to the larger dataset. Separate NFL playoff acquisition is also underway. These running jobs are not yet completed multiweek results.

The follow-up [source disagreement research log](SOURCE_DISAGREEMENT_RESEARCH.md) tests the user's Polymarket sharpness hypothesis on paired historical prints, decomposes selections and records the multiweek, sport-specific validation plan. The first complete-day result is mixed and does not change production source weights.

```sh
.venv/bin/python scripts/mlb_native_cohort.py --help
.venv/bin/python scripts/mlb_exchange_acquire.py
.venv/bin/python scripts/mlb_model_replay.py
.venv/bin/python scripts/mlb_model_report.py
.venv/bin/python scripts/mlb_model_report.py --common-only --out runs/mlb_historical_20260907/common_model_report
.venv/bin/python scripts/mlb_universe_report.py
.venv/bin/python -m pytest -q
```

Acquisition, replay and reports retain raw responses, source coverage, mapping reviews, input/code hashes and full decision ledgers. The model-report command accepts a complete census `--date`; the current replay/cohort runner is explicitly this retained week. `scripts/mlb_public_day_acquire.py` provides resumable, cutoff-aware full-day collection and an outcome-blind expansion plan across July/August/September. That older multiweek download has not been performed, and this one complete day must not be described as the requested July-onward validation.

The complete repository suite passes **273 tests**, including the new runtime equivalence, matcher, historical timing, shared-risk, common-cohort portfolio and reporting checks. Final plots were rendered and visually inspected.

After historical access is resolved, use the saved complete-date plan, collect every eligible leg of those dates, and freeze the three-source weighting and selection rules before inspecting their results. Report both common-source and incremental coverage and retain the present limits and no-premium-cap comparison. Treat same-game pricing as a separately specified joint model. The current positive unlimited exchange benchmarks justify continued investigation; they do not validate live RFQ execution profitability.

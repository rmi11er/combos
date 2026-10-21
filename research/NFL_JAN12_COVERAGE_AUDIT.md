# NFL January 12 causal coverage audit

Zero common prints is justified for the retained four-model cohort: all 265 eligible prints require at least one divisional-round Polymarket moneyline that the cached catalog says was created on January 13. No mapping or historical query-bound error was found. Completing acquisition for all ten fixtures means the requested histories were retrieved successfully; it does not imply those markets existed on every earlier trade date.

The eligible prints total **$9,811.272 YES premium and $46,980 payout notional**. The pipeline records the first failing leg/source: 264 prints ($9,773.122/$46,871) report missing prior Polymarket state and one ($38.15/$109) reports missing prior Kalshi state. Checking every leg and venue independently shows **all 265 lack Polymarket state; only one also lacks Kalshi state**.

## Fixture-level missing coverage

These groups overlap: a print with two missing fixtures appears twice. Dollar figures are full print premium/notional, not amounts allocated between fixtures.

| Missing fixture | Prints | YES premium | Payout notional |
|---|---:|---:|---:|
| Jan 17 BUF–DEN | 241 | 8,118.669 | 40,868 |
| Jan 18 CHI–LAR | 198 | 7,811.692 | 40,227 |
| Jan 18 HOU–NE | 18 | 2,444.282 | 11,713 |
| Jan 17 SEA–SF | 3 | 52.190 | 421 |

## Saved metadata and causal clocks

All requested histories start **January 4 06:00 UTC** and extend to one minute before each January 17/18 kickoff. Thus requests fully cover January 12 Chicago time (January 12 06:00 through January 13 06:00 UTC). Cached token IDs map to the expected full-game moneyline outcome, teams, game date and event slug. Both team tokens have the same availability gap; complementing the opposing team does not recover it.

| Fixture | PM market created (UTC Jan 13) | First PM price (UTC Jan 13, two tokens) | First Kalshi candle (UTC) |
|---|---|---|---|
| BUF–DEN | 14:51:45 | 14:56:10–12 | Jan 12 06:27 |
| SEA–SF | 15:36:11 | 15:40:28–30 | Jan 12 06:27 |
| HOU–NE | 14:51:48 | 14:56:08–09 | Jan 13 04:56 |
| CHI–LAR | 14:51:42 | 14:56:09–12 | Jan 12 04:27 |

The replay applies a further 60-second publication delay. Removing that delay cannot produce January 12 PM coverage: the markets were created after the full trading window ended. HOU–PIT wildcard moneylines have PM history from January 5 and cause none of the January 12 exclusions. With distinct-fixture 2–4-leg eligibility, the sole remaining wildcard fixture cannot alone supply an eligible combo; the universe has rotated toward divisional fixtures before their PM listings.

The lone first-error Kalshi print, `2e1c040b-b2b6-692d-a97d-16b778d9e968`, occurred January 12 06:26:47 UTC. Its SEA leg predates the first saved 06:27 candle (causally available 06:28); its other leg is LAR. Both also lack PM. Excluding it is appropriate under the saved-candle availability rule.

## Implications and evidence

Keep common-cohort comparisons unchanged. A separately labeled Kalshi-only availability cohort could recover 264 prints for a future diagnostic, but it must not be presented as a matched K/PM comparison or silently mix unavailable PM into a blend. Improving coverage reporting to retain all missing sources/legs would prevent the first-error category from obscuring this distinction. A future broader catalog search could test for alternative earlier listings, but the retained catalog provides no evidence of them; this audit made no provider requests.

[Verification JSON](../runs/morning_research_20260908/nfl_jan12_coverage_audit/verification.json) records all 265 print IDs, exact missing legs, per-leg aggregates, catalog creation metadata, source/query bounds and certified input hashes. The [audit script](../runs/morning_research_20260908/nfl_jan12_coverage_audit/audit.py) invokes only offline loaders, verifies completed-day hashes and saved source/catalog hashes, and writes separate audit artifacts. No frozen pipeline, saved histories or replay outputs were changed, and no MLB outcomes were inspected.

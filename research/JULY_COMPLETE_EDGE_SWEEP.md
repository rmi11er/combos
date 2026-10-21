# Complete July edge-hurdle comparison

The 48-policy continuous snapshot completed and passed an independent check of every published artifact hash, source/plan hashes, the full model/threshold/funding grid, common-cohort sell-all totals and funded summary cash requirements. Each policy processes 467,583 common prints across 15 priced July dates. July 13 remains an identity gap. Independent admission audits and exact baseline row parity cover the four 0.3c funded portfolios; the publication check alone does not independently audit every other policy's admission decisions.

## Funded net P&L under existing limits

| Model | Sell all | 0c/combo | 0.1c/combo | 0.3c/combo | 0.5c/combo | 0.3c/leg |
|---|---:|---:|---:|---:|---:|---:|
| Kalshi | −$684 | $89 | −$6 | $506 | $94 | −$6 |
| Polymarket | −$684 | −$251 | $269 | $637 | $765 | $444 |
| Equal blend | −$684 | −$419 | $424 | $45 | $167 | $312 |
| PM75 | −$684 | $448 | −$92 | $245 | $491 | $433 |

These start with $10k, use $100 underlying/combo and $250 event limits, and carry positions continuously across sampled dates. Settled gains can be reinvested. Selling every eligible print fits only 2,701 prints under these limits; it is not the unlimited sell-all universe. A lower hurdle admits earlier positions that displace later opportunities. More participation does not monotonically improve funded profit.

## Unlimited net P&L at observed print sizes

| Model | Sell all | 0c/combo | 0.1c/combo | 0.3c/combo | 0.5c/combo | 0.3c/leg |
|---|---:|---:|---:|---:|---:|---:|
| Kalshi | $332,449 | $159,235 | $125,779 | $131,052 | $89,540 | $22,779 |
| Polymarket | $332,449 | $714,088 | $801,147 | $658,093 | $414,361 | $257,592 |
| Equal blend | $332,449 | $481,292 | $449,349 | $267,946 | $157,283 | $115,023 |
| PM75 | $332,449 | $645,356 | $606,130 | $443,060 | $214,269 | $148,550 |

This supports further testing of PM-informed selection and more permissive hurdles in MLB. It does not establish an optimal quote spread: all policies filter previously observed traded prices, rather than simulate how customers would accept newly charged prices. Unlimited portfolios also have very different capital requirements and outcome concentrations. The funded ranking differs materially from the unlimited ranking.

The results use point fair, exchange-only models and the documented historical .035 maker-fee scenario, whose historical applicability remains unverified. Pinnacle, historical creator blacklists and live RFQ acceptance are absent. The 0.3c/leg policy is generally more restrictive than 0.3c/combo; their units must remain explicit. Sharpe is not annualized across these nonconsecutive sampled dates; plot legends report descriptive sampled-date P&L variance.

Next combine the limited edge-hurdle candidates with the $1k risk-range candidate and corrected fixed-deployment policy, then examine quote-reserve assumptions and liquidity-conditioned margins. Freeze candidates before looking at held-out August prints, with fixture overlap purged. July results alone must not pick deployment parameters.

[Funded comparison](../runs/mlb_july_development_snapshot_20260908/funded.png) · [Unlimited comparison](../runs/mlb_july_development_snapshot_20260908/unlimited.png) · [Publication verification](../runs/morning_research_20260908/july_complete_snapshot_audit/verification.json) · [Risk results](JULY_CONTINUOUS_RISK_RESULTS.md)

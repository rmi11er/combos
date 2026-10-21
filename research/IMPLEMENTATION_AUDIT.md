# Audit findings and study boundaries

## Material findings in the previous implementation

1. **Customer spend and maker collateral were conflated.** In
   `../kalshi_mm/src/rfq_paper.py:788`, target cost is divided by the active NO
   bid. That does not size a customer purchasing $10 of YES exposure. At a YES
   price of $0.10, $10 before fees buys 100 shares and requires about $90 maker
   principal. Dividing by $0.90 instead buys about 11 shares. The old report's
   claim that changing this denominator established correct sizing was stronger
   than the available evidence. The present study uses an explicit customer
   all-in budget and separates observed contract counts. Exact exchange RFQ
   target-cost mapping/rounding still requires side-specific quote evidence;
   public prints and RFQs cannot prove their linkage.
2. **Whole contracts are not a valid universal assumption.** September 5 public
   trades and retained RFQs have fractional `count_fp`/`contracts_fp`, including
   4,761.90-contract requests. This study preserves observed fractions and uses
   a stated 0.01-share step for hypothetical allocations.
3. **Occurrence is not necessarily kickoff.** The Ohio–Nebraska market has
   `occurrence_datetime=2026-09-05T19:00:00Z`, while Polymarket's game schedule
   gives 16:00 UTC. The previous comparison of occurrence against decision time
   can admit in-play activity as pregame. Scheduled start is matched by fixture
   here; no final close/settlement timestamp is used as a pricing feature.
4. **Fees are material and market-specific.** The current Kalshi schedule
   states a 0.07 quadratic taker coefficient and 0.0175 maker coefficient with
   a 2× combo maker multiplier (excluding its stated NFL exception). The CFB
   proxy therefore uses 0.035 for combo makers and 0.07 to widen constituent
   books. The old flat $0.001 per-share scenario is not a general combo maker
   fee model. Fractional ticket cost plus fee is rounded to a centicent under
   the published July convention. Actual fill fees remain authoritative.
   The actual CFB shard's historical fee-change record sets
   `quadratic_with_combo_maker_fees`, multiplier 1, effective
   `2026-08-20T09:05:00Z`; its generic maker coefficient therefore carries the
   documented combo multiplier. Other combo shards have different fee types
   and cannot inherit this rate automatically.
5. **Polymarket generic documentation is insufficient for fees.** Retrieved
   CFB market objects report `sports_fees_v3` and a `feeSchedule` rate of 0.05,
   whereas the general documentation table lists 0.03 for sports. Preserve
   market-specific fee provenance and historical effective dates; do not
   blindly hardcode the table or today's metadata for all historical periods.
6. **Documentation and the paper risk engine differ.** The economics-v0 notes
   list daily-new-loss and contract-count limits that are absent from
   `PaperPolicy`/`make_paper_decision` and its paper JSON. Separate historical
   and live implementations have additional controls. A research report cannot
   establish that an identically named policy enforces identical limits in
   every path. This project does not inherit those undocumented controls.
7. **Fill draws did not identify acceptance.** Quote-independent synthetic
   fills, completed-print selection, arbitrary seed sensitivity, and selected
   source days invalidate interpreting historical Sharpe as live strategy
   performance. This study uses no random acceptance draw.
8. **Matching teams and lines does not match every settlement state.** The
   retained Ohio–Nebraska rules illustrate a material exception: Kalshi uses
   a 48-hour start window and can settle at a fair price, while Polymarket can
   wait for a postponed game and specifies 50–50 for cancellation without a
   make-up game. The automated Polymarket matches therefore mean equivalent
   selected outcomes for a normally completed game only. They are price
   diagnostics, not verified identical payoffs. The strict blend requires
   independently verified mapping, including these exceptional states; a
   future implementation would need an explicit basis adjustment or exclusion.
9. **A creator field in the API schema is not usable creator coverage.** Every
   recovered studied-day RFQ has a blank `creator_id`. The historical response
   exposes requests and leg structure but cannot support creator-level spam
   counting, pickoff attribution or a populated blacklist. The output status
   is explicitly unavailable identity; it is not a finding of zero bad actors.

## Pricing conventions

- A selected-side exchange book `[bid, ask]` is widened to
  `[bid - taker_fee(bid), ask + taker_fee(ask)]`, bounded to `[0,1]`. Its
  midpoint stays the point estimate. Widening alone does not identify a new
  point fair. Quote uncertainty and the actual combo maker execution fee are
  separate quantities; constituent taker fees are not charged again as hedge
  execution costs when no hedge is executed.
- A three-venue liquidity blend requires matching date, fixture, period,
  strike, selected outcome and void/push/overtime rules; historical liquidity
  in a common payout-capacity unit; and price/liquidity timestamps no later
  than the decision. Present-day depth and full-day final volume are not
  substituted for historical liquidity. A bookmaker max stake is converted
  into payout capacity before comparison with exchange shares.
- Pinnacle paired decimal odds are multiplicatively de-vigged for the proposed
  center; executable opposing odds provide an interval. This is a modeling
  convention, not a uniquely identified fair probability. Do not double-charge
  bookmaker margin as an invented taker fee.
- In the actual recovered dataset, the full requested blend is missing.
  Kalshi-only fee-expanded independence is an explicitly labeled proxy.
  Matched Polymarket historical point prices support a separate equal-weight
  diagnostic, not a liquidity-weighted executable book.
- Two-leg cross-game joint probability is a product only under independence.
  Same-game combinations are segregated. Positive 0.02/0.05 Bernoulli
  correlation stresses are assumptions bounded by marginal Fréchet limits.
  They are not estimated correlations, and pricing protection does not remove
  shared-fixture exposure across different tickets.

## Evidence limits and accounting

- Historical candles provide minute book summaries, not millisecond executable
  books. The primary benchmark assumes 60 seconds publication delay and allows
  120 additional seconds of age. No forward candle enters the fair. Sensitivity
  runs show the consequence of 0/30/120-second assumed publication delay.
- Public prints have no RFQ ID or creator ID. Do not infer which requester
  traded from nearby timestamps; do not apply a creator blacklist to public
  prints via such a join. Retained RFQs are conditional on traded markets and
  a bounded context sample, not the entire RFQ universe.
- Maker quotes are private to each maker and requester. All-universe quoted
  volume is unavailable. RFQ target-budget sums count repeat requests and are
  not unique demand, quoted volume, filled volume, or revenue.
- Retrospective RFQ status does not establish its lifetime at the hypothetical
  decision timestamp. Per-request quoteability assumes the request survives
  the stated one-second response delay; this was not observed historically.
- The capital scenario has no ticket-spend cap and allocates at most once per
  market per second, never more than observed printed quantity, with all
  $10,000 initially available. Quantity is reduced to fit available cash for
  principal plus maker fees, in 0.01-contract steps.
  It requires 0.3 cents net edge per share, reserves full NO principal plus
  fees, and releases payout at observed settlement plus an assumed 60 seconds.
  Realized gains/losses affect cash. This is an ex-post capacity scenario, not
  a full-size RFQ execution simulation, fill probability estimate, or safe
  portfolio allocation. Single-game concentration can dominate losses.
- Historical final outcomes are used only for evaluating settlement and cash
  release. Fair probabilities and quote eligibility never use terminal labels.
  Current source metadata for structurally stable composition/schedule is an
  explicit historical reconstruction assumption, not demonstrated publication
  availability.

## Sources checked

- [Kalshi RFQ mechanics](https://docs.kalshi.com/getting_started/rfqs)
- [Kalshi July 7 fee schedule](https://kalshi.com/docs/kalshi-fee-schedule.pdf)
- [Kalshi public trades](https://docs.kalshi.com/api-reference/market/get-trades)
- [Kalshi RFQ response schema](https://docs.kalshi.com/api-reference/communications/get-rfqs)
- [Polymarket historical prices](https://docs.polymarket.com/api-reference/markets/get-prices-history)
- [Polymarket fees](https://docs.polymarket.com/trading/fees)
- [Pinnacle API access and conventions](https://github.com/pinnacleapi/pinnacleapi-documentation)

Raw response envelopes under `data/raw/` retain retrieval times. Final study
outputs contain coverage/exclusions; missing required blend inputs remain null,
not zero edge. No execution adapter or live orders are included in this project.

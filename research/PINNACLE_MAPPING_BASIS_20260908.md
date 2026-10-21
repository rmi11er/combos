# Pinnacle pricing-reference review

The current 454 NFL mappings comprise 186 full-game totals, 83 full-game spreads, 32 full-game moneylines, nine full-game team totals, plus 144 first-half/first-quarter markets. The simplest normal-completion review targets are the exact full-game half-point spreads and totals; this is a review ordering, not a restriction of the intended eventual non-player scope.

Pinnacle's published American Football rules include overtime in game and second-half markets. They void games not started within 12 hours; suspension treatment depends on whether 55 minutes were completed and whether play resumes within 12 hours. Completed subperiods can retain action separately. These provisions differ from the exchange terms already retained in the mapping review, so a normal-game price correspondence cannot certify global payoff equivalence. [Pinnacle rules](https://www.pinnacle.com/en/future/betting-rules/).

OddsPapi's API documentation identifies `limit` as a maximum bet amount and describes `bookmakerChangedAt` and `changedAt` as change timestamps. A fresh poll with an old change timestamp need not be stale. [GET odds documentation](https://oddspapi.io/us/docs/get-odds).

The provider's limits guide clarifies that its outcome-level sportsbook field represents stake, even when the book determines that amount from a win-risk rule. It describes the monetary unit as account currency. This supports interpreting the field as stake, but does not establish USD for our account/feed. Do not apply a second max-win-to-stake conversion or mark currency verified from dollar examples alone. [OddsPapi limits guide](https://oddspapi.io/blog/betting-limits-api-stake-sizing/).

Two additional modeling gaps surfaced in the implementation review:

- `pinnacle_feed.normalize` still uses the older side's last-change timestamp as its observation-age proxy. With the configured 90-second maximum age this excludes unchanged prices even after successful polling. Snapshot delivery age and native price-change age need separate fields and an explicit feed-health policy. Poll receipt alone also cannot prove the provider's upstream connection is healthy.
- The current weighting configuration caps Pinnacle at 20% and uses a 0.5 score multiplier, versus 1.5 for Polymarket. It is not a sharp-heavy Pinnacle blend. Weight, delay/disagreement policy and freshness changes must be explicit candidate configurations evaluated in shadow; historical exchange-only results cannot establish their benefit.

No mapping was marked payoff-reviewed, no USD assumption was asserted, and no pricing/weight configuration changed in this review. Required next work is to encode conditional versus unconditional payoff bases (including moneyline ties), exception handling, verified limit currency or an explicit relative-liquidity proxy, and a response-age feed-health policy. Then compare clearly labeled candidate fair models on the same causal shadow stream.

The retained account responses do contain `subscriptions[].currency=USD`. The provider's account documentation defines that field as the subscription currency, alongside subscription price. It therefore cannot by itself establish the denomination of bookmaker `limit` values. No additional API request was needed for this inspection, and account identity/credentials were not copied into the review. [GET account documentation](https://oddspapi.io/en/docs/get-account).

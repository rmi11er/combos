# Provisional NFL shadow hyperparameters

The August held-out MLB study now gives us a useful capacity warning: the
equal blend was positive at $500 named limits but negative at $2,000, while
unlimited paths were economically unrealistic and often negative. It does not
identify NFL-optimal limits, since NFL January has no Pinnacle and uses public
prints rather than observed RFQ fills.

For the next NFL shadow session, the proposed baseline is:

- $10,000 reporting capital, with a $5,000 maximum committed exposure;
- $500 each per canonical underlying, combo and fixture;
- 0.3¢ minimum net edge per combo contract after fees;
- 2–4 pregame non-player legs, full RFQ size, customer YES / maker NO;
- 30-second delayed Pinnacle with the liquidity-weighted three-source fair;
- Pinnacle/Polymarket consensus lean logged as a feature only;
- hard source disagreement halt at 5¢ and half risk in the defensive regime;
- creator behavior logged for review, with no automatic blacklist yet.

These are deliberately conservative shadow settings, not a live authorization.
The $500 limits are a research allocation choice, not an extrapolation of a
Sharpe ratio. We will sweep 0.1/0.3/0.5¢ edge and $100/$500/$1,000 limits on
independent NFL slates using accepted and filled RFQs, then freeze an OOS
configuration before any quote transport is enabled.

The live account currently has unresolved cash and mapping gates. The account
read path must prove positive available balance, precision and no conflicting
positions/open orders; the strategy must not treat a $10,000 target as funded
cash. Full-fill RFQs also mean quote widening does not choose a partial size.

The machine-readable proposal is
`config/provisional_nfl_shadow_hyperparameters_20260909.json`; it explicitly
sets `live_enabled=false` and lists promotion gates. No production config was
changed and no orders were submitted.

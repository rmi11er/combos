# Correlation-charge diagnostic

This is a broad, unconstrained diagnostic over 615,952 resolved Kalshi-model rows from the saved NFL Jan 5–18 and July MLB tapes. It compares the recorded point edge with the conservative `stressed_upper` bound already stored in each row. It is not a funded portfolio replay and does not establish causal toxicity.

| Entry rule | Resolved rows selected | Retrospective P&L | Mean P&L / row | Win rate |
|---|---:|---:|---:|---:|
| Point edge ≥ 0.003 after fee | 7,078 | $336,216 | $47.50 | 77.4% |
| Stressed edge ≥ 0.003 after fee | 212 | $2,797 | $13.19 | 59.9% |

The correlation charge removes most rows because the pairwise-moment upper bound is often far above the independent point. In reserve bands with enough observations, selected P&L is not monotonic in reserve size: the 2–5¢ reserve band is positive, the 5–10¢ band is slightly negative, and the 10–20¢ band is positive again. The stressed rule therefore behaves primarily as a conservative admission filter, not as a validated predictor of which individual trades will win.

The correct next test is a matched funded replay with fixed fills, creator blacklist state, and fixture-cluster bootstrap confidence intervals. Correlation charges should be evaluated for drawdown/tail reduction and calibration of joint outcomes, not accepted solely because they lower the trade count.

# NFL charge and capacity sensitivity

Completed144 portfolios: four source priors, six charge rules, three cap levels and
two reservation assumptions. Each uses all694 matched priced RFQs from the full
47,937-RFQ capture, September9 03:17–03:19 CDT. $10k cash; caps apply separately to
underlying/combo/event, full RFQ sizes, no ticket or percentage cap. Both modes are
research assumptions: no fills with3s expiry, or all admissions filled with no release.
No acceptance rates, realized returns or optimal charges are inferred.

Captured sharp-peer source model, all-fill/no-release:

| Charge | Admissions at $1k caps | Peak held at $1k | Admissions at $2k | Peak held at $2k |
|---|---:|---:|---:|---:|
|Zero|110|$4,409.25|143|$8,792.90|
|0.1c/combo|103|$4,382.61|125|$8,763.58|
|0.3c/combo|106|$4,672.89|140|$8,717.51|
|0.6c/combo|107|$4,637.28|127|$8,732.53|
|0.3c/leg|113|$4,630.37|135|$8,677.48|
|25% marginal interval +0.3c/combo|107|$4,585.27|130|$8,658.86|

The quarter-interval charge incorporates spread, disagreement and uncertainty
padding; it is not a pure liquidity charge. Increasing asks reduces seller NO-buy
collateral requirements and may reduce target-cost contract bounds, but allocation
is path-dependent: a newly admitted early RFQ can displace later ones. The table
cannot establish a charge-to-fill-rate relationship because every admission is
assumed to fill. Removing the charge does not mechanically fill the capital budget.
Risk caps have a much larger deployment effect here; raising them still requires
independent-game risk validation and prospective acceptance evidence.

Independent audit reconciled99,936 quote/capacity decisions across all144 portfolios:
Decimal reference, full-size/target-cost bounds, actual assumed balance rounding,
net edge, collateral bound, duplicate handling, expiry, integer bucket/cash limits,
active counts and summary peaks. The existing0.3c/$1k/all-fill scenario reproduces
all2,776 prior model quote/admission rows exactly. A first checker assumed zero fee
coefficient meant zero net fee; the corrected independent checker includes purchase
cash rounding to0.0001. This was an audit assumption error, not a quote-engine change.
The current sample has zero maker coefficients; nonzero coefficients are outside
this standalone audit's scope. Grid minimality is not independently rederived here.

Workflows: scripts/rfq_charge_capacity_sweep.py, scripts/audit_rfq_charge_capacity.py,
scripts/plot_rfq_charge_capacity.py. All decisions, summary, verification and rendered
plot are retained in runs/nfl_charge_capacity_sweep_20260909. No strategy was promoted.

Historical update: August22 completed after the supervised recovery of a public
request retry-exhaustion failure. Three dates remain24,28,30. Collection and both
supervisors were verified live. Frozen held-out outcomes remain unopened.

# Creator policy audit and current economic limits

Independently reconstructed32 duplicate-request burst notices across27 creators in
the119.77-second capture of47,937 RFQs from2,862 creators. Each published window's
total/same-leg-set counts, duplicate fraction, minimum threshold and source identity
match the raw preceding RFQs. Publications follow their source evidence in sequence.

Publication-causal RFQ exposure:47,109 clear and828 watch. All694 research-priced
RFQs had clear creators. No cooldown/blocked state occurred and no markout groups
exist. Consequently no priced RFQ was removed by the blacklist, and this sample
provides no evidence of blacklist-related economic improvement.

The current service requires at least30 RFQs in60s, with at least80% sharing a leg
set, and three bursts separated by60s before a one-hour cooldown. Long leg counts
alone are context, not an automatic ban. Given fresh state and a capture shorter
than120s, this run cannot demonstrate the three-separated-burst cooldown path.
All transitions are watch notices; the five additional notices come from repeated
bursts for already watched creators. Earlier synthetic tests cover cooldown behavior.

Creator publications use the source receipt timestamp when appending their later
sequence. Thus sequence distance is measurable, but that timestamp cannot measure
actual publication latency. The research consumer correctly applies state only once
its publication event arrives. A later classification is never applied retroactively
in this audit.

Operational implications: persistent sniffer state across long sessions is required;
new short capture databases do not inherit prior creator histories. Correlation
pickoffs need mapping/joint-fair and future market evidence, not leg count alone.
Current economic markout collection is not connected to these research-priced
candidates. Attach causal markouts to the candidate stream before estimating which
creators systematically take mispriced risk. Compare excluded and admitted cohorts
with independent-fixture grouping rather than assuming watch labels improve P&L.

Workflow: scripts/audit_creator_capture.py. Results and input/source hashes:
runs/nfl_creator_capture_audit_20260909. Closed immutable SQLite input was used;
no capture rows, creator states or strategy thresholds were changed. The audit
checks this complete observed sample; it does not infer behavior across data gaps.

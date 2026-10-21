# NFL actual-RFQ quote-charge and sizing scenarios

The workflow `scripts/rfq_quote_charge_sweep.py` consumes the complete 43,003-row
RFQ census and prices each of the 167 three-source-eligible RFQs under 12 policies:
point, quarter marginal reserve, or full marginal reserve; each with zero,
0.1c/combo, 0.3c/combo, or 0.3c/leg extra edge. All 2,004 rows reconcile quantity,
fee, cash and edge identities. Four focused tests cover full-size retention,
target bounds, infeasible quotes and NO-buy cash accounting.

At 0.3c/combo, median YES asks are 30.53c, 31.31c and 33.64c respectively.
Corresponding median worst-case fragmentation cash holds are $24.33, $22.96 and
$20.26. The median differences are not paired quote differences. Higher asks lower
NO-side purchase cost and can reduce target-cost quantities. One RFQ individually
exceeds $10k under point and quarter-reserve policies; none does under full reserve
at this edge. This is not portfolio admissibility or evidence of fill probability.

Nine RFQs specify fixed contracts, retained exactly. The other 158 specify target
cost: quantity is ceil(target/YES ask) to 0.01 contracts, a conservative bound when
nonnegative customer fees may consume part of the target. It is not the exact
exchange target-sizing algorithm. Quote edge uses a single-fill fee scenario;
cash holds separately cover maximum fragmentation at 0.01-contract minimum fills.

Assumptions remain explicit: 0.0001 price grid, 0.0001 balance precision, 0.035 maker
coefficient, native Pinnacle stake converted at 1:1, and the existing independent
joint/payoff sensitivity inputs. Neither account precision nor this generic grid
is certified for every captured combo. No live configuration changed.

Outputs: `runs/nfl_rfq_quote_charge_sweep_20260909/{summary,decisions,verification}.json`.
Next: actual per-market grids and fee metadata, causal creator policy, canonical
underlying/event limits and outstanding quote reservations. No executions, capital
release, profitability, or blacklist benefit are inferred from this sweep.

Follow-up correction: the captured series metadata assigns zero maker fees to all
167 RFQs. Use `RFQ_CAPTURED_TERMS_20260909.md` for captured-term results; this
uniform-.035 sweep remains only a fee sensitivity scenario.

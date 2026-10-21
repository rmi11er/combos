# NFL per-ticket event-risk allocation

The follow-up tests whole-contract partial sizing with each ticket limited to 100%, 25%, 10% or 5% of the configured event risk allowance. The aggregate event, underlying, combo and cash limits remain enforced. This is a risk allocation experiment; no historical prints are excluded by their original premium, and no live ticket cap is introduced.

All 32 portfolios use the same January 5–18 exchange-only point-fair cohort, 0.3c/combo hurdle, $10,000 starting capital and unverified .035 maker-fee scenario. Underlying/combo caps are $10,000; event caps are $1,000 or $2,000. Fees are recalculated at reduced quantities. Funding becomes available only at actual settlement.

| Event limit | Per-ticket fraction | Kalshi net | Equal net | PM75 net | PM net |
|---|---:|---:|---:|---:|---:|
| $1,000 | 100% | $954.17 | $523.28 | $431.57 | −$1,511.59 |
| $1,000 | 25% | $391.27 | $68.58 | −$126.92 | −$1,325.54 |
| $1,000 | 10% | $218.72 | −$33.35 | −$39.42 | −$502.78 |
| $1,000 | 5% | $554.95 | $2.68 | $38.25 | −$366.13 |
| $2,000 | 100% | $2,196.06 | $2,158.38 | $1,858.16 | −$1,239.56 |
| $2,000 | 25% | $943.36 | $676.04 | −$73.71 | −$1,273.00 |
| $2,000 | 10% | $779.29 | −$328.97 | $142.73 | −$1,060.54 |
| $2,000 | 5% | $1,119.36 | $370.48 | −$72.76 | −$574.89 |

Smaller allocations increase participation but do not consistently improve profit. At the $1,000 event cap, 5% allocations produce 120/125/133/130 fills for K/equal/PM75/PM, versus 54/44/55/50 at 100%. Peak cash at 5% is $1,642–$1,839. At the $2,000 cap, 5% gives 142–179 fills and $3,220–$3,754 peak cash.

All 32 portfolios have a negative minimum after removing trades touching one game without reallocating capital. The smallest loss is Kalshi's −$50.61 at $1,000/5%, but this is an inspected development result, not a parameter recommendation. Smaller tickets spread participation over more prints while those prints still share the same small set of outcomes. No optimal fraction or stable NFL source weight is established.

## Verification

All admission sets match the existing backtester; all 32 independent integer exposure audits pass. At 100%, fills, P&L, peak cash and accepted point edge exactly reproduce the preceding partial-sizing experiment. Four focused sizer tests pass, including aggregate exposure retention across smaller tickets, fee repricing, settlement funding and pre-settlement outcome invariance. Source/input hashes and retained artifact hashes were verified.

The previous sizer source is preserved at `nfl_partial_sizing/research_partial_sizing_v1.py`, with a source archive receipt. Existing receipts continue to describe that original version. The new optional fraction defaults to 100%; production risk and pricing code are unchanged.

The next research priority is the full July pooled model comparison and calibrated quote reserves, followed by independent held-out/prospective evidence. Expanding this NFL grid further on nine already inspected games would add parameter choices without adding independent information. These hypothetical partial fills do not establish RFQ acceptance, supported minimum quantity increments, live fee precision or three-source pricing quality.

[Results](../runs/morning_research_20260908/nfl_ticket_allocation/summary.json) · [Verification](../runs/morning_research_20260908/nfl_ticket_allocation/root_verification.json) · [Reproduction](../runs/morning_research_20260908/nfl_ticket_allocation/run.py)

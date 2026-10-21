# CFB combo volume, August 31–September 6, 2026

Trade timestamps use America/Chicago. The standard KXMVE RFQ-combo universe is classified from actual market leg definitions: every leg must be CFB. Mixed-sport combos are excluded. All leg counts are included, with a separate two-leg comparison. Figures include in-play activity and are not pregame quoteable opportunity.

**Saturday is a complete census; all other days are estimates.** We selected four random 15-second cells without replacement in every hour on each of the other six days (576 cells, 144 minutes, 1/60 of their elapsed time), then collected every print in those cells with full pagination. Totals use inverse-inclusion weights. Approximate 95% intervals use within-hour time-cluster variance; rare large trades can make these normal approximations optimistic.

| Day | YES premium | Premium share | Payout notional | Two-leg YES premium |
|---|---:|---:|---:|---:|
| Monday (estimate) | $0.111m | 0.2% | $1.691m | $0.034m |
| Tuesday (estimate) | $0.149m | 0.3% | $7.197m | $0.051m |
| Wednesday (estimate) | $0.454m | 0.9% | $10.715m | $0.221m |
| Thursday (estimate) | $4.749m | 9.4% | $57.793m | $1.955m |
| Friday (estimate) | $3.773m | 7.5% | $60.666m | $1.275m |
| Saturday (census) | $32.495m | 64.6% | $204.566m | $18.788m |
| Sunday (estimate) | $8.536m | 17.0% | $35.657m | $5.030m |

YES premium is sum(quantity × YES price), with each print counted once. Payout notional is sum(quantity × $1), the full face value, not cash spent or maker collateral. Public trades do not reveal private RFQ volume or all quotes.

Thursday through Saturday account for an estimated **81.6% of YES premium** (approximate 95% interval 77.2–86.0%) and **85.4% of payout notional**. Narrowing the window to Thursday at 6 p.m. through Saturday midnight yields **77.9% of premium** (73.5–82.3%) and **77.6% of payout notional**. The corresponding two-leg premium share for that evening window is **78.7%** (71.4–86.0%).

Sunday accounts for about 17.0% of all-CFB premium and 18.4% of two-leg premium. A fixture-aware acquisition schedule should therefore include Sunday whenever pregame CFB fixtures remain. One week does not establish a permanent weekday profile.

Reproduce: `.venv/bin/python scripts/cfb_week_volume.py` followed by `.venv/bin/python scripts/report_cfb_week.py`. Raw sampled responses and persistent classifications are under `data/raw/cfb_week_20260831/`; the prior Saturday raw tape remains under `data/raw/trades/`. Sampling plan, full numerical estimates/error bars, hourly aggregates, code hashes and chart are under `runs/cfb_week_20260831/`.

[Weekday chart](../runs/cfb_week_20260831/weekday_volume.png) · [Daily estimates](../runs/cfb_week_20260831/summary.json) · [Timing shares](../runs/cfb_week_20260831/timing_summary.json)

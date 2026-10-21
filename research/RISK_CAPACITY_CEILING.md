# Structural capacity ceiling

Run `scripts/risk_capacity_ceiling.py --input <opportunities.json or decisions.jsonl.gz> --out <result.json>`.

The existing risk ledger charges a position's full rounded NO cash cost, including maker fees, to every distinct underlying and fixture bucket. If every position charges at least m buckets, then m times total committed cash is no greater than the sum of those bucket caps. The workflow computes this bound for each family and takes the smaller value. It counts canonical bucket identities, not ticker aliases.

The January 5–10 NFL moneyline cohort has six underlying buckets and at least two per position. Under $100 underlying caps, its total committed cash cannot exceed $300. The observed ~$209 peak is therefore about70% of this loose risk ceiling. Relaxing price selection or taking partial sizes cannot exceed it.

This is a bound for positions drawn from the supplied cohort, without additional preexisting/outside positions. Whole-window bucket unions can overstate simultaneous opportunity. It does not estimate fills, turnover, loss probability or appropriate limits. Lower per-trade limit multipliers and other constraints only reduce capacity. Profit reinvestment does not remove bucket caps.

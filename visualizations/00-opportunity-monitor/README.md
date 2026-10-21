# Liquidity opportunity monitor

Open `index.html` in a browser after rebuilding the snapshot:

```sh
python3 scripts/build_opportunity_monitor.py
open visualizations/00-opportunity-monitor/index.html
```

The page starts with a trader-facing research allocation view: the executable
RFQ funnel, adverse-selection/markout curves, capacity frontiers under release
assumptions, and data blockers. It then re-buckets observed activity into daily,
weekly, or monthly periods and keeps provenance, sampling method, and coverage
caveats visible.
Add future normalized rows to `data/opportunity_monitor/snapshot.json` using the
same schema to expand the cross-venue and non-US history.

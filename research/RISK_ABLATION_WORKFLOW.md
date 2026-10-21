# Isolated risk-limit experiments

`scripts/replay_risk_ablation.py` evaluates a fixed grid on the entire paired cohort from a retained unlimited replay. It strips previous admission decisions, preserves source fair values, prices, fees, full print quantities and canonical buckets, and replays chronology using actual settlement funding. It rejects constrained inputs, sampled rows, mismatched model cohorts and inconsistent paired economics.

Every scenario uses the archived entry policy and initial capital. Event caps are $100/$250/$500/$1,000/$2,000; underlying caps are $50/$100/$250/$500/$1,000. Each family is evaluated with the other archived limits held fixed, then with the other two caps set to $10,000. The latter caps are relaxed, not infinite. There are 21 named scenarios including baseline; some reproduce identical configurations and must not be counted as independent evidence. No Cartesian optimization or partial sizing is performed. Partial-size experiments remain a separate required task.

Before any alternative is evaluated, the baseline must exactly reproduce retained summaries, all decisions, fills, curves and daily records. NFL's appended concentration diagnostics are reproduced too. Each alternative independently reconciles integer exposure accounting and reports every binding limit, peak-cash game concentration and outcome sensitivity. Game omissions do not rerun allocation. Shared fixtures mean that prints and overlapping omission results are not independent statistical trials.

Outputs preserve every decision/fill/curve/daily row in Zstandard, with exact input/source hashes and an explicit completion marker after all scenarios. An interrupted experiment retains its directory and requires a fresh output path. Historical fee validity, source coverage, live depth and actual RFQ acceptance are not established by these accounting checks. There is no creator adjustment when historical creator IDs are absent.

## First NFL run

```sh
.venv/bin/python -u scripts/replay_risk_ablation.py \
  --ledger runs/nfl_moneyline_replay_20260907/jan5_18/fee0.035_unlimited_selection.json.gz \
  --study-summary runs/nfl_moneyline_replay_20260907/jan5_18/summary.json \
  --baseline-ledger runs/nfl_moneyline_replay_20260907/jan5_18/fee0.035_funded_selection.json.gz \
  --out runs/morning_research_20260908/nfl_risk_ablation_v2
```

The complete January 5–18 sample is already inspected development evidence, not a new held-out test. Its four models lack Pinnacle and use the unverified .035 maker-fee scenario. Nine complementary moneyline risk families make this useful for diagnosing capacity, but insufficient for calibrating a broad NFL spread/total inventory model.

Seven focused tests passed. The first attempt stopped before any alternative because the core replay lacked the NFL archive's appended concentration field; all actual decisions/fills/curves/daily values matched. The new version reproduces the additional field exactly and has passed the full baseline gate. The v2 sweep completed all 21 scenarios/84 portfolios. Source/input/output hashes and independent exposure audits pass. Ledger/economic peak differences stay within the per-fill rounding bound (maximum $0.0022). Both plots were visually inspected. See [NFL results](NFL_JAN5_18_RISK_ABLATION.md). Frozen MLB collection code and live parameters are unchanged.

# combos

Research and shadow-trading tooling for Kalshi/Polymarket sports combo (parlay) markets: data acquisition, causal pricing replay, passive RFQ capture, backtests with correlation/risk charges, and a supervised shadow-quoting runtime. Read-only, no live trading adapter by default. Built with Claude Code / Codex as copilots.

```bash
uv sync --all-extras
PYTHONPATH=. uv run pytest   # ~1,165 pass; 11 tests need local gitignored runs/ artifacts and fail on a fresh clone
```

Provider credentials are read from the environment and never committed. Raw data, run databases and counterparty identifiers are excluded.

---

# September 5 college-football combo study

[Open the liquidity opportunity monitor](visualizations/00-opportunity-monitor/README.md) — daily, weekly, and monthly cuts across the normalized combo/sports snapshot.

[Browse historical backtests and opportunity visualizations](visualizations/README.md) — curated previews, sport-specific reviews, daily drilldowns and earlier/QA artifacts.

Read-only research in a separate project from `../kalshi_mm`. No trading adapter.

Reusable acquisition, causal pricing replay and passive creator capture are now
available through `scripts/research.py`. See the [research sequence, weighting
model and command reference](research/RESEARCH_PIPELINE.md). New experiments use
`runs/`; the September 5 outputs below remain the historical study.

The current delivery target is [continuous NFL shadow quoting for Wednesday,
September 9](research/NFL_LAUNCH_PLAN.md), followed by live operation once the
pricing feeds, contract risk limits and execution lifecycle are ready.
`scripts/runtime.py` now supplies independent collectors, creator monitoring,
continuous shadow decisions and atomic risk reservations. See the
[runtime operations guide](research/RUNTIME_OPERATIONS.md) for setup, feed
contracts, review exports, archive restoration and remaining deployment work.
For a repeatable bounded run, use `source .venv/bin/activate && .venv/bin/python
scripts/run_shadow.py`; it loads `~/.codex/.env`, runs NFL preflight, creates a
timestamped `runs/shadow_...` database, starts the supervised services, and
prints adjacent service logs if startup fails. Pass `--run-dir ... --resume`
to resume an already initialized run. The event database safety limit defaults
to 8 GB and can be changed per run with `--max-db-gb`.
The follow-on pricing and risk research backlog is in
[research/NFL_SHADOW_RESEARCH_BACKLOG.md](research/NFL_SHADOW_RESEARCH_BACKLOG.md).

The [NFL mapping and fee review](research/NFL_MAPPING_REVIEW.md) supplies a
repeatable 299-contract Kalshi/Polymarket collection configuration. The
[September 6–7 runtime review](research/NFL_RUNTIME_REVIEW.md) records the sustained
capture, sleep interruptions, fixes and successful short live verification.

The current modeling defaults use [delayed Pinnacle for pregame-only quotes](research/DELAYED_PINNACLE.md):
30-second minimum effective age, exchange-disagreement guards, a provisional
Polymarket weight preference, and reduced concentration limits. The document also
sets out the shared-cache architecture and request budget for the retail OddsPapi
subscription. Provider credentials, payload validation and the automatic Pinnacle
polling/normalization service remain pending; the existing live collectors are
Kalshi and Polymarket only. Existing runs keep their original frozen configuration.

The [NFL fee and equivalent-payoff risk review](research/NFL_FEES_AND_RISK.md)
records current market coefficients, cash-fee rounding, alias grouping and
buy/sell signs. `scripts/refresh_nfl_fee_metadata.py` refreshes the market-specific
fee inputs without removing independent payoff-review or combo-term gates.

[CFB volume by weekday, August 31–September 6](research/CFB_WEEKDAY_VOLUME.md)
combines the saved Saturday census with reproducible random time samples on the
other six days. It includes all-CFB and two-leg cohorts, uncertainty estimates,
hourly aggregates and a weekday chart.

[CFB market coverage and leg counts](research/CFB_PROP_COVERAGE.md) compares
full-game-only parlays with team-total/period extensions across all leg counts
and phases, including 2-, 3-, 4-, and 5-plus-leg totals. No individual-player
prop legs were observed in that analyzed CFB universe.

Allocations have no ticket-spend cap: observed trade quantity is limited by
available cash from the $10,000 starting capital ledger. Earlier $10-capped
results are preserved under `output/archive/ticket_cap_10/`.

- [Study configuration](config/study.json)
- [Implementation audit](research/IMPLEMENTATION_AUDIT.md)
- [Historical input contract](research/HISTORICAL_INPUT_CONTRACT.md)
- Results: `output/summary.json`, `output/opportunity_by_time.png`,
  `output/pricing_sensitivity.png`, opportunity/RFQ CSVs, and creator evidence.
- The requested three-venue liquidity-weighted estimate remains null if any
  required historical source or comparable liquidity measurement is absent.
  Kalshi-only proxies and equal-weight Polymarket diagnostics are named as such.
- External historical books can be supplied at
  `data/external/historical_venue_books.jsonl`. The record contract is enforced
  by `src/combos/external_blend.py`; it requires verified payoff mapping,
  source references, availability times and comparable historical capacity.
  Coverage and strict three-venue edge are emitted separately in the CSV/JSON.

## Reproduce

Python 3.13. Install `requirements.txt` into `.venv`. Data collection uses only
GET requests; RFQ history requires the existing read-capable Kalshi environment
variables. Credentials are never stored in research outputs. For authenticated
read signing only, collectors reuse `../kalshi_mm/src/kalshi_v2.py`.

Recompute results from the retained inputs:

```sh
.venv/bin/python scripts/analyze_day.py
.venv/bin/python scripts/verify_outputs.py
.venv/bin/python scripts/audit_inputs.py
.venv/bin/python scripts/plot_results.py
.venv/bin/python scripts/write_report.py
.venv/bin/python -m pytest -q
```

Collectors are resumable: `collect_trades.py`, `build_catalog.py`,
`fetch_inputs.py`, and `fetch_polymarket.py`, in that order. `repair_inputs.py`
retries explicitly missing market definitions and failed candles; rerun the
catalog and leg/Polymarket collectors after recovery. This study froze its
adaptive RFQ enrichment with `fetch_inputs.py --retained-rfqs-only` while
finishing exhaustive traded-market and leg coverage. The retained RFQ sampling
manifest records the retrieved markets and the incomplete intended hash sample.
Do not treat that sample as probability-weighted population coverage.

`probe_sources.py` and `probe_more.py` recover source-discovery metadata;
`fetch_creator_sample.py` adds bounded creator context.
`audit_nonprefix_combos.py` checks separately named composite series against the
legacy KXMVE screen. Raw pages are compressed and retained with retrieval times.

The data are a completed-trade census plus retained RFQs in a bounded subset of
traded markets, not a census of all requests or private maker quotes. Missing
data, assumed historical publication delay, cross-game dependence and shared
fixture concentration are material limits on every opportunity number.

Current NFL launch work: [2–4-leg pregame runbook and live blockers](research/NFL_LAUNCH_PLAN.md).
Run `.venv/bin/python scripts/nfl_preflight.py` for a static configuration report.

Expanded NFL scope and replaceable pricing components: [non-player architecture and coverage](research/NFL_NONPLAYER_ARCHITECTURE.md).

Historical CFB fair validation and repeatable P&L/volume/model comparisons: [pilot results and reporting commands](research/CFB_FAIR_PILOT_RESULTS.md). Historical imputation is explicitly rejected by forward pricing.

Paired $10,000/concentration-constrained and unlimited portfolio backtests, with
equity, Sharpe/variance, settlement recycling and full decision logs:
[backtester results, assumptions and commands](research/BACKTEST_EVALUATOR.md).
Research next steps: [delayed Pinnacle modeling](research/DELAYED_FEED_MODEL_RESEARCH.md)
and [July-onward MLB validation](research/MLB_HISTORICAL_VALIDATION_PLAN.md).

Latest results: [all-available CFB week backtest](research/CFB_FULL_WEEK_BACKTEST.md).

Latest audit: [$50 premium, fees, all-market and selected/rejected performance](research/CFB_PERFORMANCE_AUDIT.md).
The game sample is removed; P&L and model edge accumulate at trade time, with
61,205 eligible YES-taker prints and separate model-coverage counts.

Selection follow-up: [exposure-adjusted diagnosis, walk-forward validation and new research components](research/CFB_SELECTION_RESEARCH.md).
Includes reusable forensic plots, quote-policy accounting, a delayed Pinnacle
anchor estimator, and a bounded three-source shadow capture with explicit
pricing-readiness checks.

MLB follow-up: [substantial native universe, paired exchange-model portfolios and three-source access status](research/MLB_MODEL_RESEARCH_20260907.md).
Includes complete-day constrained/unconstrained curves, leg-count and exposure
cuts, reusable collection tools, verified runtime throughput improvements and
Pinnacle mapping review.

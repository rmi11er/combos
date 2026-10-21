"""Render a saved public-tape review without touching runtime inputs."""
import argparse
from collections import Counter,defaultdict
import datetime as dt
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

p=argparse.ArgumentParser();p.add_argument('directory',type=Path);a=p.parse_args();root=a.directory
s=json.loads((root/'summary.json').read_text())
quotes=[json.loads(l) for l in (root/'quotes.jsonl').read_text().splitlines()]
qs={q['quote_key']:q for q in quotes};fills=json.loads((root/'fill_proxy_0s.json').read_text())
marks=[json.loads(l) for l in (root/'markouts.jsonl').read_text().splitlines()]
accepted=[q for q in quotes if q['status']=='shadow_quote']
fixtures=defaultdict(float)
for f in fills:
    for fixture in qs[f['quote_key']]['pricing']['fixtures']:fixtures[fixture]+=f['liability_dollars']
by_market=defaultdict(float)
for f in fills:by_market[f['ticker']]+=f['point_edge_dollars']
match_quantities=Counter()
for f in fills:match_quantities[f['quote_key']]+=f['quantity']
matched_marks=[]
for m in marks:
    if m['quote_key'] not in match_quantities or m['status']!='observed':continue
    q=qs[m['quote_key']];qty=match_quantities[m['quote_key']]
    # This comparison is only valid when the benchmark follows the assumed fill.
    eligible_qty=sum(f['quantity'] for f in fills if f['quote_key']==m['quote_key'] and f['at']<=m['observed_at'])
    matched_marks.append(dict(quote_key=m['quote_key'],horizon=m['horizon_seconds'],quantity=eligible_qty,
        model_mtm_dollars=eligible_qty*(q['yes_ask']-m['fair']-q['economics']['maker_fee']/q['quantity']),
        fair_move_dollars=-eligible_qty*m['adverse_move_cents']/100))
(root/'matched_model_marks.json').write_text(json.dumps(matched_marks,indent=2))
fig,axes=plt.subplots(2,3,figsize=(17,10),layout='constrained')
axes[0,0].hist([100*q['economics']['expected_edge']/q['quantity'] for q in accepted],bins=30,label='After stressed reference')
axes[0,0].set(title='Charged edge per quoted contract',xlabel='Cents',ylabel='Quotes')
axes[0,1].scatter([q['pricing']['dependence']['reserve_cents'] for q in accepted],
    [100*q['point_economics']['expected_edge']/q['quantity'] for q in accepted],s=7,alpha=.3)
axes[0,1].set(title='Correlation charge vs point-model edge',xlabel='Dependence-only charge (cents)',ylabel='Point-model edge (cents)')
delays=list(s['fill_proxy_sensitivity']);axes[0,2].bar(delays,[s['fill_proxy_sensitivity'][k]['matched_quotes'] for k in delays])
axes[0,2].set(title='Hypothetical matches by added delay',xlabel='Additional delay (seconds)',ylabel='Distinct quotes')
axes[0,2].set_ylim(0,1)
axes[0,2].text(.5,.6,'0 qualifying matches at every tested delay',transform=axes[0,2].transAxes,ha='center') if not fills else None
if fills:
    times=[dt.datetime.fromtimestamp(f['at']) for f in fills]
    axes[1,0].plot(times,np.cumsum([f['point_edge_dollars'] for f in fills]),label='Point-model edge')
    axes[1,0].plot(times,np.cumsum([f['charged_edge_dollars'] for f in fills]),label='After stressed reference')
    axes[1,0].legend();axes[1,0].tick_params(axis='x',rotation=25)
else:
    comparisons=json.loads((root/'active_quote_trade_comparisons.json').read_text())
    axes[1,0].scatter([100*r['quote_yes_ask'] for r in comparisons],[100*r['trade_yes_price'] for r in comparisons],alpha=.5)
    axes[1,0].plot([20,40],[20,40],ls='--',color='gray',label='Trade equals ask');axes[1,0].legend()
    axes[1,0].set(title='Public trade prices during quote lifetime',xlabel='Our YES ask (cents)',ylabel='Public YES print (cents)')
if fills:axes[1,0].set(title='Cumulative matched model edge — NOT equity',ylabel='Dollars')
hs=sorted(s['markouts'],key=float)
axes[1,1].bar(hs,[s['markouts'][h]['observed'] for h in hs]);axes[1,1].set(title='Model-markout coverage (all quotes)',xlabel='Horizon (seconds)',ylabel='Observed marks')
items=sorted(fixtures.items(),key=lambda kv:kv[1],reverse=True)[:8]
axes[1,2].barh([k for k,v in items][::-1],[v for k,v in items][::-1]);axes[1,2].set(title='Matched liability by fixture (overlapping)',xlabel='Dollars, no settlement release')
if not items:
    axes[1,2].clear()
    corr=s['correlation_charge_cents']['mean'];total=s['total_reference_reserve_cents']['mean'];edge=s['charged_edge_cents']['mean']
    axes[1,2].bar(['Marginal uncertainty','Dependence stress','Residual edge'],[total-corr,corr,edge],color=['#729fcf','#e9b34c','#78a879'])
    axes[1,2].set(title='Average ask-minus-point decomposition',ylabel='Cents per contract')
fig.suptitle('September 9 shadow review | public prints are hypothetical fill evidence',fontsize=16)
fig.savefig(root/'performance.png',dpi=140);plt.close(fig)
lines=['# September 9 shadow performance review','',
    f"Capture cutoff: {s['cutoff']}. Both preserved production shadow sessions are included.",'',
    'The strict public-tape reconstruction found no fills at our posted prices. Some markets traded while our quotes were valid, but those prices were below our asks. This sample supports investigating quote competitiveness; it does not establish profitable live execution.', '',
    '## Results','',
    f"- Shadow quotes: {s['quote_count']:,}; distinct combo markets: {s['unique_quoted_markets']:,}.",
    f"- Quoted cases with a later public trade: {s['quotes_with_later_public_trades']:,}; trades during quote life: {s['quotes_with_trade_during_life']:,}.",
    f"- Complete public-tape requests: {s['complete_tapes']}/{s['total_tapes']}.",
    f"- Blocked quote counterfactuals retained: {s['blocked_counterfactual_quotes']}.",'',
    '## Quote economics','',
    '| Metric | Mean | Median | 95th percentile |','|---|---:|---:|---:|']
for k in ('charged_edge_cents','point_edge_cents','correlation_charge_cents','total_reference_reserve_cents','latency_seconds'):
    d=s[k];lines.append(f"| {k} | {d.get('mean',0):.4f} | {d.get('p50',0):.4f} | {d.get('p95',0):.4f} |")
lines+=['','The dependence-only charge and total reference reserve are different: the latter also includes marginal probability uncertainty. The 0.05 rho is an assumption, not an estimated correlation.','',
    '## Public-tape fill proxies','',
    '| Added delay | Quotes | Contracts | Point-model edge ($) | Charged edge ($) | Held liability ($) |','|---|---:|---:|---:|---:|---:|']
for k,v in s['fill_proxy_sensitivity'].items():
    lines.append(f"| {k}s | {v['matched_quotes']} | {v['contracts']:.2f} | {v['point_edge_dollars']:.2f} | {v['charged_edge_dollars']:.2f} | {v['liability_if_held']:.2f} |")
lines+=['', 'Matching requires exact ticker, YES taker, public YES price at least our YES ask, and a trade after decision completion plus added delay but before expiry/cancellation/cutoff. Trade volume is allocated chronologically and never reused within a scenario. Hypothetical executions use our quote price; public prints are comparison prices, not an entitlement to price improvement.', '',
    'RFQ acceptance and queue priority are unobserved. These are conditional participation scenarios, not observed fills or an unbiased fill-probability estimate. Missing tape coverage is censored, not evidence of no trade.', '',
    '## Markouts and risk','',
    '| Horizon | Observed / total | Mean adverse fair move (cents) | Mean residual charged edge (cents) |','|---|---:|---:|---:|']
for h,d in s['markouts'].items():lines.append(f"| {h}s | {d['observed']} / {d['total']} | {d['adverse_move_cents'].get('mean',0):.4f} | {d['residual_charged_edge_cents'].get('mean',0):.4f} |")
lines+=['', 'These marks reuse the same pricing model, so they test model stability rather than independent price accuracy. `matched_model_marks.json` includes marks after hypothetical fills only. Unobserved or unavailable marks are not imputed.', '',
    'The cumulative chart is matched model edge, not realized P&L or account equity. Settlement P&L, portfolio drawdown, Sharpe, and deployable bankroll growth are not yet identified. A later inventory replay must carry hypothetical filled positions through settlement instead of recycling expired shadow reservations. The scenarios above do not reapply bankroll/fixture caps to this accumulated inventory.', '',
    '## Correlation filter and blacklist','']
for run in s['runs']:
    lines += [f"### {run['run']}",'',f"Frozen rho: {run['correlation_rho']}; tail filter: `{json.dumps(run['correlation_tail'])}`.",'',
        f"Final consumers: `{json.dumps(run.get('consumers',[]))}`. Residual event lag includes shutdown events; unprocessed RFQs, if any, are not fabricated as quotes.", '',
        f"Markout table status counts: `{json.dumps(run.get('markout_status_counts',{}))}`. Pending marks at shutdown are censored.", '',
        '| Decision | Reason | Count |','|---|---|---:|']
    lines += [f'| {st} | {reason or "—"} | {count:,} |' for st,reason,count in run['decisions']]
lines += ['', 'No rejection or blocked quote is evidence of a profitable filter by itself. Where there are no blocked counterfactual quotes, blacklist P&L impact is unidentifiable. The collector filtered RFQs before creator processing, so creator history covers only the retained universe; it is not equivalent to the original all-RFQ behavior model.', '',
    '## Competitiveness during quote lifetime','',
    'Quote/trade pairs below may share the same public trade; they are not independent observations.', '',
    '```json',json.dumps(s.get('active_trade_comparison',{}),indent=2),'```','',
    'The tail threshold is frozen at 23.9065 cents of total stressed-upper-minus-point reserve. It is not a freshly estimated top percentile of this NFL sample. Removing charges requires independent calibration and out-of-sample testing; a more competitive price alone does not establish positive expected return.', '',
    '## Next research priorities','',
    '1. Test reference-reserve and rho sensitivity against the recovered tape, keeping the tail filter separate. Preserve out-of-sample fixtures and avoid treating repeated requests as independent samples.',
    '2. Recompute independent post-quote marks and investigate missing model-markout windows. Longer-horizon coverage is too incomplete for a reliable adverse-selection conclusion.',
    '3. Restore compact public-trade capture and broader creator-history evidence without recreating the oversized raw stream.',
    '4. Once plausible fills exist, simulate persistent inventory, cash collateral, fixture caps, settlement timing, and costs before constructing equity or scaling bankroll.', '',
    '## Artifacts and source','',
    '- [Performance chart](performance.png)',
    '- [Summary](summary.json)',
    '- [Full quote features](quotes.jsonl)',
    '- [Per-quote public trade context](quote_trade_context.json)',
    '- [Matched model marks](matched_model_marks.json)',
    '- `public_tape/`: original paginated API responses and retrieval times.',
    '- [Kalshi public trades API](https://docs.kalshi.com/api-reference/market/get-trades)',
    '- [Kalshi trade direction semantics](https://docs.kalshi.com/getting_started/order_direction)', '']
(root/'REPORT.md').write_text('\n'.join(lines))
print(root/'REPORT.md')

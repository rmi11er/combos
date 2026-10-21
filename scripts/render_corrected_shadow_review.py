"""Detailed counterfactual report from frozen quote and recovered tape artifacts."""
import argparse,json
from pathlib import Path
from collections import defaultdict
import datetime as dt
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

p=argparse.ArgumentParser();p.add_argument('directory',type=Path);a=p.parse_args();root=a.directory
s=json.loads((root/'summary.json').read_text());pairs=json.loads((root/'trade_price_comparisons.json').read_text())
fills=json.loads((root/'edge_0.003_delay_0.json').read_text());validation=json.loads((root/'fill_time_validation.json').read_text())
qs={q['quote_key']:q for q in map(json.loads,(root/'corrected_quotes.jsonl').read_text().splitlines())}
base=s['scenarios']['edge_0.003_delay_0'];groups=defaultdict(list)
for f in fills:groups[f['ticker']].append(f)
market_ids={ticker:'M'+str(i+1) for i,ticker in enumerate(sorted(groups))}
by_market=[]
for ticker,fs in groups.items():
    q=qs[fs[0]['quote_key']];contracts=sum(f['quantity'] for f in fs)
    by_market.append(dict(id=market_ids[ticker],ticker=ticker,legs=q['request']['mve_selected_legs'],
        quotes=len({f['quote_key'] for f in fs}),contracts=contracts,
        public_vwap=sum(f['public_yes_price']*f['quantity'] for f in fs)/contracts,
        quote_vwap=sum(f['hypothetical_yes_price']*f['quantity'] for f in fs)/contracts,
        edge=sum(f['point_edge_dollars'] for f in fs),liability=sum(f['liability_dollars'] for f in fs)))
(root/'market_breakdown.json').write_text(json.dumps(by_market,indent=2))
fig,ax=plt.subplots(2,3,figsize=(17,10),layout='constrained')
ax[0,0].scatter([100*r['public_price'] for r in pairs],[100*r['old_ask'] for r in pairs],label='Original ask',alpha=.5)
ax[0,0].scatter([100*r['public_price'] for r in pairs],[100*r['new_ask'] for r in pairs],label='Corrected ask',alpha=.5)
ax[0,0].plot([20,40],[20,40],ls='--',color='gray');ax[0,0].legend();ax[0,0].set(title='Competitiveness during valid quote windows',xlabel='Public YES price (cents)',ylabel='Our YES ask (cents)')
ax[0,1].hist([r['public_minus_new_cents'] for r in pairs],bins=12);ax[0,1].axvline(0,color='black');ax[0,1].set(title='Public print minus corrected ask',xlabel='Cents; positive meets our price',ylabel='Quote/trade comparisons (not independent)')
delays=[0,.1,.25,.5,1];ax[0,2].bar([str(d) for d in delays],[s['scenarios'][f'edge_0.003_delay_{d}']['contracts'] for d in delays]);ax[0,2].set(title='Conditional matched volume',xlabel='Additional response delay (seconds)',ylabel='Contracts')
ax[1,0].plot([dt.datetime.fromtimestamp(f['at']) for f in fills],np.cumsum([f['point_edge_dollars'] for f in fills]),drawstyle='steps-post')
ax[1,0].set(title='Cumulative model edge on matched volume',ylabel='Dollars — not realized P&L or equity');ax[1,0].tick_params(axis='x',rotation=20)
hs=['5','30','120'];ax[1,1].bar(hs,[100*s['markouts'][h]['observed']/s['original_quotes'] for h in hs]);ax[1,1].set_ylim(0,100);ax[1,1].set(title='Observed model marks / all quotes',xlabel='Horizon (seconds)',ylabel='Coverage (%)')
ax[1,2].bar([r['id'] for r in by_market],[r['liability'] for r in by_market]);ax[1,2].set(title='Hypothetical held collateral by market',ylabel='Dollars; no settlement recycling')
fig.suptitle('Corrected strategy: three-venue point fair + 0.30¢ minimum, rounded to ticks',fontsize=15)
fig.savefig(root/'corrected_performance.png',dpi=145);plt.close(fig)

def table(headers,rows):
    return ['| '+' | '.join(headers)+' |','|'+'|'.join(['---']*len(headers))+'|']+['| '+' | '.join(map(str,r))+' |' for r in rows]
cooldowns=[x for r in s['blacklist']['runs'] for x in r['cooldowns']]
lines=['# Corrected September 9 shadow strategy reconstruction','',
    '## Finding','',
    f"Removing the unintended price reserves changes the strict tape result from zero to {base['quote_count']} candidate quote fills, {base['contracts']:.2f} contracts across {base['market_count']} markets. The corrected average charge is {s['economics']['corrected_edge_cents']['mean']:.3f} cents above the same recorded three-venue point fair. This is evidence of substantially improved price competitiveness on a small observed trading sample, not verified customer acceptance or settlement profit.", '',
    'The original run remains stopped at the requested 19:20 Central cutoff. This reconstruction uses both preserved sessions (16:11 and 17:24 starts), excludes failed recovery tests, and preserves original data.', '',
    '## Exact policy and reconstruction boundary','',
    '- Same recorded Kalshi / Polymarket / Pinnacle blended point probabilities; no switch to a Kalshi-only model.',
    '- YES ask = lowest permitted tick meeting point fair + 0.003 dollars per contract + recorded maker fee. Maker fees in these quotes are zero. The resulting average charge is about 0.35 cents.',
    '- The rho 0.05 stress calculation remains available for the tail filter, but contributes no additional quote-price charge. The frozen rejection threshold remains 23.9065 cents of stressed upper minus point fair.',
    '- Recompute RFQ target-cost quantities at the corrected price and enforce the $250 ticket liability cap. Fixed-count requests retain their requested size subject to that cap.',
    '- Primary sample is the same 2,257 recorded eligible quotes. It does not invent prices for stale/unmapped requests or automatically revive 47 original contract-risk rejections. This is an opportunity-matched reconstruction, not a full event-by-event counterfactual of the entire live engine.',
    '- Primary matching preserves recorded cancellations and expirations. Removing price reserves could change intermediate repricing/cancellation decisions. An expiry-only sensitivity is provided; it is not the primary result.', '',
    '## Volume and competition','']
lines+=table(['Measure','Result'],[
    ['Original eligible quotes',s['original_quotes']],['Distinct quoted markets',310],
    ['Quotes with any later public trade before cutoff',s['competitiveness']['quotes_with_later_trades']],
    ['Quotes with a trade during recorded valid lifetime',s['competitiveness']['quotes_with_active_trades']],
    ['Distinct trades / markets during those windows',f"{s['competitiveness']['unique_trades']} / {s['competitiveness']['unique_markets']}"],
    ['Corrected conditional quote matches',f"{base['quote_count']} ({100*base['quote_count']/s['original_quotes']:.2f}% of all quotes)"],
    ['Matched contracts',f"{base['contracts']:.2f}"],['Point-model expected edge at our prices',f"${base['model_edge_dollars']:.4f}"],
    ['Point-model edge if priced at observed prints (comparison only)',f"${base['public_price_edge_at_quote_fair_dollars']:.4f}"],
    ['Held collateral / maximum aggregate loss before settlement',f"${base['collateral_dollars']:.4f}"]])
lines+=['', 'Public prints must be on the exact ticker, YES-taker direction, at or above our corrected YES ask, and after decision completion plus response delay but before the recorded invalidation/expiry. Printed contract volume is assigned chronologically once per scenario across overlapping quotes. Multiple RFQs on one ticker do not create additional trade volume.', '',
    f"All {len(validation)} candidate allocations pass an additional as-of feed-state and point-edge check at their trade timestamps. This reconstructs observation/fixture/reset state in event order. It does not recover the exact historical worker scheduling or prove there was no earlier counterfactual cancellation.", '',
    'RFQ acceptance, queue position, and whether the print belongs to our particular request remain unobserved. Public print times may follow private acceptance/confirmation; the strict three-second window can miss that lifecycle. Conversely, a matching print does not guarantee we would receive it.', '',
    '## Trade price versus charge','']
lines+=table(['Metric across valid-window quote/trade pairs','Mean (cents)','Median (cents)'],[
    ['Original ask minus public print',f"{np.mean([r['old_minus_public_cents'] for r in pairs]):.3f}",f"{np.median([r['old_minus_public_cents'] for r in pairs]):.3f}"],
    ['Public print minus corrected ask',f"{s['competitiveness']['public_minus_new_cents']['mean']:.3f}",f"{s['competitiveness']['public_minus_new_cents']['median']:.3f}"],
    ['Public print minus recorded point fair',f"{s['competitiveness']['public_minus_fair_cents']['mean']:.3f}",f"{s['competitiveness']['public_minus_fair_cents']['median']:.3f}"]])
lines+=['',f"{s['competitiveness']['quote_trade_pairs_meeting_price']} of {len(pairs)} quote/trade pairs meet the corrected price, before allocating shared trade volume. These pairs are dependent. Equal-weighting the nine markets produces a mean public-minus-ask gap of {s['competitiveness']['market_equal_weight_gap_mean_cents']:.3f} cents: recurring activity in a few competitive markets improves the pair-weighted average. The exploratory market-resampling 95% interval is {s['competitiveness']['exploratory_market_bootstrap_95pct']}; nine markets are insufficient for a strong generalization.", '',
    f"Across all quotes the average price reduction is {s['economics']['reduction_cents']['mean']:.3f} cents; median {s['economics']['reduction_cents']['median']:.3f} cents. Recomputed offered quantities total {s['economics']['requested_contracts']:,.2f} contracts versus {s['economics']['original_contracts']:,.2f} originally. These sums include repeated RFQs and are not executable volume.", '',
    '## Market-level candidate fills','']
lines+=table(['Market','Quotes','Contracts','Our VWAP (¢)','Public VWAP (¢)','Model edge ($)','Collateral ($)'],[
    [r['id'],r['quotes'],f"{r['contracts']:.2f}",f"{100*r['quote_vwap']:.3f}",f"{100*r['public_vwap']:.3f}",f"{r['edge']:.4f}",f"{r['liability']:.2f}"] for r in by_market])
for r in by_market:
    lines+=['',f"**{r['id']}** — `{r['ticker']}`",'',*['- '+l['market_ticker']+' / '+l['side'] for l in r['legs']]]
lines+=['', 'All candidate fills are two-leg combos. The original sample also contains 117 three-leg and 38 four-leg quotes, with no candidate matches in this tape reconstruction.', '',
    'All three matched markets share the same Seattle spread leg (`KXNFLSPREAD-26SEP09NESEA-SEA4`, YES). The nine matched quotes therefore have substantial common-event exposure; they are not nine independent betting outcomes. All $181.61 of gross hypothetical collateral is exposed to that shared fixture.', '',
    '## Edge and response-latency sensitivity','']
lines+=table(['Minimum edge','Added delay','Quote matches','Contracts','Model edge ($)'],[
    [f'{edge*100:.2f}¢',f'{delay}s',s['scenarios'][f'edge_{edge}_delay_{delay}']['quote_count'],f"{s['scenarios'][f'edge_{edge}_delay_{delay}']['contracts']:.2f}",f"{s['scenarios'][f'edge_{edge}_delay_{delay}']['model_edge_dollars']:.4f}"]
    for edge in (.003,.0035) for delay in (0,.25,.5,1)])
lines+=['',f"Ignoring cancellations but retaining expiry yields {s['expiry_only_sensitivity']['quote_count']} quote matches and {s['expiry_only_sensitivity']['contracts']:.2f} contracts. This bounds the influence of recorded cancellation handling in the matched sample; it does not justify extending quotes live.",'',
    '## Longer-window trade context — not fills','',
    'These counts ignore cancellation/expiry and compare later prints against the old quote-time fair. They diagnose public reporting timing and repeat market activity, not achievable executions. End-of-capture windows can be censored.','']
lines += [f"Among the 1,426 quotes with any later print, the median delay to the first print is {s['first_later_trade_delay_seconds']['median']:.1f} seconds. A later ticker match is frequently several minutes removed from the RFQ and is not evidence that this RFQ traded.",'']
lines+=table(['Seconds after decision','Fully observed windows','Quotes with any print','Quotes with price-compatible YES print'],[
    [h,d['fully_observed_quotes'],d['quotes_with_public_trade'],d['quotes_with_price_compatible_yes_trade']] for h,d in s['diagnostic_windows_ignoring_expiry_and_cancellation'].items()])
lines+=['','## Markouts','', 'Model marks are recomputed as corrected ask minus later three-venue point fair minus maker fees. They do not reuse the old stressed-reference net edge.','']
lines+=table(['Horizon','Observed / all quotes','Mean remaining edge (¢)','Negative remaining edge','Matched quantity observed','Matched model value ($)'],[
    [h+'s',f"{d['observed']}/{d['quote_denominator']}",f"{d['residual_edge_cents']['mean']:.4f}",d['negative_residual'],f"{d['matched_quantity']:.2f}",f"{d['matched_model_value_dollars']:.4f}"] for h,d in s['markouts'].items()])
lines+=['','Model stability is not proof of forecast calibration. Missing marks are excluded; different horizons describe different surviving subsets. Values across horizons must not be added.','',
    'For an independent but sparse comparison, use the first subsequent public print at/after each fill-relative horizon, allowing 30 seconds of grace. This is a mark-to-print, not an executable liquidation price; it may include spread effects.','']
lines+=table(['Horizon','Observed allocations / total','Contracts observed','Mean mark (¢)','Aggregate mark ($)'],[
    [h+'s',f"{d['allocations_observed']}/{d['allocations_total']}",f"{d['quantity']:.2f}",f"{d['markout_cents'].get('mean',0):.4f}" if d['allocations_observed'] else 'Unavailable',f"{d['markout_dollars']:.4f}" if d['allocations_observed'] else 'Unavailable'] for h,d in s['public_marks'].items()])
lines+=['','The available independent short-horizon marks are adverse even though same-model marks remain positive. The small, incomplete independent sample does not establish the sign of true expected P&L.','',
    '## Blacklist activity and efficacy','',
    f"There were {len(cooldowns)} cooldown transitions across {len({r['creator'] for r in cooldowns})} distinct creator IDs, affecting {sum(r['affected_rfq_ids'] for r in s['blacklist']['runs']):,} retained RFQs within their recorded cooldown windows. The quote cohort contains 2,252 clear-state and five watch-state quotes. None was a fully priceable blocked/cooldown counterfactual.",'']
for run in s['blacklist']['runs']:
    lines += [f"### {run['run']}",'',*table(['Decision reason for requests during cooldown','Count'],list(run['affected_decision_reasons'].items())),'']
lines+=['The blacklist was active, but there is no identified incremental avoided trading loss in this priced cohort. Other eligibility gates excluded those requests first. Disabling the blacklist therefore adds zero observed fully priced quotes in this reconstruction; that does not prove the blacklist is useless.', '',
    'Creator state restarted with the second database and only retained collection-candidate RFQs were processed. This truncates behavior history compared with an all-RFQ behavioral backtest. Efficacy needs counterfactual fair values for excluded requests plus independent adverse-selection labels, which this capture does not provide.', '',
    '## Correlation filter and risk','',
    'The frozen tail filter remains enabled, and no correlation-tail rejection appears in the recorded decision reason counts. It therefore had no observed marginal exclusion in this sample. The fixed historical 23.9065-cent threshold is not the top 1% of tonight’s NFL distribution.', '',
    f"A conservative held-inventory check carries all candidate fill liability through cutoff, across the session restart: ${base['collateral_dollars']:.2f}. It applies $10,000 capital, $500 contract/combo and $1,000 fixture caps (with recorded risk multipliers); {s['held_inventory_scenario']['risk_rejected_allocations']} candidate allocations are rejected. No settlement cash is recycled. This check uses gross buckets and does not simulate every pending RFQ reservation or signed hedge credit.", '',
    '## Interpretation and next steps','',
    '1. The reserve-loaded rollout did not test the specified pricing strategy. Corrected prices are competitive with some observed trades, supporting another properly configured shadow session.',
    '2. The strict realized-volume proxy is small: nine quotes on three markets. More quote activity is not equivalent to more executable volume. Private RFQ lifecycle/acceptance timing and compact trade capture should be measured next.',
    '3. Retain the distinction between 0.30-cent minimum plus rounding and a literal 0.35-cent minimum. Both are reported rather than silently changing the specified hurdle.',
    '4. Repair missing markout coverage and preserve creator history across restarts before claiming blacklist or adverse-selection improvements.',
    '5. Settlement P&L and equity are not available. The plotted cumulative expected edge is a model quantity, and no pending profit is treated as spendable cash.', '',
    '## Reproducible outputs','',
    '- [Charts](corrected_performance.png)',
    '- [Summary JSON](summary.json)',
    '- [Corrected quote features](corrected_quotes.jsonl)',
    '- [Quote/public-price comparisons](trade_price_comparisons.json)',
    '- [Candidate fills](edge_0.003_delay_0.json)',
    '- [As-of fill-time feed validation](fill_time_validation.json)',
    '- [Corrected model marks](corrected_model_marks.json)',
    '- [Independent public-print marks](public_print_marks.json)',
    '- [Held inventory scenario](held_inventory_scenario.json)',
    '- [Corrected runtime candidate](corrected_runtime_candidate.json) — separate artifact; not launched.',
    '- Original quote features and complete public tape: `../shadow_review_20260909_1920/`.', '']
(root/'REPORT.md').write_text('\n'.join(lines));print(root/'REPORT.md')

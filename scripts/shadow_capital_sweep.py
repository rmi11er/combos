"""Public-tape denominator and quote-edge sensitivity; not actual fills."""
import json
from collections import defaultdict
from pathlib import Path
from corrected_shadow_review import reconstruct, funded, fillstats
from shadow_trade_review import match, stamp

ROOT=Path(__file__).resolve().parents[1]
D=ROOT/'runs/shadow_consensus_replay_20260909'
quotes=[json.loads(l) for l in (D/'source/quotes.jsonl').read_text().splitlines()]
cutoff=stamp(json.loads((D/'source/summary.json').read_text())['cutoff'])
tapes={json.loads(p.read_text())['ticker']:json.loads(p.read_text()) for p in (D/'source/public_tape').glob('*.json')}
groups=defaultdict(list)
for q in quotes:groups[q['market_ticker']].append(q)
cohorts=defaultdict(dict)
for ticker,tape in tapes.items():
    assert tape['complete']
    first=min(q['decision_completed_at'] for q in groups[ticker])
    for t in tape['trades']:
        at=stamp(t['created_time'])
        if not first<=at<=cutoff:continue
        row=dict(t,ticker=ticker)
        cohorts['quoted_markets_after_first_quote'][t['trade_id']]=row
        if (t.get('taker_outcome_side') or t.get('taker_side'))=='yes':
            cohorts['quoted_markets_yes_taker'][t['trade_id']]=row
        active=any(q['decision_completed_at']<=at<q['valid_until'] for q in groups[ticker])
        if active:
            cohorts['active_quote_windows'][t['trade_id']]=row
            if (t.get('taker_outcome_side') or t.get('taker_side'))=='yes':
                cohorts['active_quote_windows_yes_taker'][t['trade_id']]=row

def totals(rows):
    rows=list(rows)
    return dict(trades=len(rows),markets=len({r['ticker'] for r in rows}),
        block_trades=sum(r.get('is_block_trade') is True for r in rows),
        non_block_trades=sum(r.get('is_block_trade') is False for r in rows),
        contracts=sum(float(r['count_fp']) for r in rows),
        yes_buyer_capital=sum(float(r['count_fp'])*float(r['yes_price_dollars']) for r in rows),
        yes_seller_capital=sum(float(r['count_fp'])*(1-float(r['yes_price_dollars'])) for r in rows))

denominators={k:totals(v.values()) for k,v in cohorts.items()}
sweep={}
for edge in (.0035,.003,.0025,.002,.0015,.001,.0005,0.):
    qs=[reconstruct(q,edge) for q in quotes]
    fills=match(qs,tapes,0);held=funded(fills,{q['quote_key']:q for q in qs})
    sweep[str(edge)]=dict(**fillstats(fills),held_inventory=fillstats(held['fills']),
        risk_rejected_allocations=len(held['rejected']),
        matched_public_seller_collateral=sum(f['quantity']*(1-f['public_yes_price']) for f in fills))
out=dict(basis='Unique public prints in 310 quoted tickers, per-ticker first completed quote through 19:20. Not the full RFQ universe. Seller collateral assumes unhedged YES selling; no public fees or margin offsets.',
    denominators=denominators,sweep=sweep)
(D/'results/capital_sweep.json').write_text(json.dumps(out,indent=2)+'\n')
lines=['# Capital utilization and edge sensitivity','',
'No actual fills or capital deployment occurred. The baseline represents ten potential quote matches across four markets, with eleven allocations against ten unique public trades.', '',
'## Denominators','',
'Across 310 quoted tickers, from each ticker\'s first completed quote through 19:20 Central: 206 unique public trades across 50 markets, 25,559.18 contracts. At recorded prices the unhedged YES seller side represents $18,826.71; the YES buyer side $6,732.47. Both sides together sum to $25,559.18. These are turnover amounts, not measured peak margin.', '',
'For the 203 YES-taker trades comparable to our YES-selling direction: seller collateral is $18,750.42. Within actual recorded quote lifetimes: 15 trades / $1,032.24 seller collateral. Our matched quantity accounts for $198.83 at public prices (19.26% of active-window volume, 1.06% of broader directional volume), versus $199.19 required at our hypothetical asks. Only about 5.5% of broader directional traded collateral coincided with active quotes.', '',
'IMPORTANT: all 206 cached public trades have is_block_trade=false. This is not observed RFQ acceptance or an RFQ turnover denominator. The public tape includes block trades by default according to https://docs.kalshi.com/api-reference/market/get-trades, but none is flagged in this captured subset. We do not have total RFQ-traded collateral across the full platform or full eligible universe.', '',
'## Minimum-edge sweep','',
'| Minimum charge (cents) | Candidate quote matches | Markets | Contracts | Collateral ($) | Quote-time model EV ($) |',
'|---|---|---|---|---|---|']
for k,v in sweep.items():
    lines.append(f"| {float(k)*100:.2f} | {v['quote_count']} | {v['market_count']} | {v['contracts']:.2f} | {v['collateral_dollars']:.2f} | {v['model_edge_dollars']:.3f} |")
lines += ['', 'All scenarios retain the replayed consensus fair, recorded quote lifetimes and opportunity cohort, target-cost sizing, $250 ticket cap, correlation filter, creator eligibility, and held-inventory risk check. None had a held-inventory rejection. Pending reservations, altered cancellations, new acceptance behavior, and fill-time checks at each alternative hurdle are NOT re-simulated. The baseline alone has separate fill-time validation.', '',
'The 0.20-cent scenario is a candidate for a parallel shadow experiment, not a calibrated production optimum. Its gain is dominated by one additional large trade; going to 0.10 cents adds almost no volume and reduces model EV. No live/runtime pricing setting was changed. Improving eligible RFQ coverage and measuring true acceptance is more fundamental than filling capital at any price. Total portfolio capacity is a ceiling, not a deployment target; event concentration remains important.']
(D/'results/CAPITAL_REVIEW.md').write_text('\n'.join(lines)+'\n')
print(json.dumps(out,indent=2))

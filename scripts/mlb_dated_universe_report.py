#!/usr/bin/env python3
"""Stream complete dated MLB cohorts into fee-inclusive, model-independent diagnostics."""
import argparse
from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal
import gzip
import hashlib
import json
import math
from pathlib import Path
import sqlite3
import tempfile
from zoneinfo import ZoneInfo

ZONE = ZoneInfo('America/Chicago')
CUTS = ('legs', 'structure', 'family', 'phase', 'premium')


def digest(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def stamp(value):
    at = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if at.tzinfo is None:
        raise ValueError('timezone_required')
    return at.timestamp()


def check_cohort(path):
    summary = json.loads((path / 'summary.json').read_text())
    day = datetime.fromisoformat(summary['date']).replace(tzinfo=ZONE)
    start, end = day.timestamp(), (day + timedelta(days=1)).timestamp()
    if not summary.get('complete_census') or summary['start_at'] != start or summary['end_at'] != end:
        raise ValueError('complete_calendar_date_required')
    sources = sorted(summary['sources'], key=lambda s: s['start_at'])
    cursor = start
    for source in sources:
        if source.get('method') != 'census' or source.get('sample_weight_in_replay') != 1 or source['start_at'] != cursor or source['end_at'] <= cursor:
            raise ValueError('noncontiguous_or_sampled_source')
        source_path = Path(source['path'])
        if digest(source_path) != source['sha256']:
            raise ValueError('source_manifest_hash_mismatch')
        cursor = source['end_at']
    if cursor != end:
        raise ValueError('incomplete_source_windows')
    return summary


def zero():
    return dict(prints=0, known_prints=0, unknown_prints=0, known_net_pnl=0.,
                unknown_lower=0., unknown_upper=0., yes_premium=0., payout_notional=0.,
                maker_fees=0., cumulative_no_cash=0., unknown_payout_notional=0.)


def accumulate(target, row):
    for key in target:
        target[key] += row[key]


def finish(row):
    return {**row, 'final_pnl_lower': row['known_net_pnl'] + row['unknown_lower'],
            'final_pnl_upper': row['known_net_pnl'] + row['unknown_upper']}


def economics(row):
    trade = row['trade']
    q, p, fee = (Decimal(str(x)) for x in (trade['count_fp'], trade['yes_price_dollars'], row['maker_fee_dollars']))
    if not all(x.is_finite() for x in (q, p, fee)) or q <= 0 or not 0 <= p <= 1 or fee < 0:
        raise ValueError('invalid_trade_economics')
    s = row['settlement_value']
    if s is not None:
        s = Decimal(str(s))
        if not s.is_finite() or not 0 <= s <= 1:
            raise ValueError('invalid_settlement')
    known = s is not None
    pnl = float(q * (p-s) - fee) if known else 0.
    archived = row.get('seller_pnl_dollars')
    if known and archived is not None and not math.isclose(float(archived), pnl, abs_tol=1e-6):
        raise ValueError('archived_pnl_mismatch')
    return dict(prints=1, known_prints=int(known), unknown_prints=int(not known), known_net_pnl=pnl,
                unknown_lower=float(q*(p-1)-fee) if not known else 0.,
                unknown_upper=float(q*p-fee) if not known else 0.,
                yes_premium=float(q*p), payout_notional=float(q), maker_fees=float(fee),
                cumulative_no_cash=float(q*(1-p)+fee), unknown_payout_notional=float(q) if not known else 0.)


def labels(row, econ):
    c = row['classification']; n = c['nlegs']; phase = row['pregame_scheduled_proxy']
    if type(n) is not int or n < 1 or c.get('pure_mlb') is not True:
        raise ValueError('invalid_mlb_classification')
    return dict(legs=str(n) if n < 5 else '5+',
                structure='Distinct fixtures' if c['distinct_fixtures'] else 'Contains same-game legs',
                family='Full-game core' if c['fullgame_core'] else 'Includes known player prop' if c['known_player_prop'] else 'Other or unclassified',
                phase='Pregame schedule proxy' if phase is True else 'After scheduled start' if phase is False else 'Unknown schedule',
                premium='At most $10' if econ['yes_premium'] <= 10 else '$10–50' if econ['yes_premium'] <= 50 else '$50–250' if econ['yes_premium'] <= 250 else 'Above $250')


def analyze(cohorts):
    total = zero(); cuts = {k: defaultdict(zero) for k in CUTS}; curves = defaultdict(zero)
    cut_curves = {k: defaultdict(lambda: defaultdict(zero)) for k in CUTS}
    fixtures = defaultdict(zero); daily = {}; provenance = []; dates = set(); fee_sources = {}
    duplicate_rows = 0; excluded_direction = 0
    with tempfile.TemporaryDirectory(prefix='mlb-universe-dedup-') as temp:
        db = sqlite3.connect(str(Path(temp) / 'dedup.sqlite'))
        db.execute('CREATE TABLE seen (id TEXT PRIMARY KEY, hash TEXT NOT NULL)')
        try:
            for cohort in sorted(map(Path, cohorts)):
                summary = check_cohort(cohort); day = summary['date']
                if day in dates:
                    raise ValueError('duplicate_cohort_date')
                dates.add(day); daily[day] = zero(); path = cohort / 'universe_trades.jsonl.gz'; count = 0
                provenance.append({'cohort': str(cohort.resolve()), 'date': day, 'summary_sha256': digest(cohort/'summary.json'),
                                   'universe_sha256': digest(path), 'fee_scenario': summary.get('fee_scenario')})
                with gzip.open(path, 'rt') as f:
                    for line in f:
                        row = json.loads(line); count += 1; t = row['trade']; at = stamp(t['created_time'])
                        if not summary['start_at'] <= at < summary['end_at'] or row['sampling_method'] != 'census':
                            raise ValueError('row_outside_census_date')
                        canonical = hashlib.sha256(json.dumps(row, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
                        previous = db.execute('SELECT hash FROM seen WHERE id=?', (t['trade_id'],)).fetchone()
                        if previous:
                            if previous[0] != canonical:
                                raise ValueError('conflicting_duplicate_trade')
                            duplicate_rows += 1; continue
                        db.execute('INSERT INTO seen VALUES (?,?)', (t['trade_id'], canonical))
                        if t.get('taker_side') != 'yes':
                            excluded_direction += 1; continue
                        if not row.get('fee_rate_provenance'):
                            raise ValueError('archived_fee_provenance_required')
                        fee_key = json.dumps(row['fee_rate_provenance'], sort_keys=True)
                        fee_sources[fee_key] = row['fee_rate_provenance']
                        econ = economics(row); group = labels(row, econ); bucket = int(at // 300) * 300 + 300
                        for target in (total, daily[day], curves[bucket]):
                            accumulate(target, econ)
                        for key, value in group.items():
                            accumulate(cuts[key][value], econ); accumulate(cut_curves[key][value][bucket], econ)
                        for fixture in set(row['classification']['fixture_tokens']):
                            accumulate(fixtures[fixture], econ)
                if count != summary['pure_mlb_prints']:
                    raise ValueError('universe_row_count_mismatch')
                db.commit()
        finally:
            db.close()
    observed = sorted(dates)
    pnl_values = [daily[d]['known_net_pnl'] for d in observed]
    variance = (sum((p-sum(pnl_values)/len(pnl_values))**2 for p in pnl_values)/(len(pnl_values)-1)) if len(pnl_values)>1 and not total['unknown_prints'] else None
    fixture_rows = [{'fixture': key, **finish(value),
                     'known_pnl_after_exclusion': total['known_net_pnl']-value['known_net_pnl'],
                     'final_pnl_lower_after_exclusion': finish(total)['final_pnl_lower']-finish(value)['final_pnl_lower'],
                     'final_pnl_upper_after_exclusion': finish(total)['final_pnl_upper']-finish(value)['final_pnl_upper']}
                    for key, value in sorted(fixtures.items())]
    report = dict(schema_version=1, observed_dates=observed, totals=finish(total),
                  daily={d:finish(daily[d]) for d in observed}, cuts={k:{label:finish(v) for label,v in sorted(groups.items())} for k,groups in cuts.items()},
                  fixtures=fixture_rows, duplicate_identical_rows_removed=duplicate_rows,
                  opposite_or_unknown_taker_direction_excluded=excluded_direction, input_provenance=provenance,
                  fee_provenance=list(fee_sources.values()), historical_fees_verified=all(x.get('verified') is True for x in fee_sources.values()) if fee_sources else False,
                  statistics={'annualized_sharpe':None, 'observed_date_pnl_variance_dollars2':variance,
                              'reason':'Unlimited-exposure counterfactual has no funded return denominator. Variance uses only complete supplied dates, ddof=1; unavailable if fewer than two dates or unresolved outcomes. No unobserved dates are assigned zero returns.'},
                  assumptions=['YES-taker public prints interpreted as hypothetical maker sales at observed price and full observed size; no own execution claim.',
                               'All pure-MLB market families, leg counts and phases retained; no model availability, fair-price, capital or risk filter.',
                               'Archived per-print maker fees are used without substituting current rates; fee verification is reported explicitly.',
                               'Eventual outcome P&L attributed to trade time. This is not spendable equity or committed capital.',
                               'Fixture membership overlaps; exclude-fixture results remove every print involving the named fixture.',
                               'Schedule phase is a native scheduled-time proxy; unknown outcomes are bounded, never assigned a realized zero.'])
    return report, curves, cut_curves


def plot(report, curves, cuts, out):
    import matplotlib
    matplotlib.use('Agg'); matplotlib.rcParams['text.parse_math'] = False
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FuncFormatter
    fig, axes = plt.subplots(3, 2, figsize=(16, 14), layout='constrained')
    def cumulative(points):
        acc = zero(); xs=[]; values=[]
        for at, value in sorted(points.items()):
            accumulate(acc, value); xs.append(datetime.fromtimestamp(at, ZONE)); values.append(finish(acc))
        return xs, values
    xs, vals = cumulative(curves); ax = axes.flat[0]
    ax.plot(xs, [v['known_net_pnl'] for v in vals], label=f"Known net P&L ${report['totals']['known_net_pnl']:,.0f}")
    ax.fill_between(xs, [v['final_pnl_lower'] for v in vals], [v['final_pnl_upper'] for v in vals], alpha=.18, label='Unresolved outcome bounds')
    ax.plot([], [], alpha=0, label='Sharpe: N/A — unlimited exposure')
    var=report['statistics']['observed_date_pnl_variance_dollars2']
    ax.plot([], [], alpha=0, label='Observed-date P&L variance: '+('N/A' if var is None else f'{var:,.0f} USD²'))
    ax.legend(fontsize=8, loc='upper left'); ax.set_title('Entire YES-taker universe')
    volume=ax.twinx();volume.plot(xs,[v['yes_premium'] for v in vals],color='#cf8b36',ls='--',alpha=.65,label='YES premium');volume.plot(xs,[v['payout_notional'] for v in vals],color='#8265ad',ls=':',alpha=.65,label='Payout notional');volume.legend(fontsize=8,loc='lower right');volume.set_ylabel('Cumulative volume ($)');volume.yaxis.set_major_formatter(FuncFormatter(lambda x,pos:f'{x/1e6:.1f}m'))
    for ax, key in zip(list(axes.flat)[1:], CUTS):
        for label, points in sorted(cuts[key].items()):
            xx, vv = cumulative(points)
            ax.plot(xx, [v['known_net_pnl'] for v in vv], label=f"{label}: ${vv[-1]['known_net_pnl']:,.0f}")
        ax.set_title(key.capitalize());ax.legend(fontsize=8)
    for ax in axes.flat:
        ax.grid(alpha=.2); ax.axhline(0,color='gray',linewidth=.6);ax.set_ylabel('Cumulative known P&L ($)');ax.tick_params(axis='x',rotation=25);ax.yaxis.set_major_formatter(FuncFormatter(lambda x,pos:f'{x/1e6:.2f}m'))
    fig.suptitle(f"MLB complete-date universe • {len(report['observed_dates'])} observed date(s): {report['observed_dates'][0]} – {report['observed_dates'][-1]}\nArchived maker fees {'verified' if report['historical_fees_verified'] else 'UNVERIFIED scenario'} • Eventual P&L at trade time • No assumed trades on unobserved dates",fontsize=12)
    for ext in ('png','svg'):fig.savefig(out/f'universe.{ext}',dpi=160)
    plt.close(fig)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--cohort',action='append',type=Path,required=True);parser.add_argument('--out',type=Path,required=True);args=parser.parse_args()
    report, curves, cuts = analyze(args.cohort);args.out.mkdir(parents=True,exist_ok=True)
    report['script_sha256']=digest(Path(__file__))
    (args.out/'summary.json').write_text(json.dumps(report,indent=2)+'\n')
    with gzip.open(args.out/'curves.jsonl.gz','wt') as f:
        for at,value in sorted(curves.items()):f.write(json.dumps({'bucket_end_at':at,**value})+'\n')
    plot(report,curves,cuts,args.out)
    (args.out/'REPORT.md').write_text('# Dated MLB full-universe diagnostic\n\n'+f"Observed dates: {', '.join(report['observed_dates'])}. Includes {report['totals']['prints']:,} YES-taker prints without model filtering.\n\n"+f"Known eventual net P&L: ${report['totals']['known_net_pnl']:,.2f}; final bounds ${report['totals']['final_pnl_lower']:,.2f} to ${report['totals']['final_pnl_upper']:,.2f}. Historical fees verified: {report['historical_fees_verified']}.\n\n"+'\n'.join('- '+x for x in report['assumptions'])+'\n\nSee summary.json for daily contributions, all cuts, fixture-exclusion bounds and hashed provenance. Curves contain five-minute **incremental** aggregates, not cumulative values.\n')
    print(json.dumps({'out':str(args.out),'totals':report['totals'],'dates':report['observed_dates']}))


if __name__ == '__main__':
    main()

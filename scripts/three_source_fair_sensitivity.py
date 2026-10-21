"""Explicit liquidity-unit/payoff scenarios on matched captured moneyline legs."""
import argparse
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import statistics
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from combos.observations import Observation
from combos.pricing import Interval,pinnacle_fair
from combos.weighted_fair import WeightPolicy,weighted_fair


def run(inputs,weights,out):
    rows=json.loads(inputs.read_text());policy=WeightPolicy(**json.loads(weights.read_text()))
    results=[];summaries=[]
    for multiplier in (.1,1.,10.):
        for tie in (0.,.01):
            for exception in (0.,.005):
                group=[]
                for row in rows:
                    exchange=[]
                    for value in row['exchange_observations']:
                        value=dict(value);value['interval']=Interval(**value['interval']);exchange.append(Observation(**value))
                    yes,no=row['pinnacle_decimal_odds'];yl,nl=row['pinnacle_native_stake_limits']
                    original=pinnacle_fair(yes,no)
                    point=(1-tie)*original.point+.5*tie
                    lower=(1-exception)*((1-tie)*original.lower+.5*tie)
                    upper=(1-exception)*((1-tie)*original.upper+.5*tie)+exception
                    pin=Observation(row['market_key'],'pinnacle',row['pinnacle_observed_at'],
                        row['pinnacle_available_at'],True,Interval(lower,point,upper),
                        nl*no*multiplier,yl*yes*multiplier,
                        'captured_event:'+str(row['pinnacle_seq']),row['mapping_reference'],None,
                        freshness_context={'liquidity_unit_conversion_assumed':multiplier,
                            'tie_probability_assumed':tie,'exception_probability_upper_assumed':exception,
                            'exception_cash_payoff_bounds':[0,1],'research_only':True})
                    fair=weighted_fair([*exchange,pin],row['decision_at'],'pregame',policy)
                    result={'checkpoint_seq':row['checkpoint_seq'],'market_key':row['market_key'],
                        'assumed_usd_per_native_stake_unit':multiplier,'assumed_tie_probability':tie,
                        'assumed_exception_probability_upper':exception,'fair':fair['fair'],
                        'weights':{v:d['weight'] for v,d in fair['venues'].items()},
                        'fair_minus_k_cents':100*(fair['fair']['point']-exchange[0].interval.point),
                        'fair_minus_pm_cents':100*(fair['fair']['point']-exchange[1].interval.point),
                        'interval_guard_regime':fair['guard']['regime'],'sharp_agreement_vs_k':row['sharp_agreement_vs_k']}
                    group.append(result);results.append(result)
                summaries.append({'assumed_usd_per_native_stake_unit':multiplier,'assumed_tie_probability':tie,
                    'assumed_exception_probability_upper':exception,'comparisons':len(group),
                    'median_pinnacle_weight':statistics.median(r['weights']['pinnacle'] for r in group),
                    'median_absolute_fair_k_gap_cents':statistics.median(abs(r['fair_minus_k_cents']) for r in group),
                    'maximum_absolute_fair_k_gap_cents':max(abs(r['fair_minus_k_cents']) for r in group),
                    'median_agreement_absolute_fair_k_gap_cents':statistics.median(abs(r['fair_minus_k_cents']) for r in group if r['sharp_agreement_vs_k']),
                    'hard_guard_count':sum(r['interval_guard_regime']=='halt' for r in group)})
    out.mkdir(parents=True,exist_ok=False)
    summary={'scenarios':summaries,'pricing_authorized':False,'source_hashes':{str(p):hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (inputs,weights,Path(__file__),Path(__file__).resolve().parents[1]/'src/combos/weighted_fair.py')},
        'interpretation':'hypothetical unit conversions and payoff assumptions; actual exchange depth and fee intervals; no profitability test'}
    (out/'summary.json').write_text(json.dumps(summary,indent=2));(out/'rows.json').write_text(json.dumps(results))
    return summary


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('inputs','weights','out'):p.add_argument('--'+name,required=True,type=Path)
    a=p.parse_args();s=run(a.inputs,a.weights,a.out)
    print(json.dumps([r for r in s['scenarios'] if r['assumed_tie_probability']==0 and r['assumed_exception_probability_upper']==0]))

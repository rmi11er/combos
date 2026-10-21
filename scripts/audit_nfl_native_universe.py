#!/usr/bin/env python3
"""Cached NFL native-universe coverage audit; no pricing, plots or requests."""
import argparse,gzip,json,math
from collections import Counter,defaultdict
from datetime import datetime
from pathlib import Path
from mlb_dated_universe_report import check_cohort,digest

def main():
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--through',default='2026-01-12');p.add_argument('--out',type=Path,required=True);a=p.parse_args()
 state=json.loads((a.root/'days/state.json').read_text());report={'through':a.through,'days':{},'overall':{},'source':'native universe_trades.jsonl.gz, completed certified calendars only'};total=Counter();sides=Counter();series=Counter();outcomes=Counter();ids=set();duplicates=0
 for day,status in sorted(state['days'].items()):
  if day>a.through or status.get('status')!='complete':continue
  for path,h in status['output_sha256'].items():
   if digest(path)!=h:raise ValueError('certificate mismatch: '+path)
  cohort=a.root/'days'/day/'cohort';summary=check_cohort(cohort);counts=Counter();local_sides=Counter();local_outcomes=Counter()
  if summary['sport']!='NFL':raise ValueError('wrong sport')
  with gzip.open(cohort/'universe_trades.jsonl.gz','rt') as f:
   for line in f:
    r=json.loads(line);t=r['trade'];c=r['classification'];at=datetime.fromisoformat(t['created_time'].replace('Z','+00:00')).timestamp()
    if not c['pure_nfl'] or r['sampling_method']!='census' or not summary['start_at']<=at<summary['end_at']:raise ValueError('invalid native row')
    if t['trade_id'] in ids:duplicates+=1
    ids.add(t['trade_id']);counts['native_prints']+=1;counts['native_numeric_known' if r.get('settlement_value_dollars') is not None else 'native_numeric_unknown']+=1;counts['native_time_known' if r.get('settlement_ts') is not None else 'native_time_unknown']+=1;side=(t.get('taker_side'),t.get('taker_outcome_side'),t.get('taker_book_side'));local_sides[str(side)]+=1
    if t.get('taker_side')!=t.get('taker_outcome_side'):counts['side_field_disagreement']+=1
    if t.get('taker_side')!='yes':continue
    counts['yes_taker_prints']+=1;counts['yes_payout_notional']+=float(t['count_fp']);counts['yes_premium']+=float(t['count_fp'])*float(t['yes_price_dollars']);counts['legs_'+(str(c['nlegs']) if c['nlegs']<5 else '5+')]+=1;counts['distinct_fixtures' if c['distinct_fixtures'] else 'same_game_legs']+=1
    counts['fullgame_core' if c['fullgame_core'] else 'other_nfl_family']+=1;counts['target_fixtures_only' if c['target_fixtures_only'] else 'includes_other_fixture']+=1
    start=c.get('earliest_scheduled_start');counts['unknown_schedule' if start is None else 'pregame_proxy' if r['pregame_scheduled_proxy'] else 'after_schedule_cutoff']+=1
    value=r.get('settlement_value_dollars');timestamp=r.get('settlement_ts');outcome=r.get('result');local_outcomes[str((value is not None,timestamp is not None,outcome,r.get('native_status')))]+=1
    if value is None:counts['unknown_numeric_settlement']+=1
    else:
     v=float(value)
     if not math.isfinite(v) or not 0<=v<=1:raise ValueError('bad settlement')
     counts['known_numeric_settlement']+=1
     if v not in (0,1):counts['fractional_numeric_settlement']+=1;counts['fractional_value_'+str(value)]+=1
     if timestamp is None:counts['known_value_missing_settlement_time']+=1
     else:
      counts['known_value_and_time']+=1
      if datetime.fromisoformat(timestamp.replace('Z','+00:00')).timestamp()<=at:counts['settled_at_or_before_trade']+=1
    counts['fee_missing' if r.get('maker_fee_dollars') is None else 'fee_present']+=1
    for family in c['series']:series[family]+=1
  if counts['native_prints']!=summary['counts']['pure_nfl_prints']:raise ValueError('count mismatch')
  total.update(counts);sides.update(local_sides);outcomes.update(local_outcomes)
  report['days'][day]={'counts':dict(counts),'side_fields':dict(local_sides),'settlement_states':dict(local_outcomes),'summary_sha256':digest(cohort/'summary.json'),'universe_sha256':digest(cohort/'universe_trades.jsonl.gz'),'primary_candidate_prints':summary['counts'].get('primary_candidate_prints',0)}
 report.update(overall=dict(total),side_fields=dict(sides),settlement_states=dict(outcomes),yes_print_series_memberships=dict(series.most_common()),duplicate_trade_ids=duplicates)
 a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report['overall'],indent=2))
if __name__=='__main__':main()

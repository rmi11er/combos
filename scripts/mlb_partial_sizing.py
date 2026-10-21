#!/usr/bin/env python3
"""Compare whole-print and affordable partial sizing on a complete paired MLB day."""
import argparse,gzip,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from combos.backtest import BacktestConfig,run_backtest
from combos.partial_sizing_research import run_partial
from mlb_entry_sweep import paired_day

def main():
 p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--date',required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
 raw=a.input.read_bytes();data=json.loads(raw);rows,start,end,coverage=paired_day(data,a.date)
 models={r['model'] for r in rows}
 if models != {'kalshi','polymarket','exchange_blend_equal','exchange_blend_pm75'}: raise ValueError('four-model common cohort required')
 cfg=BacktestConfig(entry_basis='point');a.out.mkdir(parents=True,exist_ok=True)
 results={}
 for policy in ('full','partial'):
  result=run_backtest(rows,start,end,cfg,True) if policy=='full' else run_partial(rows,start,end,cfg)
  with gzip.open(a.out/(policy+'.json.gz'),'wt') as f:json.dump(result,f)
  results[policy]=result['summaries']
 summary={'date':a.date,'source_sha256':hashlib.sha256(raw).hexdigest(),'source_hashes':{str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest() for f in (Path(__file__).resolve(),ROOT/'src/combos/partial_sizing_research.py',ROOT/'src/combos/backtest.py',ROOT/'src/combos/risk.py',ROOT/'src/combos/fees.py',ROOT/'scripts/mlb_entry_sweep.py')},'models':sorted(models),'common_prints':len(rows)//4,'coverage':coverage,'results':results,'fees':'Dated source fee scenarios retained; recomputed for each selected quantity; direct precision .0001 and zero new-order accumulator. Historical fee verification limitations unchanged.'}
 (a.out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
 lines=['# Partial-size capacity research — '+a.date,'','Common paired cohort: '+str(len(rows)//4)+' prints per model. Actual print size is the upper bound; 0.01-contract grid; unchanged 0.3c/contract point-edge test, quote guards, risk multipliers and $10k/$100 underlying/$100 combo/$250 fixture limits. No ticket cap.','','| Policy | Model | Fills | Payout notional | Net P&L | Model edge | Peak committed cash |','|---|---|---:|---:|---:|---:|---:|']
 for policy, summaries in results.items():
  for r in summaries:
   lines.append(f"| {policy} | {r['model']} | {r['fills']} | ${r['payout_notional']:,.2f} | ${r['trade_attributed_pnl']:,.2f} | ${r['accepted_point_edge']:,.2f} | ${r['peak_committed_cash']:,.2f} |")
 lines += ['', 'P&L is known eventual settlement outcome attributed to trade time; cash and risk are released only at actual settlement. Unknown outcomes remain reserved and absent from known P&L. Full retained ledgers include outcomes, curves, decisions and per-print sizing audit. One date has no defensible daily variance/Sharpe estimate.','',summary['fees'],'','This is a hypothetical public-print capacity experiment, not an RFQ execution strategy. Largest affordable size can consume shared underlying room early and displace later prints: fewer fills and lower P&L are possible despite more total size. Observed customer print quantity does not establish acceptance of a smaller RFQ response. No parameter was selected from this result.']
 (a.out/'REPORT.md').write_text('\n'.join(lines)+'\n')
 print(json.dumps(summary,indent=2))
if __name__=='__main__':main()

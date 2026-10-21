#!/usr/bin/env python3
"""Back-check mapped settlement policies and available historical outcome audits."""
import argparse,json,collections
from pathlib import Path

def run(runtime, mlb_audit=None):
 d=json.loads(Path(runtime).read_text()); rows=d['mappings']; errors=[]; fam=collections.Counter();
 for m in rows:
  period=m.get('period','full_game'); kind=m['market_type']; fam[f'{period}:{kind}']+=1
  if m.get('player_prop') is not False: errors.append((m['market_key'],'player_prop'))
  if kind in ('spreads','totals','team_totals'):
   try: line=float(m['market_key'].split(':')[-1])
   except Exception: errors.append((m['market_key'],'line_unparseable')); continue
   if abs(line*2-round(line*2))>1e-9: errors.append((m['market_key'],'non_half_point_push_state'))
  if m.get('shadow_pricing_authorized') is not True: errors.append((m['market_key'],'not_shadow_authorized'))
 hist=None
 if mlb_audit and Path(mlb_audit).exists():
  hist=json.loads(Path(mlb_audit).read_text()).get('counts',{})
 return {'runtime':str(runtime),'mapped_markets':len(rows),'families':dict(fam),'errors':errors,'valid':not errors,'historical_mlb_outcome_audit':hist,'limitations':['This verifies deterministic mapping/policy invariants; it cannot infer unrecorded postponement or suspension states.']}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--runtime',type=Path,required=True);p.add_argument('--mlb-audit',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args();r=run(a.runtime,a.mlb_audit);a.out.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2));raise SystemExit(0 if r['valid'] else 2)

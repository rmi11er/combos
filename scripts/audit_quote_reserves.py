#!/usr/bin/env python3
"""Same-print decomposition of quoting reserves; production configuration unchanged."""
import importlib.util,json,math,sys
from pathlib import Path
from collections import defaultdict
import pandas as pd
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from combos.historical_fair import historical_observations,compare_fairs
from combos.observations import Observation
from combos.pricing import Interval,pinnacle_fair,short_yes_economics
from combos.replay import complement
from combos.joint_pricing import price_joint


def main():
 spec=importlib.util.spec_from_file_location('pilot',ROOT/'scripts/cfb_fair_pilot.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
 settings=json.load(open(ROOT/'config/cfb_fair_pilot.json'));pilot=module.Pilot(settings);tape=module.extract_tape(pilot)
 comparable=set(pd.read_csv(module.OUT/'combo_comparisons.csv').trade_id);rows=[];stages=('point','raw_book_band','fee_expanded_blend','exchange_envelope','delay_padding','correlation_bound')
 for item in tape['trades']:
  trade=item['trade']
  if trade['trade_id'] not in comparable:continue
  m=tape['markets'][trade['ticker']];at=module.timestamp(trade['created_time']);legs=m['mve_selected_legs'];leg_stages=[]
  for leg in legs:
   lm=pilot.maps[leg['market_ticker']];k=lm['kalshi'].latest(at,60);pm=lm['pm'].latest(at,60);yt,yr=lm['pin_yes'].latest(at,30);nt,nr=lm['pin_no'].latest(at,30)
   records=historical_observations(leg['market_ticker'],k,pm,(yt,yr,nt,nr),at,1000,30,lm['pm_fee']);fair,observations=compare_fairs(records)
   weights={v:row['weight'] for v,row in fair['venues'].items()}
   raw=[Interval(r['yes_bid'],(r['yes_bid']+r['yes_ask'])/2,r['yes_ask']) if r['venue']!='pinnacle' else pinnacle_fair(r['decimal_odds_yes'],r['decimal_odds_no']) for r in records]
   blend_raw=Interval(*(sum(weights[r['venue']]*getattr(iv,key) for r,iv in zip(records,raw)) for key in ('lower','point','upper')))
   fee_blend=Interval(**fair['unprotected_blend']);env=Interval(min(fee_blend.lower,observations[0].interval.lower,observations[1].interval.lower),fee_blend.point,max(fee_blend.upper,observations[0].interval.upper,observations[1].interval.upper))
   values={'point':Interval(fee_blend.point,fee_blend.point,fee_blend.point),'raw_book_band':blend_raw,'fee_expanded_blend':fee_blend,'exchange_envelope':env,'delay_padding':Interval(**fair['fair'])}
   leg_stages.append({s:complement(v,leg['side']) for s,v in values.items()})
  q=float(trade['count_fp']);p=float(trade['yes_price_dollars']);rate=.035 if m['event_ticker'].startswith('KXMVECROSSCATEGORY-SHARD1-') else 0
  fee=short_yes_economics(q,p,0,rate)['maker_fee'];probs={s:math.prod(ls[s].upper for ls in leg_stages) for s in stages[:-1]}
  probs['correlation_bound']=price_joint([ls['delay_padding'] for ls in leg_stages],settings['correlation_rho'])['stressed_upper']
  for s in stages:rows.append({'trade_id':trade['trade_id'],'legs':len(legs),'quantity':q,'price':p,'stage':s,'probability':probs[s],'net_edge':q*(p-probs[s])-fee,'clears_edge':q*(p-probs[s])-fee>=q*.003})
 frame=pd.DataFrame(rows);out=module.OUT/'reserve_audit';out.mkdir(exist_ok=True);frame.to_csv(out/'per_print.csv',index=False)
 summary=[];previous=None
 for stage in stages:
  g=frame[frame.stage==stage];total=float(g.net_edge.sum());summary.append({'stage':stage,'net_edge_dollars':total,'incremental_reserve_dollars':0 if previous is None else previous-total,'prints_clearing_edge':int(g.clears_edge.sum())});previous=total
 (out/'summary.json').write_text(json.dumps({'stages':summary,'method':'fixed final venue weights; nested quoting bounds; not an additive statistical variance decomposition'},indent=2)+'\n')
 print(json.dumps(summary,indent=2))
if __name__=='__main__':main()

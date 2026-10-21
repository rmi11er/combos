"""Fee sensitivity of matched-risk inventory pricing, no runtime mutation."""
import argparse
from decimal import Decimal
import gzip
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from combos.fees import kalshi_fill_fee
from research_inventory_relief import replay


def run(out):
    original=sorted([json.loads(l) for l in gzip.open(out/'nfl_panel.jsonl.gz','rt')],key=lambda r:(r['at'],r['evaluation_id']))
    results=[]
    for rate in ['0','.0175','.035','.07']:
        rows=[]
        for r in original:
            fee=float(kalshi_fill_fee(str(r['quantity']),1-Decimal(str(r['yes_price'])),rate)['net_fee'])
            marks={h:{**m,**({'seller_net_markout_cents':m['seller_net_markout_cents']+100*(r['maker_fee']-fee)/r['quantity']} if 'seller_net_markout_cents' in m else {})} for h,m in r['marks'].items()}
            rows.append({**r,'maker_fee':fee,'marks':marks})
        for max_age in ([None,180] if rate=='.035' else [None]):
            gated=[{**r,'quote_allowed':r['quote_allowed'] and (max_age is None or r['entry_max_age_seconds']<=max_age)} for r in rows]
            for period,subset in [('full',gated),('later',[r for r in gated if r['at']>=1768197600])]:
                for arm,trigger in [('net',.9),('relief',.8),('relief',.9)]:
                    s,fills=replay(subset,arm,trigger,.001,1000,250,True)
                    s.update(maker_rate=rate,period=period,entry_max_age=max_age,pnl_without_largest_winning_fill=s['pnl']-max([0]+[f['pnl'] for f in fills if f['pnl'] is not None]))
                    results.append(s);print(rate,max_age,period,arm,trigger,s['fills'],round(s['pnl'],2),flush=True)
    (out/'inventory_fee_followup.json').write_text(json.dumps({'results':results,'limitations':[
        'Explicit unverified January maker fee scenarios; not a historical effective-date certification.',
        'Net-risk book, outcome revelation at recorded settlement, instrument1000/combo250/fixture250 limits.',
        'Full original print size and price retained, not a quote repricing or acceptance experiment.',
        'Largest-fill omission is descriptive; book is not reallocated after removing that fill.']},indent=2)+'\n')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);run(p.parse_args().out)

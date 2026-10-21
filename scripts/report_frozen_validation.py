"""Plot completed, independently audited frozen validation; never fit policies."""
import argparse
import csv
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

from replay_artifact_io import text_reader
from mlb_streaming_longitudinal import Compact


def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()


def verified_summary(study):
    summary=study/'summary.json'; audit=json.loads((study/'independent_verification.json').read_text())
    complete=json.loads((study/'complete.json').read_text())
    actual=digest(summary)
    if audit.get('passed') is not True or audit.get('summary_sha256')!=actual or complete.get('summary_sha256')!=actual:
        raise ValueError('completed independently audited summary required')
    data=json.loads(summary.read_text())
    expected={(r['variant'],r['regime']) for r in data['records']}
    audited={(r['policy'],r['regime']) for r in audit['portfolios']}
    if len(data['records'])!=28 or len(expected)!=28 or expected!=audited:
        raise ValueError('exact 28-portfolio audit census required')
    for portfolio in audit['portfolios']:
        for name,expected_hash in portfolio['artifact_hashes'].items():
            if digest(Path(name))!=expected_hash:raise ValueError('audited artifact changed')
    return data,actual


def curve(study,record):
    p=study/(record['variant']+'__'+record['regime']+'.curves.jsonl.zst')
    before=digest(p)
    with text_reader(p) as f:count=sum(1 for _ in f)
    compact=Compact(count);last=None
    with text_reader(p) as f:
        for i,line in enumerate(f):
            row=json.loads(line)
            if last and row['at']<last['at']:raise ValueError('curve chronology regressed')
            compact.add(i,row);last=row
    if last is None or digest(p)!=before:raise ValueError('empty or changed curve')
    for key,expected in (('trade_attributed_pnl',record['portfolio']['trade_attributed_pnl']),
                         ('committed_cash',record['portfolio']['ending_committed_cash']),
                         ('filled_yes_premium',record['selected']['yes_premium']),
                         ('filled_payout_notional',record['selected']['payout_notional'])):
        if abs(last[key]-expected)>.01:raise ValueError('curve endpoint mismatch: '+key)
    return compact.output,{'path':str(p),'sha256':before,'rows':count}


def run(study,out):
    data,summary_hash=verified_summary(study)
    out.mkdir(parents=True,exist_ok=False)
    fields=['policy','role','regime','fills','net_pnl','modeled_net_edge','yes_premium',
            'payout_notional','peak_cash','max_trade_pnl_drawdown','observed_date_pnl_variance_dollars2']
    with (out/'portfolios.csv').open('w') as f:
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader()
        for r in data['records']:
            writer.writerow(dict(zip(fields,[r['variant'],r['frozen_role'],r['regime'],r['portfolio']['fills'],
                r['portfolio']['trade_attributed_pnl'],r['selected']['net_point_edge'],r['selected']['yes_premium'],
                r['selected']['payout_notional'],r['portfolio']['peak_committed_cash'],
                r['portfolio']['max_trade_attributed_drawdown_dollars'],
                r['sampled_statistics']['observed_date_pnl_variance_dollars2']])))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    plt.style.use('dark_background');plt.rcParams['text.parse_math']=False
    chosen={'equal_point_primary':'Equal primary','pm75_point_challenger':'PM75 challenger',
            'pm_quarter_challenger':'PM quarter reserve','sell_all_control':'Sell every priced print'}
    receipts=[]
    for regime in ('funded','unlimited'):
        fig,axes=plt.subplots(5,1,figsize=(14,15),sharex=True)
        for r in data['records']:
            if r['regime']!=regime or r['variant'] not in chosen:continue
            rows,receipt=curve(study,r);receipts.append(receipt)
            times=[datetime.fromtimestamp(v['at'],timezone.utc) for v in rows]
            variance=r['sampled_statistics']['observed_date_pnl_variance_dollars2']
            label=chosen[r['variant']];var='N/A' if variance is None else f'{variance:,.0f}'
            line,=axes[0].step(times,[v['trade_attributed_pnl'] for v in rows],where='post',label=f'{label} | Sharpe N/A | Var {var} dollars²')
            color=line.get_color()
            for ax,key in zip(axes[1:],('accepted_point_edge','filled_yes_premium','filled_payout_notional','committed_cash')):
                ax.step(times,[v[key] for v in rows],where='post',color=color,label=label)
        for ax,label in zip(axes,('Cumulative eventual P&L ($)','Cumulative model net edge ($)','Cumulative YES premium ($)','Cumulative payout notional ($)','Committed cash ($)')):
            ax.set_ylabel(label);ax.grid(alpha=.2);ax.legend(fontsize=8)
        day_span=(axes[-1].get_xlim()[1]-axes[-1].get_xlim()[0])
        axes[-1].xaxis.set_major_locator(mdates.DayLocator(interval=max(1,math.ceil(day_span/9))))
        axes[-1].xaxis.set_major_formatter(mdates.DateFormatter('%b %d'))
        title='SYNTHETIC DATA — rendering test only' if data.get('synthetic_data') else 'Frozen August validation'
        fig.suptitle(title+' — '+regime+'\nTrade-time P&L attribution; cash released at actual settlement')
        fig.text(.08,.015,'Counterfactual fills at observed prints; dated fee assumptions. Variance across observed dates; no annualized IID Sharpe claim.\nPayout notional counts $1 face value per contract, not customer winnings. Unlimited results require additional funding. All 28 policies: portfolios.csv.',fontsize=9)
        fig.tight_layout(rect=(0,.05,1,.95))
        for ext in ('png','svg'):fig.savefig(out/(regime+'.'+ext),dpi=140)
        plt.close(fig)
    if digest(study/'summary.json')!=summary_hash:raise ValueError('summary changed during plotting')
    (out/'manifest.json').write_text(json.dumps({'summary_sha256':summary_hash,'curves':receipts,
        'script_sha256':digest(Path(__file__)),'limitations':['Curve endpoints and chronology checked; intermediate curve arithmetic is not independently reconstructed here.','No policy fitting or promotion.']},indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--study',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();run(a.study,a.out)

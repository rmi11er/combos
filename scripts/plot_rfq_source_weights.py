"""Plot matched RFQ quote differences and hypothetical capacity, not returns."""
import argparse
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams['text.parse_math'] = False


def run(folder):
    summary=json.loads((folder/'summary.json').read_text())
    rows={name:{} for name in summary['models']}
    for line in (folder/'priced_decisions.jsonl').open():
        r=json.loads(line);rows[r['model']][r['source_seq']]=r
    base=rows[summary['baseline']]
    common=set.intersection(*(set(r) for r in rows.values()))
    fig,axes=plt.subplots(1,2,figsize=(12,4.5),layout='constrained')
    names=[];counts=[];cash=[]
    for name,records in rows.items():
        label=name.replace('_',' ')
        names.append(label)
        counts.append(summary['models'][name]['counts'].get('policy:reserved_scenario',0))
        cash.append(summary['models'][name]['peak_reserved_dollars'])
        if name==summary['baseline']:continue
        values=sorted(100*(float(records[s]['research_policy']['quote']['yes_ask'])-
            float(base[s]['research_policy']['quote']['yes_ask'])) for s in common)
        axes[0].step(values,[(i+1)/len(values) for i in range(len(values))],where='post',label=label)
    axes[0].axvline(0,color='gray',lw=.8)
    axes[0].set(xlabel='YES ask difference from captured policy (cents/contract)',
        ylabel='Fraction of matched RFQs',title=f'Quote sensitivity: {len(common):,} matched RFQs')
    axes[0].legend(fontsize=8,loc='lower right');axes[0].grid(alpha=.2)
    bars=axes[1].bar(range(len(names)),counts,color='#387ca3')
    axes[1].set(xticks=range(len(names)),xticklabels=[n.replace(' ','\n') for n in names],
        ylabel='Research reservations',title='Assume all admitted quotes fill; no cash release')
    axes[1].set_ylim(0,max(counts)*1.3)
    for b,n,c in zip(bars,counts,cash):
        axes[1].text(b.get_x()+b.get_width()/2,n+2,f'{n}\n${c:,.0f} peak',ha='center',fontsize=9)
    fig.suptitle('NFL captured pregame RFQs — source-weight sensitivity, not performance\n'
        '$10k research capital · $1k underlying/combo/event caps · 0.3¢/combo · point fair')
    fig.savefig(folder/'source_weight_sensitivity.png',dpi=160)
    plt.close(fig)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('folder',type=Path)
    run(p.parse_args().folder)

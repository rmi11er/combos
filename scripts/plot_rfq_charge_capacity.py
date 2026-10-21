"""Plot charge/capacity scenarios without implying executions or profitability."""
import argparse,json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams['text.parse_math']=False


def run(folder):
    data=json.loads((folder/'summary.json').read_text())['scenarios']
    names=['zero','0.1c_combo','0.3c_combo','0.6c_combo','0.3c_leg','quarter_interval_plus_0.3c']
    labels=['Zero','0.1¢/combo','0.3¢/combo','0.6¢/combo','0.3¢/leg','¼ interval\n+0.3¢/combo']
    fig,axes=plt.subplots(2,2,figsize=(12,7),layout='constrained')
    for col,mode in enumerate(['unfilled_expiry_3s','all_admitted_fill_no_release']):
        for cap in (500,1000,2000):
            rows={r['charge']:r for r in data if r['model']=='captured_sharp_peer' and r['cap']==cap and r['mode']==mode}
            for ax,values in [(axes[0,col],[rows[n]['counts']['admitted'] for n in names]),
                              (axes[1,col],[rows[n]['peak_committed_dollars'] for n in names])]:
                ax.plot(range(len(names)),values,marker='o',label=f'${cap:,} caps')
                ax.set_xticks(range(len(names)),labels,fontsize=8);ax.grid(alpha=.2)
        axes[0,col].set_title('No fills; reservations expire after 3s' if col==0 else 'All admitted fill; no release')
        axes[0,col].legend(fontsize=8)
        axes[1,col].axhline(10000,color='gray',ls='--',lw=1)
        axes[1,col].set_ylim(0,10500)
    axes[0,0].set_ylabel('Research admissions')
    axes[1,0].set_ylabel('Peak held cash ($)')
    fig.suptitle('NFL: 694 matched RFQs, September 9, 03:17–03:19 CDT\n'
        'Captured three-source blend · $10k capital · full RFQ size · no acceptance or P&L inference')
    fig.savefig(folder/'charge_capacity.png',dpi=160);plt.close(fig)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('folder',type=Path)
    run(p.parse_args().folder)

import json,os
from pathlib import Path
os.environ.setdefault('MPLCONFIGDIR','/private/tmp/combos-matplotlib')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
import pandas as pd
import numpy as np
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'output';START=1788584400

def money(x,pos=None):
    if abs(x)>=1e6:return f'${x/1e6:.1f}m'
    if abs(x)>=1000:return '$'+f'{x/1e3:.1f}'.rstrip('0').rstrip('.')+'k'
    return f'${x:.0f}'

def main():
    s=json.loads((OUT/'summary.json').read_text());h=pd.read_csv(OUT/'hourly_volume.csv').set_index('hour').reindex(range(24)).fillna(0)
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False,'axes.titleweight':'medium','axes.labelcolor':'#27354a','text.color':'#27354a','xtick.color':'#56647a','ytick.color':'#56647a','axes.edgecolor':'#bbc4d0','figure.facecolor':'white','axes.facecolor':'white','savefig.facecolor':'white'})
    colors={'all':'#9baabd','cross':'#176b87','same':'#d8a14b','mid':'#8795a8','upper':'#176b87','rho002':'#a16b9f','rho005':'#bb6749','upper_small_prints':'#317759'}
    fig,axes=plt.subplots(4,1,figsize=(13,13),sharex=True,gridspec_kw={'height_ratios':[1,1,1.3,1]})
    fig.subplots_adjust(top=.875,bottom=.08,left=.1,right=.97,hspace=.47)
    fig.suptitle('September 5, 2026 college-football combos: flow and opportunity bounds',x=.1,y=.975,ha='left',fontsize=17,weight='medium')
    fig.text(.1,.943,'Two legs · all fair probabilities · pregame and in-play · $10,000 initial capital · America/Chicago',fontsize=11)
    fig.text(.1,.917,'Three-venue liquidity-weighted edge is unavailable. Pricing below is a Kalshi-only historical proxy.',fontsize=11,color='#964b35')
    x=np.arange(24)+.5
    axes[0].bar(x,h['all_combo_premium'],width=.82,color=colors['all'])
    axes[0].set_title('Entire RFQ-combo universe (KXMVE) — observed taker-side premium',loc='left',pad=12)
    axes[0].text(.99,.87,f"{s['totals']['all_combo_trades']:,} prints · {money(s['totals']['all_combo_taker_premium'])}",transform=axes[0].transAxes,ha='right')
    axes[0].text(.99,.69,'Competing quoted volume: not public',transform=axes[0].transAxes,ha='right',color='#56647a',fontsize=9)
    axes[1].bar(x,h['cross_game_premium'],width=.82,color=colors['cross'],label='Different games')
    axes[1].bar(x,h['same_game_premium'],bottom=h['cross_game_premium'],width=.82,color=colors['same'],label='Same game — separate joint model needed')
    axes[1].set_title('Two-leg college-football subset — observed traded premium',loc='left',pad=12)
    axes[1].legend(frameon=False,loc='upper left',fontsize=9)
    axes[1].text(.99,.9,f"{s['totals']['cfb_two_leg_trades']:,} prints · {money(s['totals']['cfb_two_leg_premium'])}",transform=axes[1].transAxes,ha='right')
    f=pd.read_csv(OUT/'cfb_trade_opportunities.csv')
    largest_share=f.groupby('ticker').premium.sum().max()/f.premium.sum()
    axes[1].text(.01,.63,f'Largest single market: {largest_share:.0%} of CFB traded premium',transform=axes[1].transAxes,fontsize=9,color='#56647a')
    for variant,label,style in [('mid','Midpoint fair','--'),('upper','Fee-expanded upper fair','-'),('rho002','Upper fair + 0.02 correlation stress',':'),('rho005','Upper fair + 0.05 correlation stress','-.'),('upper_small_prints','Fee upper; observed $5–$20 prints only','-')]:
        p=pd.read_csv(OUT/f'capital_path_{variant}.csv')
        if p.empty:continue
        tx=[0]+(p['at']-START).div(3600).tolist()+[24]
        ys=[0]+p.cumulative_edge.tolist()+[p.cumulative_edge.iloc[-1]]
        axes[2].step(tx,ys,where='post',label=f"{label}: ${ys[-1]:,.0f}",color=colors[variant],linestyle=style,lw=2)
    axes[2].set_title('Cumulative modeled edge — no ticket cap; observed size limited by available capital',loc='left',pad=12)
    axes[2].legend(frameon=False,loc='upper left',fontsize=9,ncol=2)
    axes[2].text(.99,.03,'All scenarios: ≥0.3¢ net edge/share. No actual acceptance model.',transform=axes[2].transAxes,ha='right',fontsize=9,color='#56647a')
    axes[3].bar(x,h.get('cfb_observed_target_cost',pd.Series(0,index=h.index)),width=.82,color='#cad2dd',label='Observed RFQ target budgets')
    axes[3].bar(x,h.get('cfb_model_quotable_target_cost',pd.Series(0,index=h.index)),width=.50,color=colors['cross'],label='Individually quotable under proxy')
    axes[3].set_title('Retained RFQs in sampled traded CFB markets — requested budgets, not quote or fill volume',loc='left',pad=12)
    axes[3].legend(frameon=False,loc='upper left',fontsize=9)
    for ax in axes:
        ax.set_axisbelow(True);ax.grid(axis='y',color='#e5e9ef',linewidth=.7);ax.yaxis.set_major_formatter(FuncFormatter(money));ax.set_xlim(0,24);ax.set_ylim(bottom=0)
    for ax in [axes[0],axes[1],axes[3]]:ax.set_ylim(0,ax.get_ylim()[1]*1.2)
    axes[2].set_ylim(0,axes[2].get_ylim()[1]*1.35)
    axes[-1].set_xticks(range(0,25,3));axes[-1].set_xticklabels([f'{t:02d}:00' for t in range(0,25,3)]);axes[-1].set_xlabel('Time of day, Central Daylight Time')
    fig.text(.1,.025,'Source: Kalshi public trades, market metadata, minute candles and retained RFQs. Historical price availability is assumed; same-game edge is excluded.\nObserved prices are an ex-post competitiveness ceiling. Summed modeled edge is not expected live P&L.',fontsize=9,color='#56647a')
    fig.savefig(OUT/'opportunity_by_time.png',dpi=190);fig.savefig(OUT/'opportunity_by_time.svg');plt.close(fig)

    f=pd.read_csv(OUT/'cfb_trade_opportunities.csv');good=f[f.exclusion.isna()].copy()
    fig,axes=plt.subplots(1,3,figsize=(15,4.6));fig.subplots_adjust(left=.07,right=.98,bottom=.23,top=.8,wspace=.4)
    fig.suptitle('What survives the pricing assumptions?',x=.07,ha='left',fontsize=17,weight='medium')
    positive=[s[f'observed_size_{v}']['positive_edge_dollars'] for v in ['mid','upper','rho002','rho005']]
    axes[0].bar(range(4),positive,color=[colors[v] for v in ['mid','upper','rho002','rho005']]);axes[0].set_xticks(range(4),['Midpoint','Fee upper','+ρ 0.02','+ρ 0.05']);axes[0].set_title('Positive edge at observed trade size',loc='left',fontsize=11);axes[0].yaxis.set_major_formatter(FuncFormatter(money))
    vals=[s['latency_sensitivity']['0']['positive_edge'],s['latency_sensitivity']['30']['positive_edge'],s['observed_size_upper']['positive_edge_dollars'],s['latency_sensitivity']['120']['positive_edge']]
    axes[1].bar(range(4),vals,color=colors['cross']);axes[1].set_xticks(range(4),['0s','30s','60s','120s']);axes[1].set_title('Assumed candle publication lag',loc='left',fontsize=11);axes[1].yaxis.set_major_formatter(FuncFormatter(money))
    models=['mid','upper','rho002','rho005'];pnl=[s['capital_upper_bound_scenarios'][v]['terminal_net_pnl'] for v in models]
    axes[2].bar(range(4),pnl,color=[colors[v] for v in models]);axes[2].axhline(0,color='#56647a',lw=.7);axes[2].set_xticks(range(4),['Midpoint','Fee upper','+ρ 0.02','+ρ 0.05']);axes[2].set_title('Terminal P&L on the allocated scenario',loc='left',fontsize=11);axes[2].yaxis.set_major_formatter(FuncFormatter(money))
    for ax in axes:ax.set_axisbelow(True);ax.grid(axis='y',color='#e5e9ef',lw=.7)
    fig.text(.07,.08,'Cross-game independence is an assumption. Correlation stresses are sensitivities. Lag comparisons use the primary priced cohort.\nTerminal P&L uses actual outcomes on hypothetical allocations; these are not live fills or return forecasts.',fontsize=9,color='#56647a')
    fig.savefig(OUT/'pricing_sensitivity.png',dpi=190);fig.savefig(OUT/'pricing_sensitivity.svg');plt.close(fig)

if __name__=='__main__':main()

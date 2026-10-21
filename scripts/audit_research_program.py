"""Independently reconcile retained study artifacts and record provenance."""
from collections import defaultdict
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from nfl_moneyline_replay import certified_days


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def risk_check(rows,fills,conditioned,trigger=.9,contract_cap=100.,combo_cap=100.):
    index={r['evaluation_id']:r for r in rows}
    fixtures=sorted({f for r in rows for f,_ in r['selected_fixture_bits']})
    indices={f:j for j,f in enumerate(fixtures)};states=np.arange(2**len(fixtures))
    reveal={}
    if conditioned:
        for r in rows:
            if r['yes_settlement']!=1 or r['settled_at'] is None:continue
            for f,b in r['selected_fixture_bits']:
                if f not in reveal or r['settled_at']<reveal[f][0]:reveal[f]=(r['settled_at'],b)
    active=[];accepted=[];checked=0
    def loss(r):
        wins=np.ones(len(states),dtype=bool)
        for f,b in r['selected_fixture_bits']:wins &= ((states>>indices[f])&1)==b
        return r['quantity']*(wins-r['yes_price'])+r['maker_fee']
    def sens(values,feasible):
        result=[]
        for j in range(len(fixtures)):
            partner=states^(1<<j);valid=feasible&feasible[partner]
            result.append(float(np.max(abs(values[valid]-values[partner[valid]]))) if valid.any() else 0.)
        return np.array(result)
    for fill in fills:
        r=index[fill['id']];at=r['at'];active=[a for a in active if a['settled_at'] is None or a['settled_at']>at]
        feasible=np.ones(len(states),dtype=bool)
        for f,(known,b) in reveal.items():
            if known<=at:feasible &= ((states>>indices[f])&1)==b
        before=sum((loss(a) for a in active),np.zeros(len(states)));after=before+loss(r)
        a=sens(before,feasible);b=sens(after,feasible)
        assert abs(max(0,float(before[feasible].max()))-fill['worst_loss_before'])<1e-6
        assert abs(max(0,float(after[feasible].max()))-fill['worst_loss_after'])<1e-6
        assert abs(float(b.max())-fill['after_max_sensitivity'])<1e-6
        if fill['discount_admitted']:
            assert np.any((a>=250*trigger-1e-8)&(b<a-1e-8))
            assert max(0,float(after[feasible].max()))<=max(0,float(before[feasible].max()))+1e-8
        liability=lambda p:p['quantity']*(1-p['yes_price'])+p['maker_fee']
        contracts=defaultdict(float);combos=defaultdict(float)
        for p in active+[r]:
            for key in p['buckets']['contract']:contracts[key]+=liability(p)
            combos[p['buckets']['combo'][0]]+=liability(p)
        assert max(contracts.values())<=contract_cap+1e-7 and max(combos.values())<=combo_cap+1e-7
        realized=sum(p['quantity']*(p['yes_price']-p['yes_settlement'])-p['maker_fee'] for p in accepted if p['settled_at'] is not None and p['settled_at']<=at)
        assert sum(liability(p) for p in active+[r])<=10000+realized+1e-7
        active.append(r);accepted.append(r);checked+=1
    return checked


def run(out):
    load=lambda name:json.loads((out/name).read_text())
    rows=[json.loads(l) for l in gzip.open(out/'nfl_panel.jsonl.gz','rt')]
    index={r['evaluation_id']:r for r in rows};assert len(index)==len(rows)==23809
    checked_marks=0
    for r in rows:
        assert abs(float(np.prod(r['leg_mids']))-r['fair_point'])<1e-12
        for m in r['marks'].values():
            if m['status']!='observed':continue
            assert m['at']<r['source']['start_at'] and m['at']>r['at']
            assert all(t+60<=m['at'] for t in m['source_at'])
            assert abs(np.prod(m['selected_mids'])-m['fair'])<1e-12
            assert abs(100*(r['yes_price']-m['fair']-r['maker_fee']/r['quantity'])-m['seller_net_markout_cents'])<1e-9
            checked_marks+=1
    books=0;checked_fills=0
    for suffix in ['','_fixture_constrained','_conditioned']:
        result=load('inventory_relief'+suffix+'.json')
        for s in result['results']:
            name=f"inventory{suffix}_{s['period']}_{s['arm']}_{s['trigger']}_{s['relief_edge_cents']/100}.json.gz"
            with gzip.open(out/name,'rt') as f:fills=json.load(f)
            assert len({f['id'] for f in fills})==len(fills)==s['fills']
            assert abs(sum(f['pnl'] for f in fills)-s['pnl'])<1e-6
            assert abs(s['ending_cash']-10000-s['pnl'])<1e-6
            assert sum(f['discount_admitted'] for f in fills)==s['discount_fills']
            for f in fills:
                r=index[f['id']];edge=100*(r['yes_price']-r['fair_point']-r['maker_fee']/r['quantity'])
                floor=s['relief_edge_cents'] if f['discount_admitted'] else .1 if s['arm']=='flat01' else .3
                assert edge>=floor-1e-8
                if s['arm']!='gross':assert f['after_max_sensitivity']<=250+1e-7
            subset=rows if s['period']=='full' else [r for r in rows if r['at']>=1768197600]
            checked_fills+=risk_check(subset,fills,s.get('condition_settled',False),s['trigger'],s['contract_cap'],s['combo_cap']);books+=1
    default=load('inventory_relief.json')['results']
    baseline=next(s for s in default if s['period']=='full' and s['arm']=='gross')
    assert baseline['fills']==21 and abs(baseline['pnl']+29.4028)<1e-8
    for s in load('inventory_repricing.json')['results']:
        with gzip.open(out/f"repriced_{s['period']}_{s['arm']}_{s['trigger']}.json.gz",'rt') as f:fills=json.load(f)
        assert len(fills)==s['fills'] and abs(sum(f['pnl'] for f in fills)-s['pnl'])<1e-6
        assert abs(s['ending_cash']-10000-s['pnl'])<1e-6
        replacement={f['id']:f for f in fills}
        adjusted=[]
        for r in rows:
            f=replacement.get(r['evaluation_id'])
            if f is None:adjusted.append(r);continue
            assert f['charged_price']<=r['yes_price']+1e-12
            expected_pnl=r['quantity']*(f['charged_price']-r['yes_settlement'])-f['charged_fee']
            assert abs(expected_pnl-f['pnl'])<1e-8
            edge=100*(f['charged_price']-r['fair_point']-f['charged_fee']/r['quantity'])
            assert abs(edge-f['edge_cents'])<1e-8
            assert edge>=(.1 if f['discount_admitted'] or s['arm']=='flat01' else .3)-1e-8
            for h,value in f['markouts'].items():
                if value is not None:assert abs(value-100*(f['charged_price']-r['marks'][h]['fair']-f['charged_fee']/r['quantity']))<1e-8
            adjusted.append({**r,'yes_price':f['charged_price'],'maker_fee':f['charged_fee']})
        subset=adjusted if s['period']=='full' else [r for r in adjusted if r['at']>=1768197600]
        checked_fills+=risk_check(subset,fills,True,s['trigger'],s['contract_cap'],s['combo_cap']);books+=1
    final=load('final_analysis.json');same=load('samegame_history.json');mlb=load('mlb_volume_clock.json')
    assert len(mlb['dates'])==31 and len(mlb['clocks'])==290
    assert sum(r['clock_prints'] for r in mlb['dates'])==585691
    for c in mlb['clocks']:
        assert abs(sum(b['contracts'] for b in c['bins'])-c['contracts'])<1e-5
        assert abs(sum(b['contracts_share'] for b in c['bins'])-1)<1e-10
    for r in same['portfolio_bounds']:
        assert 0<=r['guaranteed_reduction_units']<=r['gross_payout_units']
        if r['scenario']=='all_legs_yes_selection':assert r['guaranteed_reduction_units']==0
    days=certified_days(ROOT/'runs/nfl_playoffs_history_20260907');assert len(days)==14
    source_hashes={}
    for _,cohort,_,hashes in days:
        for path,h in hashes.items():source_hashes[str(Path(path).resolve())]=h
        for filename in ['summary.json','candidate_trades.jsonl.gz','universe_trades.jsonl.gz','combo_markets.json.gz']:
            path=cohort/filename;source_hashes[str(path.resolve())]=digest(path)
    for filename in ['extraction.json','mlb_volume_clock.json']:
        for name,h in load(filename)['hashes'].items():
            path=Path(name);path=path if path.is_absolute() else ROOT/path
            assert digest(path)==h,(str(path),'source changed')
            source_hashes[str(path.resolve())]=h
    pipeline=load('pipeline_run.json')
    assert len(pipeline['steps'])==12 and all(s['exit_code']==0 for s in pipeline['steps'])
    assert all(digest(Path(s['command'][1]))==s['script_sha256'] for s in pipeline['steps'])
    assert pipeline['tests']['exit_code']==0
    qa=load('visual_qa.json')
    assert qa['runtime_exceptions']==0 and qa['standalone_iframe_present']
    assert qa['fragment_sha256']==digest(out/'research-atlas.html')
    assert qa['standalone_sha256']==digest(ROOT/'visualizations/07-research-program/index.html')
    assert {r['width'] for r in qa['viewports']}=={320,736}
    assert all(r['charts']==20 and not r['overflow'] and r['details_interaction'] for r in qa['viewports'])
    result={'status':'passed','panel_prints':len(rows),'reconciled_future_marks':checked_marks,'reconciled_books':books,
        'independently_recomputed_fill_risks':checked_fills,'nfl_certified_days':len(days),'mlb_clock_prints':585691,
        'visual_charts':20,'tests':pipeline['tests']['stdout'],'limitations':['Audit proves stated artifact/accounting invariants, not acceptance, historical depth, fee applicability, or production safety.']}
    (out/'audit.json').write_text(json.dumps(result,indent=2)+'\n')
    script_names=['research_program_extract','research_volume_markouts','research_inventory_relief','research_inventory_fee_followup','research_inventory_repricing',
        'research_hedge_followup','research_samegame_history','research_mlb_volume_clock','research_final_analysis',
        'build_research_atlas','verify_research_atlas','run_research_program','audit_research_program']
    sources=[ROOT/'scripts'/f'{n}.py' for n in script_names]
    sources += [ROOT/'src/combos'/n for n in ['kalshi_history.py','fees.py','research_spend_risk.py']]
    sources += list((ROOT/'tests').glob('test_research_*.py'))
    sources += [ROOT/'visualizations/07-research-program/research-atlas.template.html',ROOT/'visualizations/07-research-program/README.md',
        ROOT/'research/RESEARCH_FINDINGS_20260910.md',ROOT/'research/RESEARCH_PROGRAM_20260910.md',ROOT/'research/RESEARCH_PROGRAM_PROGRESS_20260910.md']
    artifacts=[p for p in out.iterdir() if p.is_file() and p.name!='reproducibility_manifest.json']+[ROOT/'visualizations/07-research-program/index.html']
    manifest={'raw_inputs':source_hashes,'code_and_report':{str(p.relative_to(ROOT)):digest(p) for p in sources},
        'artifacts':{str(p.relative_to(ROOT)):digest(p) for p in artifacts},'pipeline_commands':[s['command'] for s in pipeline['steps']]}
    (out/'reproducibility_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);run(p.parse_args().out.resolve())

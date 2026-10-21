"""Independent economic/cohort checks for the weekly research report."""
import gzip
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from combos.pricing import short_yes_economics
OUT=ROOT/'runs/football_week_review_20260914'

def read(name):
    with gzip.open(OUT/name,'rt') as f:return json.load(f)

def main():
    checks={};rows=read('observed_football_trades.json.gz');priced=read('priced_trades.json.gz')
    assert len({r['id'] for r in rows})==len(rows)
    assert all(not any(t.startswith('KXNFL') and '-26SEP14' in t for t,side,*_ in r['legs']) for r in rows)
    assert all(r['settlement'] is not None for r in rows)
    for r in rows:
        e=short_yes_economics(r['q'],r['price'],0,r['rate'])
        assert abs(e['maximum_loss']-r['cost'])<1e-8
        assert abs(r['q']*(1-r['settlement'])-r['cost']-r['pnl'])<1e-7
    checks['unique_settled_observed_prints_excluding_monday']=len(rows)
    for r in priced:
        assert all(t+60<=r['quote_forecast_at'] for t in r['candle_ends'])
        assert max(r['quote_forecast_at']-t for t in r['candle_ends'])<=180
        assert r['leg_count'] in (2,3,4) and r['distinct_fixtures']
    checks['causal_candle_forecasts']=len(priced)
    summary=json.loads((OUT/'performance_summary.json').read_text())
    for key,result in summary.items():
        fills=read(key+'_fills.json.gz')
        assert len({r['id'] for r in fills})==len(fills)==result['prints']
        assert abs(sum(r['pnl'] for r in fills)-result['settled_seller_pnl_dollars'])<1e-7
        assert result['peak_committed_dollars']<=10000+1e-7
        assert result['peak_fixture_conditional_risk_dollars']<=1000+1e-7
        for r in fills:
            assert .25<=r['request_lag']<=3
            assert r['price']<=r['public_price']+1e-12
            e=short_yes_economics(r['q'],r['price'],r['fair'],r['rate'])
            assert e['maximum_loss']<=250+1e-9
            assert e['expected_edge']/r['q']+1e-12>=r['required_edge_cents']/100
            assert abs(e['expected_edge']-r['model_ev'])<1e-8
        checks[key]=len(fills)
    sources=[ROOT/'scripts'/f for f in ('review_football_week_20260914.py','analyze_football_week_20260914.py','verify_football_week_20260914.py')]
    sources += [ROOT/'src/combos'/f for f in ('risk.py','deployment_risk.py','inventory_fitting.py','pricing.py','joint_pricing.py','shadow_engine.py','creator_service.py')]
    result={'passed':True,'checks':checks,'source_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
        'limitations':'Economic identities, chronology and limits verified; actual fills, historical depth, three-source fair and full-slate coverage are NOT established.'}
    (OUT/'verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result['checks'],indent=2))

if __name__=='__main__':main()

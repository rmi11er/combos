from copy import deepcopy
import pytest
from test_runtime import config,observation,rfq
from combos.pricing_service import PricingService
from combos.weighted_fair import WeightPolicy

class State:
    def __init__(self,venues):
        self.rows={('observations',k+':A-B:moneyline:A:'+v):observation(k,v) for k in ('a','b') for v in venues}
    def get(self,owner,key,default=None):return self.rows.get((owner,key),default)

def setup(venues,mode='shadow'):
    c=config();c['mode']=mode
    c['source_fallback']={'enabled':True,'minimum_two_sided_depth_dollars':100,'maximum_raw_spread_cents':5}
    return c,State(venues)

@pytest.mark.parametrize('mode',['shadow','live'])
@pytest.mark.parametrize('venues',[['kalshi'],['polymarket'],['kalshi','polymarket'],['kalshi','pinnacle'],['kalshi','polymarket','pinnacle']])
def test_fallback_prices_fresh_available_sources(mode,venues):
    c,s=setup(venues,mode)
    r=PricingService(s,c,WeightPolicy(delayed_pinnacle=True)).price(rfq()['mve_selected_legs'],100)
    assert r['quote_allowed']
    for leg in r['legs']:
        assert set(leg['venues'])==set(venues)
        assert sum(v['weight'] for v in leg['venues'].values())==pytest.approx(1)
        if 'pinnacle' in venues:assert leg['venues']['pinnacle']['weight']<=.2+1e-10

def test_opt_in_pair_weights_respond_to_liquidity_and_age():
    c,s=setup(['kalshi','pinnacle'])
    c['source_fallback']['liquidity_weighted_pair_fallback']=True
    pricer=PricingService(s,c,WeightPolicy(delayed_pinnacle=True))
    before=pricer.price(rfq()['mve_selected_legs'],100)['legs'][0]['venues']
    for row in s.rows.values():
        if row['venue']=='kalshi':
            row['yes_bid_size']*=1000;row['yes_ask_size']*=1000
    after=pricer.price(rfq()['mve_selected_legs'],100)['legs'][0]['venues']
    assert after['kalshi']['weight']>before['kalshi']['weight']
    assert 0<after['pinnacle']['weight']<.2
    for row in s.rows.values():
        if row['venue']=='pinnacle':row['observed_at']=40
    aged=pricer.price(rfq()['mve_selected_legs'],100)['legs'][0]['venues']
    assert aged['pinnacle']['weight']<after['pinnacle']['weight']


def test_pinnacle_alone_cannot_authorize_quote():
    c,s=setup(['pinnacle'])
    with pytest.raises(ValueError,match='no_liquid_fresh_exchange'):
        PricingService(s,c,WeightPolicy()).price(rfq()['mve_selected_legs'],100)

def test_stale_external_excluded_without_blocking_fresh_kalshi():
    c,s=setup(['kalshi','polymarket'])
    for (owner,key),r in s.rows.items():
        if r['venue']=='polymarket':r['observed_at']=50
    r=PricingService(s,c,WeightPolicy(delayed_pinnacle=True)).price(rfq()['mve_selected_legs'],100)
    assert all(l['source_fallback']['used']==['kalshi'] for l in r['legs'])

@pytest.mark.parametrize('change',[{'yes_bid_size':99},{'yes_ask':.6},{'active':False}])
def test_no_liquid_exchange_blocks(change):
    c,s=setup(['kalshi'])
    next(iter(s.rows.values())).update(change)
    with pytest.raises(ValueError,match='no_liquid_fresh_exchange'):
        PricingService(s,c,WeightPolicy()).price(rfq()['mve_selected_legs'],100)

def test_missing_pinnacle_review_blocks_only_that_source():
    c,s=setup(['kalshi','pinnacle'])
    for m in c['mappings']:m['pricing_block_reason']='pinnacle_payoff_mapping_unreviewed'
    r=PricingService(s,c,WeightPolicy()).price(rfq()['mve_selected_legs'],100)
    assert all(set(l['venues'])=={'kalshi'} for l in r['legs'])
    c['mappings'][0]['pricing_block_reason']='wrong_payoff'
    with pytest.raises(ValueError,match='wrong_payoff'):
        PricingService(s,c,WeightPolicy()).price(rfq()['mve_selected_legs'],100)

def test_mapping_version_mismatch_not_silently_dropped():
    c,s=setup(['kalshi','polymarket'])
    next(iter(s.rows.values()))['mapping_reference']='wrong'
    with pytest.raises(ValueError,match='mapping_version_mismatch'):
        PricingService(s,c,WeightPolicy()).price(rfq()['mve_selected_legs'],100)


def test_expanded_runtime_prices_exact_alternate_strikes_and_period_tie():
    import json
    from pathlib import Path
    c=json.loads((Path(__file__).resolve().parents[1]/'config/runtime_nfl_authorized_shadow_20260910.json').read_text())
    c=deepcopy(c)
    assert len(c['mappings'])==1689
    assert all('2026-09-20' not in m['fixture_key'] for m in c['mappings'])
    selected=['KXNFL1H-26SEP09NESEA-TIE','KXNFL1HSPREAD-26SEP10SFLAR-LAR3']
    s=State([]);legs=[];at=1788989000.
    for ticker in selected:
        m=next(m for m in c['mappings'] if m['kalshi_ticker']==ticker)
        row=observation(m['market_key'],'kalshi',at=at,point=.4)
        row.update(mapping_reference=m['mapping_reference'])
        s.rows[('observations',m['market_key']+':kalshi')]=row
        legs.append({'market_ticker':ticker,'side':'yes'})
    result=PricingService(s,c,WeightPolicy(delayed_pinnacle=True)).price(legs,at)
    assert result['quote_allowed']
    assert all(set(l['venues'])=={'kalshi'} for l in result['legs'])

"""Compile exact recorded Kalshi definitions with optional external venues."""
import argparse,json,hashlib
from pathlib import Path
from copy import deepcopy
from collections import Counter
from enable_nfl_moneylines import enable
from authorize_nfl_event_mappings import accepted_review,LIMIT_REFERENCE
from combos.market_families import FAMILIES
from combos.nfl_matching import event_identity,half_line,digest
from combos.payoff_risk import nfl_risk_identity
from combos.event_types import validate_event_type
ROOT=Path(__file__).resolve().parents[1]


def expand(config):
    source=ROOT/'runs/morning_research_20260908/pinnacle_delivery_mapping_review/runtime_reviewed_candidates.json'
    candidates=json.loads(source.read_text())['mappings']
    review=ROOT/'runs/nfl_all_payoff_enumeration_20260909/rows.json'
    reviews={r['market_key']:r['review'] for r in json.loads(review.read_text())};sha=hashlib.sha256(review.read_bytes()).hexdigest()
    config,_=enable(config,candidates,reviews,sha)
    fixtures={m['fixture_key']:m['start_at'] for m in candidates}
    by={m['kalshi_ticker']:deepcopy(m) for m in candidates}
    by.update({m['kalshi_ticker']:m for m in config['mappings']})
    for source_mapping in candidates:
        target=by[source_mapping['kalshi_ticker']]
        if not target.get('pinnacle') and source_mapping.get('pinnacle'):
            target['pinnacle']=deepcopy(source_mapping['pinnacle'])
    for m in by.values():
        r=reviews.get(m['market_key'])
        if accepted_review(m,r):
            profile=validate_event_type(m);m['event_type']=profile['event_type']
            m['pinnacle'].update(payoff_reference=profile['reference']+':score-grid:'+sha,
                settlement_policy='nonplayer_rules_v1',limit_currency='USD',limit_unit='stake',limit_reference=LIMIT_REFERENCE)
            m.pop('pricing_block_reason',None)
    rawdir=ROOT/'data/raw/nfl_nonplayer_20260907'
    markets=[]
    for p in rawdir.glob('KXNFL*_*.json'):markets.extend(json.loads(p.read_text())['payload']['markets'])
    teams={m['custom_strike']['football_team']:m['ticker'].rsplit('-',1)[-1] for m in markets if m['ticker'].startswith('KXNFLGAME-')}
    fees={m['kalshi_ticker'].split('-')[0]:m['fees']['kalshi'] for m in candidates}
    excluded=Counter();added=0
    for market in markets:
        ticker=market['ticker']
        if ticker in by:continue
        try:
            family=FAMILIES[ticker.split('-')[0]]
            day,pair=event_identity('KXNFLGAME-'+market['event_ticker'].split('-',1)[1],set(teams.values()))
            fixture='NFL:'+day+':'+'-'.join(pair)
            if fixture not in fixtures:raise ValueError('outside_week_one')
            kind=family.market_type;period=family.period
            team='over' if kind=='totals' else ('TIE' if ticker.endswith('-TIE') else teams[market['custom_strike']['football_team']])
            if team not in (*pair,'over','TIE'):raise ValueError('team_mismatch')
            text=' '.join((market['rules_primary']+' '+market['rules_secondary']).lower().split())
            token={'first_half':'1st half','first_quarter':'1st quarter'}.get(period)
            if token and token not in text:raise ValueError('period_rules_mismatch')
            line=None if kind=='moneyline' else half_line(market['floor_strike'])
            if line is not None and not any(w+str(market['floor_strike']) in text for w in ('more than ','over ')):raise ValueError('threshold_rules_mismatch')
            if team=='TIE' and (period=='full_game' or 'tie' not in text):raise ValueError('tie_rules_mismatch')
            sid=ticker.split('-')[0]
            if sid not in fees:raise ValueError('series_fee_unavailable')
            suffix=kind+':'+team+(':over' if kind=='team_totals' else '')+(':'+str(line) if line is not None else '')
            m=dict(market_key=fixture+(':'+period if period!='full_game' else '')+':'+suffix,
                fixture_key=fixture,start_at=fixtures[fixture],sport='NFL',period=period,market_type=kind,
                kalshi_ticker=ticker,player_prop=False,fees={'kalshi':deepcopy(fees[sid])},
                mapping_reference='kalshi-definition-v1:sha256:'+digest(market),
                payoff_review={'kalshi_rules':[market['rules_primary'],market['rules_secondary']],
                    'status':'exact_kalshi_definition','source':'data/raw/nfl_nonplayer_20260907'})
            if kind=='moneyline' and period!='full_game':m['tie_settlement']='tie_wins' if team=='TIE' else 'team_loses'
            m['risk_identity']=nfl_risk_identity(m);m['event_type']=validate_event_type(m)['event_type']
            by[ticker]=m;added+=1
        except (ValueError,KeyError,TypeError) as exc:excluded[str(exc)]+=1
    config['mappings']=list(by.values())
    config['source_fallback']={'enabled':True,'minimum_two_sided_depth_dollars':100.,'maximum_raw_spread_cents':5.}
    config['quote_reference']={'model':'independent_marginal_reserve_v1','marginal_fraction':0.}
    config.get('candidate_scope',{})['full_game_only']=False
    return config,dict(mappings=len(by),added_kalshi_only=added,excluded=dict(excluded))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--config',action='append',type=Path,required=True);a=p.parse_args()
    for path in a.config:
        c,report=expand(json.loads(path.read_text()));path.write_text(json.dumps(c,indent=2)+'\n');print(path,report)

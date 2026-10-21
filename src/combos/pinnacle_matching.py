"""Catalog-checked, exact Pinnacle selector candidates; separate from payoff approval."""
from collections import defaultdict, Counter
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo
from .nfl_matching import digest, pm_code, half_line
from .market_families import FAMILIES


def bind_selectors(mappings, fixtures, catalog, bookmaker='pinnacle+30'):
    definitions={str(m['marketId']):m for m in catalog}
    candidates=defaultdict(list);rejected=[]
    for fixture in fixtures:
        if fixture.get('sportId')!=14 or fixture.get('tournamentId')!=31:continue
        home,away=(pm_code(fixture['participant'+str(i)+'Abbr']) for i in (1,2))
        day=datetime.fromisoformat(fixture['startTime'].replace('Z','+00:00')).astimezone(ZoneInfo('America/New_York')).date().isoformat()
        fk='NFL:'+day+':'+ '-'.join(sorted((home,away)))
        for mid,market in fixture.get('bookmakerOdds',{}).get(bookmaker,{}).get('markets',{}).items():
            try:
                definition=definitions[mid]
                if definition.get('playerProp') is not False or definition.get('sportId')!=14:raise ValueError('not_verified_non_player_football')
                period={'result':'full_game','p1+p2':'first_half','p1':'first_quarter'}.get(definition['period'])
                kind=definition['marketType']
                if period is None or kind not in ('moneyline','spreads','totals','teamtotals-team1','teamtotals-team2'):continue
                entries=[]
                if set(market['outcomes'])!={str(o['outcomeId']) for o in definition['outcomes']} or len(market['outcomes'])!=2:
                    raise ValueError('catalog_outcomes_mismatch')
                for oid,outcome in market['outcomes'].items():
                    if set(outcome['players'])!={'0'}:raise ValueError('player_outcome_unexpected')
                    v=outcome['players']['0']
                    if v.get('playerName') is not None:raise ValueError('player_outcome_unexpected')
                    parts=v['bookmakerOutcomeId'].split('/')
                    if kind=='moneyline':
                        if parts not in (['home'],['away']):raise ValueError('unknown_moneyline_selector')
                        team=home if parts[0]=='home' else away
                        key=(fk,period,kind,team,None)
                    elif kind=='spreads':
                        line=half_line(parts[0])
                        if len(parts)!=2 or parts[1] not in ('home','away') or line!=Decimal(str(definition['handicap'])):raise ValueError('spread_selector_mismatch')
                        key=(fk,period,kind,home if parts[1]=='home' else away,-line if parts[1]=='home' else line)
                    else:
                        team='over';typ='totals'
                        if kind.startswith('teamtotals-'):
                            expected='home' if kind.endswith('team1') else 'away'
                            if parts[0]!=expected:raise ValueError('team_total_selector_mismatch')
                            team=home if expected=='home' else away;typ='team_totals';parts=parts[1:]
                        line=half_line(parts[0])
                        if len(parts)!=2 or parts[1] not in ('over','under') or line!=Decimal(str(definition['handicap'])):raise ValueError('total_selector_mismatch')
                        key=(fk,period,typ,team,line) if parts[1]=='over' else None
                    entries.append((key,{'outcome_id':oid,'bookmaker_outcome_id':v['bookmakerOutcomeId']}))
                # Both native sides must refer to the same line and be complements.
                native=[e[1]['bookmaker_outcome_id'].split('/') for e in entries]
                if native[0][:-1]!=native[1][:-1] or {n[-1] for n in native} not in ({'home','away'},{'over','under'}):raise ValueError('noncomplementary_native_pair')
                for i,(key,yes) in enumerate(entries):
                    if key is None:continue
                    spec={'fixture_id':fixture['fixtureId'],'market_id':mid,'bookmaker_market_id':market['bookmakerMarketId'],
                          'yes':yes,'no':entries[1-i][1], 'catalog':definition,
                          'selector_status':'exact_catalog_candidate; payoff_limit_units_and_exception_terms_unreviewed'}
                    spec['selector_reference']='oddspapi-selector-v1:sha256:'+digest(spec)
                    candidates[key].append((fixture['startTime'],spec))
            except (KeyError,ValueError,TypeError) as exc:
                rejected.append({'fixture_id':fixture['fixtureId'],'market_id':mid,'reason':str(exc)})
    counts=Counter()
    for m in mappings:
        family=FAMILIES[m['kalshi_ticker'].split('-',1)[0]]
        suffix=m['market_key'][len(m['fixture_key'])+1:].split(':')
        if family.period!='full_game':suffix=suffix[1:]
        kind,team=suffix[:2];line=None if kind=='moneyline' else Decimal(suffix[-1])
        if kind=='moneyline' and family.period!='full_game':kind,line='spreads',Decimal('.5')
        matches=candidates.get((m['fixture_key'],family.period,kind,team,line),[])
        matches=[s for start,s in matches if abs(datetime.fromisoformat(start.replace('Z','+00:00')).timestamp()-m['start_at'])<1]
        m.pop('pinnacle',None)
        if len(matches)==1:
            m['pinnacle']=matches[0];m['pinnacle_selector_status']='exact_candidate'
            counts[family.period+':'+family.market_type]+=1
        else:m['pinnacle_selector_status']='exact_line_missing' if not matches else 'ambiguous_exact_line'
    return {'candidate_mappings_by_family':dict(counts),'candidate_mappings':sum(counts.values()),
            'unmatched_mappings':len(mappings)-sum(counts.values()),'rejected_native_markets':rejected,
            'pricing_ready':False}

"""Exact exchange mappings for all observed non-player NFL market families.

An outright period winner is a >0.5 margin payoff. A two-way moneyline paying
half on ties is a different instrument and never silently substitutes for it.
"""
from collections import Counter, defaultdict
from decimal import Decimal
import re
from .market_families import FAMILIES, PM_FAMILIES
from .nfl_matching import (build_mappings, event_identity, half_line, array, pm_code,
                           polymarket_fee, kalshi_rates, digest)
from .payoff_risk import nfl_risk_identity


def _period_rules(description, period):
    text=' '.join(description.lower().split())
    if period=='first_half' and 'in the first half' not in text:raise ValueError('polymarket_period_rules_mismatch')
    if period=='first_quarter' and 'in the first quarter' not in text:raise ValueError('polymarket_period_rules_mismatch')
    if period=='full_game' and any(p in text for p in ('first half','quarter','second half')):
        raise ValueError('polymarket_period_rules_mismatch')


def _pm_entries(m, aliases):
    family=PM_FAMILIES[m['sportsMarketType']]
    if not m.get('active') or m.get('closed') or not m.get('acceptingOrders'):raise ValueError('polymarket_not_accepting_orders')
    outcomes,tokens=array(m['outcomes']),array(m['clobTokenIds'])
    if len(outcomes)!=2 or len(set(tokens))!=2 or not all(str(t).isdigit() for t in tokens):raise ValueError('invalid_binary_outcomes')
    d=m['description'];_period_rules(d,family.period);rate=polymarket_fee(m)
    if family.market_type=='moneyline':
        # Two-way period moneylines are split-tie contracts, not outright wins.
        if '50-50' not in d:raise ValueError('period_moneyline_tie_terms_unrecognized')
        return []
    line=half_line(m['line']);out=[]
    if family.market_type=='spreads':
        match=re.search(r'resolve to "([^"]+)" if the (.+?) (?:are winning by|outscore the .+? by) (\d+) or more points',d)
        if not match or match[1] not in outcomes:raise ValueError('period_spread_rules_unrecognized')
        i=outcomes.index(match[1]);margin=-(line if i==0 else -line)
        if Decimal(match[3])!=margin+Decimal('.5') or aliases.get(match[2].casefold())!=aliases.get(match[1].casefold()):
            raise ValueError('period_spread_line_and_rules_disagree')
        if f'Otherwise, this market will resolve to "{outcomes[1-i]}".' not in d:raise ValueError('spread_complement_rules_unrecognized')
        for i,label in enumerate(outcomes):out.append(((family.period,'spreads',aliases[label.casefold()],-(line if i==0 else -line)),i))
    elif family.market_type=='totals':
        over=re.search(r'combine to score (\d+) or more points',d)
        under=re.search(r'combined (?:first half |first quarter )?total is less than (\d+)',d)
        if not over or not under or over[1]!=under[1] or Decimal(over[1])!=line+Decimal('.5'):
            raise ValueError('period_total_line_and_rules_disagree')
        if outcomes!=['Over','Under']:raise ValueError('invalid_total_outcomes')
        out.append(((family.period,'totals','over',line),0))
    elif family.market_type=='team_totals':
        over=re.search(r'resolve to "Over" if the (.+?) score (\d+) or more points',d)
        under=re.search(r'If the (.+?) score less than (\d+) points',d)
        if not over or not under or aliases.get(over[1].casefold()) is None or aliases.get(over[1].casefold())!=aliases.get(under[1].casefold()):
            raise ValueError('team_total_team_rules_unrecognized')
        if over[2]!=under[2] or Decimal(over[2])!=line+Decimal('.5') or outcomes!=['Over','Under']:
            raise ValueError('team_total_line_and_rules_disagree')
        out.append(((family.period,'team_totals',aliases[over[1].casefold()],line),0))
    return [(key,(m,i,str(tokens[i]),rate)) for key,i in out]


def build_nonplayer_mappings(kalshi_markets, pm_events, series, season, week):
    mappings,base_review=build_mappings(kalshi_markets,pm_events,series,season,week)
    codes={m['ticker'].rsplit('-',1)[-1] for m in kalshi_markets if m['ticker'].startswith('KXNFLGAME-')}
    teams={m['custom_strike']['football_team']:m['ticker'].rsplit('-',1)[-1]
           for m in kalshi_markets if m['ticker'].startswith('KXNFLGAME-')}
    fixture_start={m['fixture_key']:m['start_at'] for m in mappings}
    candidates=defaultdict(list);rejected=[]
    for event in pm_events:
        pair=tuple(sorted(pm_code(t['abbreviation']) for t in event['teams']))
        fixture='NFL:'+event['eventDate']+':'+'-'.join(pair)
        aliases={label.casefold():pm_code(t['abbreviation']) for t in event['teams']
                 for label in (t['alias'],t['name'],t['abbreviation'])}
        for m in event['markets']:
            family=PM_FAMILIES.get(m.get('sportsMarketType'))
            if not family or family.period=='full_game' and family.market_type!='team_totals':continue
            try:
                for key,value in _pm_entries(m,aliases):candidates[(fixture,*key)].append((event,*value))
            except (KeyError,ValueError,TypeError) as exc:rejected.append({'market_id':m['id'],'reason':str(exc)})
    exclusions=[]
    for m in kalshi_markets:
        sid=m['ticker'].split('-',1)[0];family=FAMILIES.get(sid)
        if not family or family.period=='full_game' and family.market_type!='team_totals':continue
        try:
            if m.get('status')!='active':raise ValueError('kalshi_not_active')
            day,pair=event_identity('KXNFLGAME-'+m['event_ticker'].split('-',1)[1],codes)
            fixture='NFL:'+day+':'+'-'.join(pair)
            if fixture not in fixture_start:raise ValueError('outside_requested_week_or_fixture_unmatched')
            kind=family.market_type;period=family.period
            if kind=='moneyline' and m['ticker'].endswith('-TIE'):raise ValueError('period_tie_requires_joint_score_model')
            team='over' if kind=='totals' else teams[m['custom_strike']['football_team']]
            if team!='over' and team not in pair:raise ValueError('team_not_in_fixture')
            text=' '.join((m['rules_primary']+' '+m['rules_secondary']).lower().split())
            token={'first_half':'1st half','first_quarter':'1st quarter'}.get(period)
            if token and token not in text:raise ValueError('kalshi_period_rules_mismatch')
            line=None if kind=='moneyline' else half_line(m['floor_strike'])
            if line is not None and not any(word+str(m['floor_strike']) in text for word in ('more than ','over ')):
                raise ValueError('kalshi_strict_threshold_unrecognized')
            lookup_kind,lookup_line=kind,line
            if kind=='moneyline':
                if 'all team strikes resolve to no' not in text:raise ValueError('period_winner_tie_terms_unrecognized')
                lookup_kind,lookup_line='spreads',Decimal('.5')
            matches=candidates.get((fixture,period,lookup_kind,team,lookup_line),[])
            if len(matches)!=1:
                if kind=='moneyline' and not matches:raise ValueError('period_winner_split_tie_mismatch_no_exact_spread_equivalent')
                raise ValueError('exact_payoff_not_listed' if not matches else 'ambiguous_exact_payoff')
            event,pm,index,token_id,rate=matches[0]
            suffix=kind+':'+team
            if kind=='team_totals':suffix+=':over'
            if line is not None:suffix+=':'+str(line)
            key=fixture+(':'+period if period!='full_game' else '')+':'+suffix
            proof={'period':period,'kalshi_rules':[m['rules_primary'],m['rules_secondary']],
                   'polymarket_id':pm['id'],'condition_id':pm['conditionId'],'description':pm['description'],
                   'selected_index':index,'token':token_id,'normal_payoff':'strict_threshold_binary; period winner via team minus 0.5',
                   'exception_basis':'postponement_cancellation_and_early_termination_unreviewed'}
            mapping={'market_key':key,'fixture_key':fixture,'sport':'NFL','start_at':fixture_start[fixture],
                'market_type':kind,'period':period,'player_prop':False,'kalshi_ticker':m['ticker'],
                'polymarket_yes_token':token_id,'polymarket_market_id':str(pm['id']),
                'polymarket_condition_id':pm['conditionId'],'polymarket_event_slug':event['slug'],
                'mapping_reference':'nfl-nonplayer-v1:sha256:'+digest(proof),'payoff_review':proof,
                'pricing_block_reason':'pinnacle_payoff_mapping_unreviewed',
                'fees':{'kalshi':{'rate':kalshi_rates(series[sid])['taker'],'reference':'series:'+sid+':sha256:'+digest(series[sid]),
                                 'fee_model':'venue_cash_v2','balance_precision':'.0001'},
                        'polymarket':{'rate':rate,'reference':'market:'+str(pm['id'])+':fee-sha256:'+digest(pm.get('feeSchedule')),
                                      'fee_model':'venue_cash_v2'}}}
            if kind=='moneyline':mapping['tie_settlement']='team_loses'
            mapping['risk_identity']=nfl_risk_identity(mapping);mappings.append(mapping)
        except (KeyError,ValueError,TypeError) as exc:exclusions.append({'kalshi_ticker':m['ticker'],'reason':str(exc)})
    if len({m['kalshi_ticker'] for m in mappings})!=len(mappings):raise ValueError('duplicate mapping ticker')
    return mappings,{'base_review':base_review,'additional_exclusions':exclusions,'rejected_polymarket':rejected,
        'mappings_by_family':dict(Counter(m.get('period','full_game')+':'+m['market_type'] for m in mappings)),
        'pricing_ready':False}

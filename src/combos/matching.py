"""Exact fixture, period, threshold and selected-outcome cross-venue matching."""
import json,re

ALIASES={'connecticut':'uconn','miamioh':'miamiohio','hawaii':'hawaii','southernmississippi':'southernmiss','louisianamonroe':'ulmonroe','louisianalafayette':'louisiana','ncstate':'northcarolinastate','appstate':'appalachianstate','utriograndevalley':'utrgv','southernconnecticutstateowls':'southernconnecticutstate','webberinternationalwarriors':'webberinternational','kentuckystatethorobreds':'kentuckystate','milesgoldenbears':'miles','edwardwaterstigers':'edwardwaters','elizabethcitystatevikings':'elizabethcitystate','tusculumpioneers':'tusculum','centralwashingtonwildcats':'centralwashington','lanedragons':'lane','westvirginiastateyellowjackets':'westvirginiastate','texaswesleyanrams':'texaswesleyan'}

def norm(team):
    team=re.sub(r'\bst\.?\b','state',team.lower())
    s=re.sub('[^a-z0-9]','',team)
    return ALIASES.get(s,s)

def fixture_teams(market):
    m=re.search(r'(?:in the |wins the )(.+?) vs (.+?) college football game',market.get('rules_primary',''))
    # Strip period wording only for fixture identity. match_market separately
    # rejects unsupported periods, preventing first-half/full-game conflation.
    return frozenset(norm(re.sub(r'^(?:1st|2nd|3rd|4th) (?:half|quarter) of the ','',x)) for x in m.groups()) if m else None

def event_index(events):
    out={}
    for event in events:
        if not event['slug'].endswith('2026-09-05'):continue
        ml=[m for m in event['markets'] if m.get('sportsMarketType')=='moneyline']
        if len(ml)!=1:continue
        teams=frozenset(norm(x) for x in json.loads(ml[0]['outcomes']))
        if teams in out: raise ValueError('ambiguous fixture')
        out[teams]=event
    return out

def match_market(kalshi,index):
    teams=fixture_teams(kalshi)
    if teams not in index:return {'status':'fixture_unmatched','teams':sorted(teams or [])}
    event=index[teams]; series=kalshi['ticker'].split('-')[0]
    fixture={'event_slug':event['slug'],'start_time':event.get('startTime'),'teams':sorted(teams)}
    candidates=[]
    for m in event['markets']:
        outcomes=json.loads(m['outcomes']); typ=m.get('sportsMarketType'); strike=kalshi.get('floor_strike')
        idx=None
        if series=='KXNCAAFGAME' and typ=='moneyline':
            selected=norm(kalshi['yes_sub_title'])
            idx=next((i for i,o in enumerate(outcomes) if norm(o)==selected),None)
        elif series=='KXNCAAFTOTAL' and typ=='totals' and strike==m.get('line'):
            idx=next((i for i,o in enumerate(outcomes) if o=='Over'),None)
        elif series=='KXNCAAFSPREAD' and typ=='spreads' and strike is not None and m.get('line') is not None:
            selected=norm(kalshi['yes_sub_title'].split(' wins by ')[0])
            idx=next((i for i,o in enumerate(outcomes) if norm(o)==selected and (m['line'] if i==0 else -m['line'])==-strike),None)
        if idx is not None:
            candidates.append({'token':json.loads(m['clobTokenIds'])[idx],'condition_id':m['conditionId'],'market_slug':m['slug'],'fee_schedule':m.get('feeSchedule'),'fees_enabled':m.get('feesEnabled'),'description':m.get('description'),'outcome':outcomes[idx]})
    if len(candidates)!=1:return {**fixture,'status':'payoff_unmatched' if not candidates else 'ambiguous_payoff','candidates':len(candidates)}
    return {**fixture,**candidates[0],'status':'matched','mapping_scope':'normal_completed_game_only','exception_rules_verified':False}

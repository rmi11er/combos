"""Explicit taxonomy for the CFB leg series observed in the Aug 31–Sep 6 tape.

Unknown series fail classification; they are never silently called player props.
"""
FULL_GAME = frozenset({'KXNCAAFGAME','KXNCAAFSPREAD','KXNCAAFTOTAL'})
TEAM_TOTAL = frozenset({'KXNCAAFTEAMTOTAL'})
PERIOD = frozenset({'KXNCAAF1H','KXNCAAF1HSPREAD','KXNCAAF1HTOTAL',
                    'KXNCAAF1Q','KXNCAAF1QSPREAD','KXNCAAF1QTOTAL'})


def classify_combo(market):
    legs=market.get('mve_selected_legs') or []
    if len(legs)<2:raise ValueError('combo requires at least two legs')
    series={l['event_ticker'].split('-')[0] for l in legs}
    unknown=series-FULL_GAME-TEAM_TOTAL-PERIOD
    if unknown:raise ValueError('unreviewed CFB series: '+','.join(sorted(unknown)))
    team=bool(series & TEAM_TOTAL);period=bool(series & PERIOD)
    scope=('team_total_and_period' if team and period else 'team_total_extension' if team
           else 'period_extension' if period else 'full_game_only')
    return {'scope':scope,'nlegs':len(legs),'series':sorted(series),'has_player_prop':False}

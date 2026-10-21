"""Explicit taxonomy for the non-player NFL families observed in our feeds."""
from dataclasses import dataclass


@dataclass(frozen=True)
class MarketFamily:
    period: str
    market_type: str
    polymarket_type: str
    pinnacle_period: str


FAMILIES = {}
for period, kprefix, pprefix, pperiod in (
    ('full_game','KXNFL','','result'),
    ('first_half','KXNFL1H','first_half_','p1+p2'),
    ('first_quarter','KXNFL1Q','q1_','p1'),
):
    for typ, suffix, pmtype in (('moneyline','GAME' if period=='full_game' else '', 'moneyline'),
                               ('spreads','SPREAD','spreads'),('totals','TOTAL','totals'),
                               ('team_totals','TEAMTOTAL','team_totals')):
        FAMILIES[kprefix+suffix]=MarketFamily(period,typ,pprefix+pmtype,pperiod)
    if period!='full_game':FAMILIES[kprefix+'WINNER']=FAMILIES[kprefix]

PM_FAMILIES={f.polymarket_type:f for f in FAMILIES.values()}
NFL_SERIES={s:f.market_type for s,f in FAMILIES.items()}


def family_for_ticker(ticker):
    try:return FAMILIES[ticker.split('-',1)[0]]
    except (KeyError,AttributeError):raise ValueError('outside_supported_non_player_scope') from None

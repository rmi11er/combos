"""Source settlement normalization for shadow fair values."""
from dataclasses import replace
from .pricing import Interval
from .event_types import validate_event_type


def normalize_pinnacle_interval(observation, mapping, full_game_tie_probability=.01,
                                period_tie_probability=.05):
    """Convert Pinnacle two-way moneyline probabilities to exchange payouts.

    Pinnacle's two-way football moneyline voids a tie; Kalshi/Polymarket
    winner-without-tie contracts pay $0.50 on a tie. Period winner contracts
    treat a tied period as No, so the period transform has no 0.50 term.
    Other binary threshold markets are unchanged for half-point lines.
    """
    if observation.venue != 'pinnacle' or observation.interval is None:
        return observation
    if mapping.get('market_type') != 'moneyline':
        return observation
    period = mapping.get('period', 'full_game')
    # Reviewed period winner selectors are exact half-point spreads: a tied
    # period already loses. Applying a second tie discount would bias fair.
    if period != 'full_game' and mapping.get('pinnacle', {}).get('catalog', {}).get('marketType') == 'spreads':
        return observation
    tie = full_game_tie_probability if period == 'full_game' else period_tie_probability
    if period == 'full_game':
        f = lambda p: (1-tie)*p + .5*tie
    else:
        f = lambda p: (1-tie)*p
    old = observation.interval
    interval = Interval(f(old.lower), f(old.point), f(old.upper))
    return replace(observation, interval=interval)


def settlement_policy(mapping):
    profile = validate_event_type(mapping)
    return profile['reference']

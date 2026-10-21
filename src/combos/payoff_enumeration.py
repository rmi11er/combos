"""Independent score-grid checks of mapped non-player NFL payoffs.

Conditional on completion of the indicated period. Does not approve exceptional
settlement states or infer a probability distribution from the score grid.
"""
from decimal import Decimal


def sign_payoff(margin):
    return None if margin == 0 else int(margin > 0)


def native(spec, home, away, side):
    parts = spec[side]['bookmaker_outcome_id'].split('/')
    kind = spec['catalog']['marketType']
    if kind == 'moneyline':
        if len(parts) != 1 or parts[0] not in ('home', 'away'):
            raise ValueError('invalid moneyline selector')
        return sign_payoff(home-away if parts[0] == 'home' else away-home)
    if kind == 'spreads':
        if len(parts) != 2 or parts[1] not in ('home', 'away'):
            raise ValueError('invalid spread selector')
        margin = Decimal(home-away) + Decimal(parts[0])
        return sign_payoff(margin if parts[1] == 'home' else -margin)
    if kind == 'totals':
        if len(parts) != 2 or parts[1] not in ('over', 'under'):
            raise ValueError('invalid total selector')
        score, line, direction = home+away, Decimal(parts[0]), parts[1]
    elif kind in ('teamtotals-team1', 'teamtotals-team2'):
        team = 'home' if kind.endswith('team1') else 'away'
        if len(parts) != 3 or parts[0] != team or parts[2] not in ('over', 'under'):
            raise ValueError('invalid team-total selector')
        score, line, direction = home if team == 'home' else away, Decimal(parts[1]), parts[2]
    else:
        raise ValueError('unsupported native market')
    return sign_payoff(Decimal(score)-line if direction == 'over' else line-Decimal(score))


def review(mapping, fixture, maximum_score=100):
    spec = mapping.get('pinnacle')
    if not spec or fixture is None:
        return {'status': 'exact_selector_unavailable'}
    period = mapping.get('period', 'full_game')
    expected_period = {'full_game':'result', 'first_half':'p1+p2', 'first_quarter':'p1'}[period]
    catalog = spec['catalog']
    if catalog.get('period') != expected_period or catalog.get('playerProp') is not False or catalog.get('sportId') != 14:
        raise ValueError('catalog scope mismatch')
    alias = lambda team: {'JAX':'JAC', 'LA':'LAR'}.get(team, team)
    home, away = (alias(fixture[f'participant{i}Abbr']) for i in (1, 2))
    prefix = mapping['fixture_key'] + ':'
    if not mapping['market_key'].startswith(prefix):
        raise ValueError('fixture prefix mismatch')
    suffix = mapping['market_key'][len(prefix):].split(':')
    if period != 'full_game':
        if suffix.pop(0) != period:
            raise ValueError('period key mismatch')
    kind = suffix.pop(0)
    if kind != mapping['market_type']:
        raise ValueError('market kind mismatch')
    if kind in ('moneyline', 'spreads', 'team_totals') and suffix[0] not in (home, away):
        raise ValueError('selected team not in fixture')
    mismatches, voids, checked = [], 0, 0
    for hs in range(maximum_score+1):
        for aws in range(maximum_score+1):
            if kind == 'moneyline':
                margin = hs-aws if suffix[0] == home else aws-hs
                target = .5 if period == 'full_game' and margin == 0 else int(margin > 0)
            elif kind == 'spreads':
                margin = hs-aws if suffix[0] == home else aws-hs
                target = int(Decimal(margin) > Decimal(suffix[1]))
            elif kind in ('totals', 'team_totals'):
                score = hs+aws if kind == 'totals' else hs if suffix[0] == home else aws
                direction, line = suffix[-2:]
                if direction != 'over':
                    raise ValueError('unreviewed target total direction')
                target = int(Decimal(score) > Decimal(line))
            else:
                raise ValueError('unsupported target market')
            yes, no = native(spec, hs, aws, 'yes'), native(spec, hs, aws, 'no')
            checked += 1
            if yes is None or no is None:
                voids += 1
            elif yes != target or no != 1-target:
                if len(mismatches) < 3:
                    mismatches.append({'home_score':hs, 'away_score':aws,
                                       'target':target, 'native_yes':yes, 'native_no':no})
    return {'status': 'payoff_mismatch' if mismatches else 'void_basis_required' if voids else 'completed_period_binary_verified',
            'score_pairs_checked': checked, 'void_score_pairs': voids, 'mismatches': mismatches,
            'period': period, 'market_type': kind, 'pricing_authorized': False}

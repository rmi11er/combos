"""Canonical period-aware risk families and signed payoff orientation.

Grouping is conservative across exceptional settlement differences. It grants
no cash-netting or hedge credit to different combo payoffs.
"""
from decimal import Decimal


def nfl_risk_identity(mapping):
    key=mapping['market_key'];fixture=mapping['fixture_key']
    if mapping.get('sport')!='NFL' or not key.startswith(fixture+':'):
        raise ValueError('unsupported_risk_identity')
    parts=key[len(fixture)+1:].split(':')
    period=mapping.get('period','full_game')
    if period not in ('full_game','first_half','first_quarter'):raise ValueError('unsupported_risk_period')
    prefix=fixture
    if period!='full_game':
        if parts[0]!=period:raise ValueError('risk_period_key_mismatch')
        parts=parts[1:];prefix+=':'+period
    teams=fixture.rsplit(':',1)[-1].split('-')
    if len(teams)!=2 or teams!=sorted(set(teams)):raise ValueError('invalid_fixture_risk_teams')
    if parts==['moneyline','TIE'] and period!='full_game' and mapping.get('tie_settlement')=='tie_wins':
        return {'key':prefix+':moneyline:TIE','yes_sign':1}
    if parts[0]=='moneyline' and len(parts)==2 and parts[1] in teams:
        if period!='full_game':
            # A period outright win loses on a tie. It is equivalent to that
            # team's >0.5 margin spread, NOT to NO on the opposing team's win.
            if mapping.get('tie_settlement')!='team_loses':raise ValueError('period_winner_tie_basis_required')
            sign=1 if parts[1]==teams[0] else -1
            return {'key':prefix+':spreads:'+teams[0]+(':0.5' if sign==1 else ':-0.5'), 'yes_sign':sign}
        # The two team contracts both pay .5 for a tie under reviewed rules.
        return {'key':fixture+':moneyline:'+teams[0], 'yes_sign':1 if parts[1]==teams[0] else -1}
    if parts[0]=='spreads' and len(parts)==3 and parts[1] in teams:
        line=Decimal(parts[2])
        if not line.is_finite() or abs(line)%1!=Decimal('.5'):raise ValueError('risk_spread_requires_half_point')
        sign=1 if parts[1]==teams[0] else -1
        canonical=line*sign
        return {'key':prefix+':spreads:'+teams[0]+':'+format(canonical.normalize(),'f'), 'yes_sign':sign}
    if parts[0]=='totals' and len(parts)==3 and parts[1] in ('over','under'):
        line=Decimal(parts[2])
        if not line.is_finite() or abs(line)%1!=Decimal('.5'):raise ValueError('risk_total_requires_half_point')
        return {'key':prefix+':totals:over:'+format(line.normalize(),'f'),'yes_sign':1 if parts[1]=='over' else -1}
    if parts[0]=='team_totals' and len(parts)==4 and parts[1] in teams and parts[2] in ('over','under'):
        line=Decimal(parts[3])
        if not line.is_finite() or abs(line)%1!=Decimal('.5'):raise ValueError('risk_team_total_requires_half_point')
        return {'key':prefix+':team_totals:'+parts[1]+':over:'+format(line.normalize(),'f'),
                'yes_sign':1 if parts[2]=='over' else -1}
    raise ValueError('unsupported_risk_payoff')


def canonical_leg_risk(mapping, selected_side, position_action='sell', quantity=1.):
    """Sign of payoff change, conditional on all other selected combo legs paying 1.

    Buying YES and selling NO have the same sign; selected-side and underlying
    orientation each flip that sign. A combo leg is a conditional sensitivity,
    not an unconditional single-contract holding or an independent hedge.
    """
    if selected_side not in ('yes','no') or position_action not in ('buy','sell'):
        raise ValueError('invalid risk side/action')
    q=Decimal(str(quantity))
    if not q.is_finite() or q<=0:raise ValueError('invalid risk quantity')
    identity=mapping.get('risk_identity')
    if identity is None:
        if mapping.get('market_type') in ('moneyline','spreads','totals','team_totals'):
            identity=nfl_risk_identity(mapping)
        else:
            # Generic synthetic/research mappings retain their original identity.
            identity={'key':mapping['market_key'],'yes_sign':1}
    elif identity!=nfl_risk_identity(mapping):
        raise ValueError('risk_identity_mapping_mismatch')
    sign=identity['yes_sign']*(1 if selected_side=='yes' else -1)
    position_sign=sign*(1 if position_action=='buy' else -1)
    return {'key':identity['key'],'selected_sign':sign,'position_sign':position_sign,
            'position_action':position_action,
            'conditional_payoff_change_dollars':float(q*position_sign),
            'interpretation':'other_selected_combo_legs_pay_one; not hedge credit'}

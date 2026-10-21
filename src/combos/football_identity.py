"""Reviewed OddsPapi football identities; never alters generic team normalization.

Evidence: native full/short pairs in runs/cfb_full_week_20260907/fixtures.json,
reviewed September 7, 2026. Both fields must match; short names alone cannot
activate an alias. Exact fixture kickoff equality remains the caller's gate.
"""
from .matching import norm

VERSION = 'oddspapi_football_native_identity_v1'
# Full name, short name -> existing Kalshi/Polymarket canonical team key.
_REVIEWED = {
    ('fiu panthers', 'fiu'): 'floridainternational',
    ('sam houston state bearkats', 'sam houston state'): 'samhouston',
    ('miami hurricanes', 'miami'): 'miamifl',
    ('louisiana ragin cajuns', 'ragin cajuns'): 'louisiana',
    ('mississippi valley state delta devils', 'mississippi valley'): 'mississippivalleystate',
    ('nicholls colonels', 'nicholls'): 'nichollsstate',
}


def provider_team_identity(fixture, participant):
    """Return canonical identity plus native evidence for participant 1 or 2."""
    if type(participant) is not int or participant not in (1, 2):
        raise ValueError('participant must be integer 1 or 2')
    prefix = f'participant{participant}'
    full, short = fixture.get(prefix + 'Name', ''), fixture.get(prefix + 'ShortName', '')
    if not isinstance(full, str) or not isinstance(short, str) or not short.strip():
        raise ValueError('native football participant short name required')
    pair = (full.strip().casefold(), short.strip().casefold())
    canonical = _REVIEWED.get(pair)
    return {'canonical_team': canonical if canonical is not None else norm(short),
            'provider': 'oddspapi', 'identity_version': VERSION,
            'rule': 'reviewed_exact_full_and_short_pair' if canonical is not None else 'existing_short_name_normalization',
            'native_participant_id': fixture.get(prefix + 'Id'),
            'native_full_name': full, 'native_short_name': short,
            'native_abbreviation': fixture.get(prefix + 'Abbr')}


def provider_team_key(fixture, participant):
    return provider_team_identity(fixture, participant)['canonical_team']

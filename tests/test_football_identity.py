import pytest
from src.combos.football_identity import provider_team_identity, provider_team_key


@pytest.mark.parametrize('full,short,expected', [
    ('FIU Panthers', 'FIU', 'floridainternational'),
    ('Sam Houston State Bearkats', 'Sam Houston State', 'samhouston'),
    ('Miami Hurricanes', 'Miami', 'miamifl'),
    ('Louisiana Ragin Cajuns', 'Ragin Cajuns', 'louisiana'),
    ('Mississippi Valley State Delta Devils', 'Mississippi Valley', 'mississippivalleystate'),
    ('Nicholls Colonels', 'Nicholls', 'nichollsstate'),
])
def test_reviewed_native_pairs_retain_evidence(full, short, expected):
    fixture = {'participant1Name': full, 'participant1ShortName': short, 'participant1Id': 123}
    result = provider_team_identity(fixture, 1)
    assert result['canonical_team'] == expected
    assert result['native_full_name'] == full
    assert result['native_short_name'] == short
    assert result['native_participant_id'] == 123
    assert result['rule'] == 'reviewed_exact_full_and_short_pair'


def test_miami_alias_cannot_apply_to_ohio_or_missing_full_evidence():
    assert provider_team_key({'participant1Name': 'Miami (OH) RedHawks',
                              'participant1ShortName': 'Miami Ohio'}, 1) == 'miamiohio'
    assert provider_team_key({'participant1ShortName': 'Miami'}, 1) == 'miami'
    assert provider_team_key({'participant1Name': 'Miami Hurricanes',
                              'participant1ShortName': 'Miami Ohio'}, 1) == 'miamiohio'

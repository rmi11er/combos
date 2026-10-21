import gzip
import json
from pathlib import Path
import sys
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from combos.observations import Observation, VENUES
from combos.weighted_fair import weighted_fair, capped_weights
from combos.research_store import ObservationStore
from combos.replay import replay_decision
from combos.journal import Journal, read_journal
from combos.oddspapi import OddsPapi, iter_history


def row(venue='kalshi', key='game-a:home-wins', **changes):
    value = {'market_key': key, 'venue': venue, 'observed_at': 100., 'available_at': 101.,
             'active': True, 'source_reference': 'synthetic:test', 'mapping_reference': 'synthetic:reviewed',
             'fee_reference': 'synthetic:zero-fee',
             'yes_bid': .48, 'yes_ask': .52, 'taker_rate': 0.,
             'yes_bid_size': 100., 'yes_ask_size': 100., 'size_unit': 'payout_dollars',
             'decimal_odds_yes': 2., 'decimal_odds_no': 2.,
             'max_stake_yes': 50., 'max_stake_no': 50., 'limit_currency': 'USD', 'limit_unit': 'stake'}
    value.update(changes)
    return value


def test_capacity_fee_interval_and_complement():
    pin = Observation.from_record(row('pinnacle', decimal_odds_yes=1.5, decimal_odds_no=3., max_stake_yes=20., max_stake_no=10.))
    assert pin.bid_capacity == pin.ask_capacity == 30.
    kalshi = Observation.from_record(row(taker_rate=.07))
    assert kalshi.interval.lower == pytest.approx(.48-.07*.48*.52)
    assert kalshi.interval.upper == pytest.approx(.52+.07*.52*.48)
    assert kalshi.selected_interval('no').lower == pytest.approx(1-kalshi.interval.upper)
    for changes in ({'yes_bid_size': 0}, {'size_unit': 'USD_stake'}, {'yes_bid': .7}, {'available_at': 99}):
        with pytest.raises(ValueError): Observation.from_record(row(**changes))
    with pytest.raises(ValueError): Observation.from_record(row('pinnacle', limit_currency='EUR'))


def test_weight_formula_known_answer_and_venue_cap():
    observations = [Observation.from_record(row(v)) for v in VENUES]
    result = weighted_fair(observations, 101, 'pregame')
    # Scores: 10/4, 10/4, 10/1. Cap Pinnacle at .6, share residual equally.
    assert {v: d['weight'] for v,d in result['venues'].items()} == pytest.approx({'kalshi': .2, 'polymarket': .2, 'pinnacle': .6})
    assert result['fair']['point'] == pytest.approx(.5)
    assert result['fair']['lower'] == pytest.approx(.492)
    deep = [Observation.from_record(row(v, yes_bid_size=400, yes_ask_size=400)) if v=='kalshi' else o for v,o in zip(VENUES, observations)]
    assert weighted_fair(deep, 101, 'pregame')['venues']['kalshi']['weight'] > .2
    assert capped_weights({'a': 10000, 'b': 100, 'c': 1}, .4) == pytest.approx({'a': .4, 'b': .4, 'c': .2})


def test_freshness_and_full_coverage_are_required():
    observations = [Observation.from_record(row(v)) for v in VENUES]
    for at, phase in ((100, 'pregame'), (116, 'in_play'), (221, 'pregame')):
        with pytest.raises(ValueError): weighted_fair(observations, at, phase)
    with pytest.raises(ValueError): weighted_fair(observations[:2], 101, 'pregame')
    observations[0] = Observation.from_record(row(active=False))
    with pytest.raises(ValueError, match='inactive'): weighted_fair(observations, 101, 'pregame')


def test_store_dedup_causality_and_suspension(tmp_path):
    store = ObservationStore(tmp_path/'observations.sqlite')
    try:
        assert store.add(row())
        assert not store.add(row())
        with pytest.raises(ValueError, match='conflicting'): store.add(row(yes_bid=.47))
        with pytest.raises(ValueError, match='no prior'): store.latest('game-a:home-wins', 'kalshi', 100)
        store.add(row(active=False, observed_at=102, available_at=103))
        assert store.latest('game-a:home-wins', 'kalshi', 102).active
        assert not store.latest('game-a:home-wins', 'kalshi', 103).active
    finally: store.close()


def test_replay_known_answer_and_same_fixture_exclusion(tmp_path):
    store = ObservationStore(tmp_path/'observations.sqlite')
    try:
        for key in ('a', 'b'):
            for venue in VENUES: store.add(row(venue, key))
        decision = {'decision_id': 'synthetic', 'decision_at': 101, 'phase': 'pregame',
                    'reference_kind': 'trade_price', 'reference_yes_price': .3,
                    'legs': [{'market_key': 'a', 'side': 'yes', 'fixture_key': 'a'},
                             {'market_key': 'b', 'side': 'no', 'fixture_key': 'b'}]}
        result = replay_decision(store, decision)
        assert result['status'] == 'priced'
        assert result['reference_kind'] == 'trade_price'
        assert result['comparisons']['spread_depth_weight']['reference_minus_fair_cents'] == pytest.approx(5)
        assert result['comparisons']['spread_depth_weight']['joint']['upper'] == pytest.approx(.508**2)
        assert replay_decision(store, dict(decision, decision_at=100))['status'] == 'excluded'
        decision['legs'][1]['fixture_key'] = 'a'
        assert 'same-fixture' in replay_decision(store, decision)['reason']
    finally: store.close()


def test_journal_rotation_identity_and_integrity(tmp_path):
    journal = Journal(tmp_path/'journal', chunk_rows=2)
    payload = {'type': 'rfq_created', 'msg': {'creator_id': 'synthetic-creator', 'id': 'synthetic-rfq'}}
    journal.append('connected', {}, 'session')
    journal.append('message', payload, 'session')
    journal.append('disconnected', {'error_type': 'synthetic'}, 'session')
    journal.close()
    rows = list(read_journal(tmp_path/'journal'))
    assert len(rows) == 3
    assert rows[1]['payload']['msg']['creator_id'] == 'synthetic-creator'
    assert len(journal.chunks) == 2
    assert journal.counts['rfq_created_with_creator'] == 1
    with (tmp_path/'journal'/journal.chunks[0]['file']).open('ab') as f: f.write(b'corrupt')
    with pytest.raises(ValueError, match='checksum'): list(read_journal(tmp_path/'journal'))


def test_odds_client_cache_and_credential_redaction(tmp_path):
    class Response:
        status_code = 200
        headers = {'ETag': 'test'}
        def json(self): return {'fixtureId': 'synthetic', 'bookmakers': {}}
    class Session:
        calls = 0
        def get(self, url, params, timeout):
            self.calls += 1
            assert params['apiKey'] == 'synthetic-secret'
            return Response()
    session = Session()
    client = OddsPapi(tmp_path, api_key='synthetic-secret', session=session)
    first = client.get('historical-odds', {'fixtureId': 'synthetic', 'bookmakers': 'pinnacle'})
    assert client.get('historical-odds', {'fixtureId': 'synthetic', 'bookmakers': 'pinnacle'}) == first
    assert session.calls == 1
    with gzip.open(next(tmp_path.rglob('*.json.gz')), 'rt') as f: assert 'synthetic-secret' not in f.read()
    Response.status_code = 401
    with pytest.raises(RuntimeError, match='HTTP 401') as exc:
        OddsPapi(tmp_path/'second', api_key='synthetic-secret', session=session).get('sports')
    assert 'synthetic-secret' not in str(exc.value)


def test_history_preserves_inactive():
    outcome = {'players': {'0': [{'active': False}, {'active': True}]}}
    market = {'outcomes': {'2': outcome}}
    history = {'fixtureId': 'synthetic', 'bookmakers': {'pinnacle': {'markets': {'1': market}}}}
    assert [r['snapshot']['active'] for r in iter_history(history)] == [False, True]


def test_creator_profile_deduplicates_and_keeps_review_separate(tmp_path):
    from combos.creator_profile import profile
    journal = Journal(tmp_path/'journal')
    for at, rfq in ((100, 'a'), (101, 'a'), (102, 'b'), (170, 'c'), (171, 'd')):
        journal.append('message', {'type': 'rfq_created', 'msg': {'id': rfq, 'creator_id': 'synthetic',
            'mve_selected_legs': [{'market_ticker': 'home', 'side': 'yes', 'event_ticker': 'game'}]}}, received_at=at)
    journal.close()
    result = profile([tmp_path/'journal'], tmp_path/'profile', minimum_requests=2)
    assert result['unique_rfqs'] == 4
    assert result['duplicates_ignored'] == 1
    creator = json.loads((tmp_path/'profile/creators.jsonl').read_text())
    assert creator['counts']['separated_duplicate_bursts'] == 2
    assert creator['status'] == 'review'
    assert creator['blacklisted'] is False
    assert creator['markout_labels'] == 0


def test_cli_import_replay_and_transaction_rollback(tmp_path):
    import subprocess
    root = Path(__file__).resolve().parents[1]
    command = [sys.executable, str(root/'scripts/research.py')]
    rows = [row(v, key) for key in ('a', 'b') for v in VENUES]
    inputs = tmp_path/'observations.jsonl'
    inputs.write_text(''.join(json.dumps(r)+'\n' for r in rows))
    db = tmp_path/'observations.sqlite'
    subprocess.run(command+['import-observations', str(inputs), '--db', str(db)], check=True, capture_output=True)
    decisions = tmp_path/'decisions.jsonl'
    decisions.write_text(json.dumps({'decision_id': 'synthetic', 'decision_at': 101, 'phase': 'pregame',
        'reference_kind': 'combo_book_midpoint', 'reference_yes_price': .3,
        'legs': [{'market_key': 'a', 'side': 'yes', 'fixture_key': 'a'},
                 {'market_key': 'b', 'side': 'yes', 'fixture_key': 'b'}]})+'\n')
    # This legacy fixture has neither kickoff metadata nor delayed availability.
    policy = tmp_path/'legacy_weights.json'
    policy.write_text(json.dumps({'delayed_pinnacle': False}))
    subprocess.run(command+['replay', str(decisions), '--db', str(db), '--out', str(tmp_path/'replay'),
                           '--policy', str(policy)], check=True, capture_output=True)
    assert json.loads((tmp_path/'replay/manifest.json').read_text())['complete']
    assert json.loads((tmp_path/'replay/summary.json').read_text())['counts'] == {'priced': 1}
    inputs.write_text(json.dumps(row(key='new'))+'\n'+json.dumps(row(key='invalid', yes_bid_size=0))+'\n')
    failed = subprocess.run(command+['import-observations', str(inputs), '--db', str(db)], capture_output=True)
    assert failed.returncode != 0
    store = ObservationStore(db)
    try:
        with pytest.raises(ValueError, match='no prior'): store.latest('new', 'kalshi', 101)
    finally: store.close()

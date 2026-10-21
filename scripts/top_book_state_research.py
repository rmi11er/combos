"""Causal top-only overlay for fixed-collection research replays."""
from copy import deepcopy
from combos.verified_book_state import VerifiedBookState
from top_book_verification_research import top_candidate_time


class TopBookState(VerifiedBookState):
    def __init__(self, token_keys, certificates):
        super().__init__()
        self.token_keys = token_keys
        self.replayed = certificates
        self.top_certificates = {}

    def consume(self, event):
        super().consume(event)
        r = event['payload']
        kind = event['kind']
        if kind == 'venue_reset' and event['source'] == 'polymarket':
            self.top_certificates.clear()
        elif kind == 'book_rebuild':
            for token in r['tokens']:
                self.top_certificates.pop(self.token_keys.get(token), None)
        elif kind == 'observation' and r.get('venue') == 'polymarket':
            key = r['market_key']
            cert = self.top_certificates.get(key)
            if cert and (r.get('connection_generation') != cert['evidence']['generation']
                         or r.get('book_revision') != cert['evidence']['revision']):
                self.top_certificates.pop(key)
        elif kind == 'book_verification_status' and r.get('status') == 'rejected':
            certificate = self.replayed.get((r.get('source_reference'), r.get('token')))
            if certificate:
                assert certificate['raw_seq'] < event['seq']
                evidence = certificate['evidence']
                assert evidence['available_at'] <= event['received_at']
                self.top_certificates[self.token_keys[r['token']]] = {
                    'evidence': evidence, 'published_at': event['received_at'], 'seq': event['seq']}

    def pair(self, key, now):
        result = super().pair(key, now)
        if result['candidate'] is not None:
            return result
        native = self.books.get(key)
        cert = self.top_certificates.get(key)
        if not native or not cert or cert['published_at'] > now:
            return result
        if not native.get('active') and native.get('invalid_reason') != 'snapshot_depth_quarantine':
            return result
        if native['available_at'] > now:
            return result
        try:
            current = {'bid': [(native['yes_bid'], native['yes_bid_size'])],
                       'ask': [(native['yes_ask'], native['yes_ask_size'])]}
            valid = top_candidate_time(cert['evidence'], token=cert['evidence']['token'],
                generation=native.get('connection_generation'), revision=native.get('book_revision'),
                current_book=current, now=now, maximum_verification_age=self.maximum_age)
        except (ValueError, KeyError, TypeError):
            return result
        candidate = deepcopy(native)
        candidate.update(active=True, observed_at=valid['candidate_observed_at'],
            native_observed_at=native['observed_at'], available_at=max(native['available_at'], cert['published_at']),
            freshness_basis=valid['basis'], verification_event_seq=cert['seq'],
            verification_reference=cert['evidence']['source_reference'], shadow_freshness_candidate=True)
        candidate.pop('invalid_reason', None)
        return dict(result, candidate=candidate)

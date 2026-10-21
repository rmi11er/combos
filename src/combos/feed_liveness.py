"""Connection evidence distinct from per-market book freshness."""
import math


class FeedLiveness:
    def __init__(self, connected_monotonic):
        self.connected = connected_monotonic
        self.last_frame = self.last_data = self.last_pong = None
        self.pending_ping = None
        self.last_ping_rtt = None

    def ping_sent(self, now):
        # Do not overwrite an unanswered ping and disguise its age.
        if self.pending_ping is None:
            self.pending_ping = now

    def received(self, now, *, pong=False):
        self.last_frame = now
        if pong:
            if self.pending_ping is not None:
                self.last_ping_rtt = now-self.pending_ping
                self.last_pong = now
                self.pending_ping = None
        else:
            self.last_data = now

    def evidence(self, now):
        def age(at):
            if at is None:
                return None
            if not math.isfinite(at) or not math.isfinite(now) or now < at:
                raise ValueError('invalid liveness chronology')
            return now-at
        return {'connected_seconds':age(self.connected),
                'last_inbound_frame_age_seconds':age(self.last_frame),
                'last_data_frame_age_seconds':age(self.last_data),
                'last_matched_application_pong_age_seconds':age(self.last_pong),
                'unanswered_application_ping_age_seconds':age(self.pending_ping),
                'last_application_ping_rtt_seconds':self.last_ping_rtt,
                'market_book_synchronization_verified':False,
                'book_observation_time_renewed':False}

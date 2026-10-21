"""Bound jobs by both elapsed process time and calendar time.

On macOS the monotonic clock can stop during system sleep. A calendar deadline
prevents an hour-long capture from silently resuming much later after wake.
"""
import math
import time


class Deadline:
    def __init__(self, seconds):
        if not math.isfinite(seconds) or seconds <= 0:
            raise ValueError('duration must be finite and positive')
        self.seconds = seconds
        self.wall_start = time.time()
        self.monotonic_start = time.monotonic()

    def elapsed(self):
        return {'wall_seconds': time.time() - self.wall_start,
                'monotonic_seconds': time.monotonic() - self.monotonic_start}

    def expired(self):
        return max(self.elapsed().values()) >= self.seconds

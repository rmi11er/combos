"""Persistent subscription-wide request allowance; independent of trading capital."""
import math
from pathlib import Path
import sqlite3
import time


class RequestBudget:
    """Use one shared file per subscription and explicit vendor billing boundaries.

    Seed/reconcile with the account's request_count before use. An attempted HTTP
    request consumes local allowance even if its transport fails or process dies.
    A new billing cycle must be explicitly configured; no calendar-month guess.
    """
    def __init__(self, path, cycle_start, cycle_end, request_limit, reserve_fraction=.1,
                 known_used=0):
        if (not all(math.isfinite(v) for v in (cycle_start, cycle_end, reserve_fraction))
                or cycle_start >= cycle_end or not 0 <= reserve_fraction < 1
                or not isinstance(request_limit, int) or request_limit <= 0
                or not isinstance(known_used, int) or known_used < 0):
            raise ValueError('invalid request budget')
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, timeout=30, isolation_level=None)
        self.start, self.end = cycle_start, cycle_end
        self.limit = math.floor(request_limit*(1-reserve_fraction))
        self.db.execute('''CREATE TABLE IF NOT EXISTS request_budget (
            cycle_start REAL PRIMARY KEY, cycle_end REAL NOT NULL, used INTEGER NOT NULL)''')
        self.db.execute('BEGIN IMMEDIATE')
        try:
            conflict = self.db.execute('SELECT cycle_start,cycle_end FROM request_budget WHERE cycle_start<? AND cycle_end>?',
                (cycle_end, cycle_start)).fetchone()
            if conflict and tuple(conflict) != (cycle_start, cycle_end):
                raise ValueError('overlapping billing cycles')
            self.db.execute('INSERT OR IGNORE INTO request_budget VALUES(?,?,?)', (cycle_start,cycle_end,known_used))
            self.db.execute('UPDATE request_budget SET used=MAX(used,?) WHERE cycle_start=?', (known_used,cycle_start))
            self.db.execute('COMMIT')
        except Exception:
            self.db.execute('ROLLBACK');self.db.close();raise

    def claim(self, endpoint, now=None):
        now = time.time() if now is None else now
        if not math.isfinite(now) or not self.start <= now < self.end:
            raise ValueError('request_budget_billing_cycle_expired_or_not_started')
        if endpoint in ('historical-odds','account'):
            return
        self.db.execute('BEGIN IMMEDIATE')
        try:
            changed = self.db.execute('UPDATE request_budget SET used=used+1 WHERE cycle_start=? AND used<?',
                (self.start,self.limit)).rowcount
            if not changed:raise ValueError('request_budget_exhausted')
            self.db.execute('COMMIT')
        except Exception:
            self.db.execute('ROLLBACK');raise

    def used(self):
        return self.db.execute('SELECT used FROM request_budget WHERE cycle_start=?',(self.start,)).fetchone()[0]

    def close(self):
        self.db.close()


def monthly_requests(active_hours_per_day, active_interval_seconds=30,
                     idle_interval_seconds=300, days=30, calls_per_poll=1):
    """Planning estimate, excluding metadata, errors, retries and historical calls."""
    if not 0 <= active_hours_per_day <= 24 or min(active_interval_seconds,idle_interval_seconds,days,calls_per_poll)<=0:
        raise ValueError('invalid polling schedule')
    return math.ceil(days*calls_per_poll*3600*(active_hours_per_day/active_interval_seconds
                    +(24-active_hours_per_day)/idle_interval_seconds))

"""
Simple in-process rate limiter for login brute-force protection.
Keyed by client IP. State is lost on server restart, which is acceptable
for a single-process deployment. For multi-process or distributed setups,
replace with a Redis-backed implementation.
"""
import time
from typing import Dict, Tuple

_WINDOW_SECONDS = 300       # 5-minute sliding window
_MAX_ATTEMPTS = 10          # failed attempts before lockout
_LOCKOUT_SECONDS = 900      # 15-minute lockout


class RateLimiter:
    def __init__(
        self,
        window: int = _WINDOW_SECONDS,
        max_attempts: int = _MAX_ATTEMPTS,
        lockout: int = _LOCKOUT_SECONDS,
    ):
        self._window = window
        self._max = max_attempts
        self._lockout = lockout
        # {ip: (attempt_count, window_start, locked_until)}
        self._state: Dict[str, Tuple[int, float, float]] = {}

    def is_blocked(self, ip: str) -> bool:
        now = time.monotonic()
        entry = self._state.get(ip)
        if not entry:
            return False
        count, window_start, locked_until = entry
        if locked_until and now < locked_until:
            return True
        if now - window_start > self._window:
            # Window expired — clean up
            del self._state[ip]
            return False
        return False

    def record_failure(self, ip: str) -> None:
        now = time.monotonic()
        entry = self._state.get(ip)
        if not entry or now - entry[1] > self._window:
            self._state[ip] = (1, now, 0.0)
        else:
            count, window_start, _ = entry
            count += 1
            locked_until = (now + self._lockout) if count >= self._max else 0.0
            self._state[ip] = (count, window_start, locked_until)

    def record_success(self, ip: str) -> None:
        self._state.pop(ip, None)


login_limiter = RateLimiter()

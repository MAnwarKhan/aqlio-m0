"""Small application-instance rate limiter behind a replaceable port."""

from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime

from app.ports import ClockPort


class InMemoryRateLimiter:
    def __init__(self, clock: ClockPort) -> None:
        self._clock = clock
        self._events: dict[tuple[str, str], deque[datetime]] = defaultdict(deque)

    def allow(self, *, subject: str, operation: str, limit: int, window_seconds: int) -> bool:
        now = self._clock.now()
        events = self._events[(subject, operation)]
        while events and (now - events[0]).total_seconds() >= window_seconds:
            events.popleft()
        if len(events) >= limit:
            return False
        events.append(now)
        return True

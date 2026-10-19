from collections import deque
from threading import Lock
from time import monotonic


class SlidingWindowRateLimiter:
    """Process-local sliding-window limiter keyed by a caller-supplied identity."""

    def __init__(self, limit: int, window_seconds: float = 60.0):
        if limit < 1:
            raise ValueError("limit must be at least 1")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be positive")
        self.limit = limit
        self.window_seconds = window_seconds
        self._events: dict[str, deque[float]] = {}
        self._lock = Lock()

    def allow(self, key: str, now: float | None = None) -> bool:
        current = monotonic() if now is None else now
        cutoff = current - self.window_seconds
        with self._lock:
            events = self._events.setdefault(key, deque())
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= self.limit:
                return False
            events.append(current)
            return True

    def reset(self) -> None:
        with self._lock:
            self._events.clear()

from collections import OrderedDict, deque
from threading import Lock
from time import monotonic


class SlidingWindowRateLimiter:
    """Bounded, thread-safe, process-local sliding-window request limiter.

    Use a shared gateway or datastore for consistent quotas across workers.
    """

    def __init__(
        self,
        limit: int,
        window_seconds: float = 60.0,
        max_keys: int = 10_000,
    ):
        if limit < 1:
            raise ValueError("limit must be at least 1")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be positive")
        if max_keys < 1:
            raise ValueError("max_keys must be at least 1")
        self.limit = limit
        self.window_seconds = window_seconds
        self.max_keys = max_keys
        self._events: OrderedDict[str, deque[float]] = OrderedDict()
        self._lock = Lock()

    def allow(self, key: str, now: float | None = None) -> bool:
        if not isinstance(key, str) or not key:
            raise ValueError("key must be a non-empty string")
        current = monotonic() if now is None else now
        cutoff = current - self.window_seconds
        with self._lock:
            events = self._events.get(key)
            if events is None:
                if len(self._events) >= self.max_keys:
                    expired_keys = [
                        identity
                        for identity, window in self._events.items()
                        if not window or window[-1] <= cutoff
                    ]
                    for identity in expired_keys:
                        del self._events[identity]
                if len(self._events) >= self.max_keys:
                    return False
                events = deque()
                self._events[key] = events
            else:
                self._events.move_to_end(key)
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= self.limit:
                return False
            events.append(current)
            return True

    def reset(self) -> None:
        with self._lock:
            self._events.clear()

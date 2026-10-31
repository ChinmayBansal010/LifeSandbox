from concurrent.futures import ThreadPoolExecutor

import pytest

from app.core.rate_limit import SlidingWindowRateLimiter


def test_limiter_allows_requests_until_limit():
    limiter = SlidingWindowRateLimiter(limit=2, window_seconds=60)
    assert limiter.allow("client", now=1)
    assert limiter.allow("client", now=2)
    assert not limiter.allow("client", now=3)


def test_limiter_expires_events_at_window_boundary():
    limiter = SlidingWindowRateLimiter(limit=1, window_seconds=10)
    assert limiter.allow("client", now=1)
    assert not limiter.allow("client", now=10)
    assert limiter.allow("client", now=11)


def test_limiter_tracks_keys_independently():
    limiter = SlidingWindowRateLimiter(limit=1)
    assert limiter.allow("client-a", now=1)
    assert limiter.allow("client-b", now=1)
    assert not limiter.allow("client-a", now=2)


def test_limiter_rejects_invalid_configuration_and_keys():
    with pytest.raises(ValueError):
        SlidingWindowRateLimiter(limit=0)
    with pytest.raises(ValueError):
        SlidingWindowRateLimiter(limit=1, window_seconds=0)
    with pytest.raises(ValueError):
        SlidingWindowRateLimiter(limit=1, max_keys=0)
    with pytest.raises(ValueError):
        SlidingWindowRateLimiter(limit=1).allow("")


def test_limiter_bounds_key_cardinality():
    limiter = SlidingWindowRateLimiter(limit=2, max_keys=2)
    assert limiter.allow("one", now=1)
    assert limiter.allow("two", now=1)
    assert limiter.allow("three", now=1)
    assert len(limiter._events) == 2


def test_limiter_is_atomic_under_concurrent_burst():
    limiter = SlidingWindowRateLimiter(limit=25, window_seconds=60)

    def attempt(_index: int) -> bool:
        return limiter.allow("shared-client", now=1)

    with ThreadPoolExecutor(max_workers=32) as pool:
        results = list(pool.map(attempt, range(250)))

    assert sum(results) == 25

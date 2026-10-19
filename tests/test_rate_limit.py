import pytest
from app.core.rate_limit import SlidingWindowRateLimiter

def test_limiter_allows_requests_until_limit():
    limiter=SlidingWindowRateLimiter(limit=2,window_seconds=60)
    assert limiter.allow("client",now=1)
    assert limiter.allow("client",now=2)
    assert not limiter.allow("client",now=3)

def test_limiter_expires_events_at_window_boundary():
    limiter=SlidingWindowRateLimiter(limit=1,window_seconds=10)
    assert limiter.allow("client",now=1)
    assert not limiter.allow("client",now=10)
    assert limiter.allow("client",now=11)

def test_limiter_tracks_keys_independently():
    limiter=SlidingWindowRateLimiter(limit=1)
    assert limiter.allow("client-a",now=1)
    assert limiter.allow("client-b",now=1)
    assert not limiter.allow("client-a",now=2)

def test_limiter_rejects_invalid_configuration():
    with pytest.raises(ValueError):
        SlidingWindowRateLimiter(limit=0)
    with pytest.raises(ValueError):
        SlidingWindowRateLimiter(limit=1,window_seconds=0)

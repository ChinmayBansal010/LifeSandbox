# API rate limiting

The API applies `RATE_LIMIT_PER_MINUTE` to `/api/` requests when `APP_ENV=production`. Development and test environments are not rate limited, and CORS preflight requests are excluded.

The in-process sliding-window limiter is thread-safe and bounds its key table to prevent unbounded memory growth. Its counters are local to one worker process; multiple workers or replicas do not share quotas. Treat it as a per-worker protective layer, not an authoritative distributed quota.

The middleware keys requests by the ASGI connection peer (`request.client.host`) and does not trust arbitrary `X-Forwarded-For` or other client-supplied headers. Behind a reverse proxy, configure the ASGI server's trusted proxy IP ranges narrowly so the peer address is derived only from a verified proxy chain. Never trust forwarded headers from arbitrary clients.

For horizontally scaled production deployments, enforce authoritative limits at a gateway or shared store such as Redis. Monitor 429 responses and tune the per-worker limit against the expected workload.

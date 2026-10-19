# API rate limiting

The API applies the configured `RATE_LIMIT_PER_MINUTE` to `/api/` requests when `APP_ENV=production`. Development and test environments are not rate limited to keep local workflows and integration tests predictable. CORS preflight requests are excluded.

The current limiter uses the request client's network address and an in-process sliding window. It is a protective baseline, not a distributed quota system: separate worker processes do not share counters, and reverse-proxy deployments must configure trusted proxy handling carefully before relying on client IPs.

For multi-worker or horizontally scaled deployments, enforce authoritative limits at a gateway or shared store such as Redis. Monitor 429 rates and adjust limits to the actual workload. Do not trust arbitrary client-supplied identity headers as rate-limit keys.

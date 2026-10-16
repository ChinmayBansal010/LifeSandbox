# API contract

All endpoints use JSON except `POST /api/v1/chat/stream`, which emits SSE. Errors use FastAPI's `detail` object with `code` and safe `message`; unexpected failures return `internal_error` and a request ID header.

- `POST /api/v1/chat` `{ "message": "...", "conversation_id": null, "remember": false, "browse": false }` returns conversation id, reply, intent, selected skill, provider, model and whether the opted-in exchange was saved to Mem0. Set `remember: true` to search and save through Mem0 (requires `MEM0_API_KEY`); set `browse: true` to allow Browser Use web research for this message (requires the optional dependency and `BROWSER_USE_ENABLED=true`).
- `POST /api/v1/chat/stream` emits `run.started`, `assistant.delta`, then `run.completed`; failure emits `run.failed`. Text is currently delivered as one delta, not token-streamed.
- `GET /api/v1/capabilities` reports whether optional Mem0 hosted memory is configured.
- `POST/GET /api/v1/conversations`; `GET /{id}`, `GET /{id}/messages`, `DELETE /{id}`. IDs belonging to another user appear as 404.
- `GET/POST /api/v1/memories`, `PATCH/DELETE /{id}`. Create/update requires consent; records include category, provenance, lifecycle status and source conversation. Replacements supersede matching active facts.
- `GET/PUT /api/v1/memory-policy` manages local memory enablement, category policy, retention and hosted-memory permission. Hosted Mem0 search/save requires both the per-message opt-in and `hosted_memory_allowed=true`.
- `GET/POST /api/v1/projects`, `PATCH /{id}` manage structured project status, progress, blockers and next action.
- `GET/POST /api/v1/tasks`, `PATCH /{id}`, `POST /{id}/complete`; task creation accepts `Idempotency-Key` and validates project ownership.
- `GET/POST /api/v1/reminders`, `DELETE /{id}` schedule or cancel durable reminders. `scheduled_at` must include a UTC offset; `timezone` is an IANA zone. Reminder creation accepts `Idempotency-Key`.
- `GET /api/v1/jobs`, `GET /api/v1/jobs/{id}`, `GET /api/v1/notifications` expose owner-scoped worker state and in-app delivery events.
- `GET/POST /api/v1/approvals`, `POST /{id}/approve|reject` persist a proposal and explicit decision. Approval records are not connected to arbitrary external action execution.
- `GET /api/v1/audit` returns a redacted, owner-scoped event history.
- `POST /api/v1/simulations` accepts starting savings, income, expenses, months and alternatives with changes.
- `POST /api/v1/research` returns Tavily sources or 503 if disabled/unavailable.
- `POST /api/v1/files/upload-url` returns a 5-minute private Neon Object Storage upload URL if configured. `POST /{id}/complete` records metadata. `GET /api/v1/files`, `GET /{id}`, `DELETE /{id}` scope by owner; storage cleanup is not connected.
- `POST /api/v1/feedback`; `GET /health`; `GET /ready`.

Simulation money inputs accept JSON numbers/decimal strings and produce Decimal-serialized values. SSE payloads always contain a `run_id`; no hidden prompts or chain-of-thought are exposed.

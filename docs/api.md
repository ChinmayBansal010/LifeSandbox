# API contract

All endpoints use JSON except `POST /api/v1/chat/stream`, which emits SSE. Errors use FastAPI's `detail` object with `code` and safe `message`; unexpected failures return `internal_error` and a request ID header.

- `POST /api/v1/chat` `{ "message": "...", "conversation_id": null, "remember": false, "browse": false }` returns conversation id, reply, intent, selected skill, provider, model and whether the opted-in exchange was saved to Mem0. Explicit "remember" requests create a local memory only when policy permits; otherwise the response includes a `memory_request` candidate ID for review. Set `remember: true` to search and save through Mem0 (requires `MEM0_API_KEY`); set `browse: true` to allow Browser Use web research for this message (requires the optional dependency and `BROWSER_USE_ENABLED=true`).
- `POST /api/v1/chat/stream` emits `run.started`, `assistant.delta`, then `run.completed`; failure emits `run.failed`. Text is currently delivered as one delta, not token-streamed.
- `GET /api/v1/capabilities` reports whether optional Mem0 and Browser Use integrations are configured.
- `POST/GET /api/v1/conversations`; `GET /{id}`, `GET /{id}/messages`, `DELETE /{id}`. IDs belonging to another user appear as 404.
- `GET/POST /api/v1/memories`, `GET /{id}`, `GET /search?query=...&limit=5`, `PATCH/DELETE /{id}`, `POST /{id}/archive`, `PATCH /{id}/project`. Create/update requires consent; records include category, provenance, lifecycle status, source conversation and optional project. Corrected facts with a stable subject supersede older active values.
- `GET /api/v1/memory-candidates`, `POST /{id}/approve|reject` review explicit chat memory requests. Approval creates a local memory; rejection leaves the candidate as a rejected review record.
- `GET/PUT /api/v1/memory-policy` manages local memory enablement, category policy, retention and hosted-memory permission. Hosted Mem0 search/save requires both the per-message opt-in and `hosted_memory_allowed=true`.
- `GET/POST /api/v1/projects`, `PATCH /{id}` manage structured project status, progress, blockers and next action.
- `GET/POST /api/v1/tasks`, `PATCH /{id}`, `POST /{id}/complete`; task creation accepts `Idempotency-Key` and validates project ownership.
- `GET/POST /api/v1/reminders`, `GET /{id}`, `PATCH /{id}`, `DELETE /{id}` schedule, edit or cancel durable reminders. `POST /api/v1/reminders/recurring` supports daily or weekly recurrence. `GET /api/v1/reminder-schedules` includes recurrence and channel. `scheduled_at` must include a UTC offset; `timezone` is an IANA zone. Reminder creation accepts `Idempotency-Key`.
- `POST /api/v1/tasks/{id}/cancel` cancels a task without deleting its history.
- `GET /api/v1/jobs`, `GET /api/v1/jobs/{id}`, `GET /api/v1/notifications` expose owner-scoped worker state and in-app delivery events.
- `GET/POST /api/v1/approvals`, `POST /{id}/approve|reject` persist a proposal and explicit decision. `POST /api/v1/approved-actions/{id}/execute` runs only approved, unchanged, unexpired `task.create` and `reminder.create` actions with persisted idempotency; external actions have no executor.
- `GET /api/v1/audit` returns a redacted, owner-scoped event history.
- `POST /api/v1/simulations` accepts starting savings, income, expenses, months and alternatives with changes.
- `POST /api/v1/research` returns Tavily sources or 503 if disabled/unavailable.
- `POST /api/v1/files/upload-url` returns a 5-minute private Neon Object Storage upload URL if configured. `POST /{id}/complete` records metadata. `GET /api/v1/files`, `GET /{id}`, `DELETE /{id}` scope by owner; storage cleanup is not connected.
- `POST /api/v1/feedback`; `GET /health`; `GET /ready`.

Simulation money inputs accept JSON numbers/decimal strings and produce Decimal-serialized values. SSE payloads always contain a `run_id`; no hidden prompts or chain-of-thought are exposed.

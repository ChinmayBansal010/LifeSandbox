# API contract

All endpoints use JSON except `POST /api/v1/chat/stream`, which emits SSE. Errors use FastAPI's `detail` object with `code` and safe `message`; unexpected failures return `internal_error` and a request ID header.

- `POST /api/v1/chat` `{ "message": "...", "conversation_id": null }` returns conversation id, reply, intent, selected skill and provider.
- `POST /api/v1/chat/stream` emits `run.started`, `assistant.delta`, then `run.completed`; failure emits `run.failed`. Text is currently delivered as one delta, not token-streamed.
- `POST/GET /api/v1/conversations`; `GET /{id}`, `GET /{id}/messages`, `DELETE /{id}`. IDs belonging to another user appear as 404.
- `GET/POST /api/v1/memories`, `PATCH/DELETE /{id}`. Create/update requires consent and provenance is marked `user-approved`.
- `POST /api/v1/simulations` accepts starting savings, income, expenses, months and alternatives with changes.
- `POST /api/v1/research` returns Tavily sources or 503 if disabled/unavailable.
- `POST /api/v1/files/upload-url` returns a 5-minute private R2 upload URL if configured. `POST /{id}/complete` records metadata. `GET /api/v1/files`, `GET /{id}`, `DELETE /{id}` scope by owner; storage cleanup is not connected.
- `GET /api/v1/jobs/{id}` currently returns 404: durable background jobs are not implemented.
- `POST /api/v1/feedback`; `GET /health`; `GET /ready`.

Simulation money inputs accept JSON numbers/decimal strings and produce Decimal-serialized values. SSE payloads always contain a `run_id`; no hidden prompts or chain-of-thought are exposed.

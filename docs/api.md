# API contract

All endpoints use JSON except `POST /api/v1/chat/stream`, which emits SSE. Errors use FastAPI's `detail` object with `code` and safe `message`; unexpected failures return `internal_error` and a request ID header.

- `POST /api/v1/chat` `{ "message": "...", "conversation_id": null, "remember": false, "browse": false }` returns conversation id, reply, intent, selected skill, provider, model and whether the opted-in exchange was saved to Mem0. Explicit "remember" requests create a local memory only when policy permits; otherwise the response includes a `memory_request` candidate ID for review. Set `remember: true` to search and save through Mem0 (requires `MEM0_API_KEY`); set `browse: true` to allow Browser Use web research for this message (requires the optional dependency and `BROWSER_USE_ENABLED=true`).
- `POST /api/v1/chat/stream` emits `run.started`, `assistant.delta`, then `run.completed`; failure emits `run.failed`. Text is currently delivered as one delta, not token-streamed.
- `GET /api/v1/capabilities` reports Mem0, Browser Use, STT, TTS, and local upload availability.
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
- `POST /api/v1/files` accepts one multipart `file`, stores bytes locally under `FILE_STORAGE_DIR`, validates and extracts PDF, DOCX, TXT, Markdown, CSV, or JSON, and accepts PNG/JPEG as image files. It returns `ready` only after bytes and text extraction (for text formats) are persisted. `GET /api/v1/files`, `GET /{id}`, `GET /{id}/download`, and `DELETE /{id}` are owner-scoped. The legacy `POST /files/upload-url` and `POST /{id}/complete` routes remain for private S3-compatible upload initialization; completion does not yet process file content.
- `POST /api/v1/chat` accepts up to five `attachment_ids`; each must be an owned `ready` file and contributes bounded extracted excerpts or explicit image inputs. Image inputs are sent as data URLs only when `VISION_ENABLED=true` and a non-mock Nebius/OpenRouter provider is configured. Select a vision-capable model; this setting cannot determine model vision support automatically. The provider receives user-attached image bytes.
- `POST /api/v1/audio/transcriptions` accepts multipart audio and an optional language hint when `STT_PROVIDER=faster_whisper`; `POST /api/v1/audio/speech` returns WAV when `TTS_PROVIDER=kokoro`. Both endpoints are disabled by default and require optional voice dependencies.
- `POST /api/v1/feedback`; `GET /health`; `GET /ready`.

Simulation money inputs accept JSON numbers/decimal strings and produce Decimal-serialized values. SSE payloads always contain a `run_id`; no hidden prompts or chain-of-thought are exposed.

## Google integrations

`GET /api/v1/integrations` returns the authenticated user's connected Google accounts and granted capabilities. `POST /api/v1/integrations/google/authorize` accepts selected `calendar.read`, `gmail.read`, `gmail.draft`, and/or `gmail.send` capabilities and returns a Google authorization URL. Google redirects to the configured callback; state is one-time and owner-bound. `DELETE /api/v1/integrations/{connection_id}` revokes where possible and removes encrypted credentials. Chat offers Calendar event/freeBusy lookup, bounded Gmail search/thread read, unsent draft creation, and approval-bound draft sending only when the user's persisted connection has the needed scope. Calendar event writes remain unavailable.

When `gmail.send` is selected in the Connections panel, `gmail.send_draft` can only create a pending approval. The approval record contains the exact draft snapshot; `POST /api/v1/approved-actions/{id}/execute` re-reads and hashes the provider draft and requires the same owner connection and scopes before sending. A timeout/ambiguous provider result is marked `uncertain` and is never blindly retried. The approval panel displays recipients, subject, and body before the user approves.

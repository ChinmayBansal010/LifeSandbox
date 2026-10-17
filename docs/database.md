# Database

Alembic migration `0002_followthrough` adds memory policy, structured projects, tasks, reminders, jobs, in-app notifications, approvals, audit events and idempotency keys. Migration `0003_memory_candidates_lifecycle` adds reviewable memory candidates, memory-to-project links, recurrence/channel fields, approval expiry/execution metadata, and idempotency request hashes. Task, reminder and memory project references use `SET NULL`; notifications cascade with their job. User-owned rows are indexed and HTTP operations scope by principal.

```mermaid
erDiagram
  CONVERSATIONS ||--o{ MESSAGES : contains
  PROJECTS ||--o{ MEMORIES : contextualizes
  MEMORIES ||--o{ MEMORY_CANDIDATES : reviews_into
  PROJECTS ||--o{ TASKS : groups
  TASKS ||--o{ REMINDERS : reminds
  REMINDERS ||--o{ JOBS : schedules
  JOBS ||--o| NOTIFICATIONS : delivers
  CONVERSATIONS ||--o{ FEEDBACK : receives
  CONVERSATIONS { string id PK; string user_id; string title }
  MESSAGES { string id PK; string conversation_id FK; string role; text content }
  MEMORIES { string id PK; string user_id; string content; string status }
  MEMORY_CANDIDATES { string id PK; string user_id; string content; string category; string status }
  PROJECTS { string id PK; string user_id; string title; string status; string next_action }
  TASKS { string id PK; string user_id; string project_id FK; string status; datetime due_at }
  REMINDERS { string id PK; string user_id; string task_id FK; datetime scheduled_at; string status }
  JOBS { string id PK; string user_id; string reminder_id FK; datetime scheduled_at; string status }
  NOTIFICATIONS { string id PK; string user_id; string job_id FK; string text }
  FILES { string id PK; string user_id; string filename; string status }
  FEEDBACK { string id PK; string user_id; string conversation_id; int rating }
```

Apply migrations using `uv run alembic upgrade head`. Fresh SQLite migrations were exercised; PostgreSQL worker concurrency was exercised against an isolated test database. Development startup creates missing tables as a convenience, but it does not alter existing schemas. Run the persistent reminder worker with `docker compose up -d worker` or `uv run python -m app.jobs.worker` for a native backend. Due jobs create one persistent in-app notification each; there is no email, push, or mobile delivery. SQLite is suitable for local single-process use; PostgreSQL is recommended for multiple workers. No embedding vectors are stored in the database.

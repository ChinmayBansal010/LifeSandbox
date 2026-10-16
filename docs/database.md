# Database

Alembic migration `0002_followthrough` adds persistent memory policy, structured projects, tasks, reminders, jobs, in-app notifications, approvals, audit events and idempotency keys. Task and reminder references to projects/tasks use `SET NULL`; notifications cascade with their job. User-owned rows are indexed and HTTP operations scope by principal. Memory saving still requires explicit consent and is not automatically extracted from chat. Local approved SQL memories are retrieved for relevant prompts.

```mermaid
erDiagram
  CONVERSATIONS ||--o{ MESSAGES : contains
  PROJECTS ||--o{ TASKS : groups
  TASKS ||--o{ REMINDERS : reminds
  REMINDERS ||--o{ JOBS : schedules
  JOBS ||--o| NOTIFICATIONS : delivers
  CONVERSATIONS ||--o{ FEEDBACK : receives
  CONVERSATIONS { string id PK; string user_id; string title }
  MESSAGES { string id PK; string conversation_id FK; string role; text content }
  MEMORIES { string id PK; string user_id; string content; string status }
  PROJECTS { string id PK; string user_id; string title; string status; string next_action }
  TASKS { string id PK; string user_id; string project_id FK; string status; datetime due_at }
  REMINDERS { string id PK; string user_id; string task_id FK; datetime scheduled_at; string status }
  JOBS { string id PK; string user_id; string reminder_id FK; datetime scheduled_at; string status }
  NOTIFICATIONS { string id PK; string user_id; string job_id FK; string text }
  FILES { string id PK; string user_id; string filename; string status }
  FEEDBACK { string id PK; string user_id; string conversation_id; int rating }
```

Apply migrations using `uv run alembic upgrade head`. Development startup creates missing model tables as a convenience; existing databases still require migrations to add columns. Run the persistent reminder worker with `uv run python -m app.jobs.worker`. Due reminders create one database notification per job; there is no email, push, or mobile delivery. SQLite is suitable for local single-process use; PostgreSQL is recommended for multiple workers. PostgreSQL live integration has not been run in this environment. No embedding vectors are stored in the database.

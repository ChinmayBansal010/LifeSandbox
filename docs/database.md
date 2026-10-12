# Database

The initial Alembic migration creates `conversations`, `messages`, `memories`, `feedback` and `files`. Messages cascade with conversation deletion. User-owned rows are indexed by `user_id`; application queries scope by principal. Memories require explicit `consent=true` at create/update and are not automatically extracted from chat.

```mermaid
erDiagram
  CONVERSATIONS ||--o{ MESSAGES : contains
  CONVERSATIONS ||--o{ FEEDBACK : receives
  CONVERSATIONS { string id PK; string user_id; string title }
  MESSAGES { string id PK; string conversation_id FK; string role; text content }
  MEMORIES { string id PK; string user_id; string content; string status }
  FILES { string id PK; string user_id; string filename; string status }
  FEEDBACK { string id PK; string user_id; string conversation_id; int rating }
```

Apply migrations using `uv run alembic upgrade head`. Development startup creates model tables as a convenience; production requires migrations. PostgreSQL and pgvector live integration has not been run in this environment. No embedding vectors are currently stored in the database.

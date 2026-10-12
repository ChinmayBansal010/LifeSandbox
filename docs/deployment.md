# Deployment

Local DB/API: `docker compose up --build`; migration: `uv run alembic upgrade head`; API health: `/health`, readiness: `/ready`. The container uses Python 3.13 and a non-root user. Configure Cloud Run with a PostgreSQL `DATABASE_URL`, `APP_ENV=production`, production auth integration, provider credentials and private R2 bucket as needed. Set secrets through the platform secret manager, never bake `.env` into the image. Run Alembic as a release step before shifting traffic.

No Cloud Run deployment was performed. PostgreSQL migrations and pgvector operations have not been exercised against a live database. Set a database URL with `postgresql+asyncpg://` for the app; Alembic's synchronous migration URL should be configured for the chosen deployment migration command. Recovery: restore database from managed backups, then redeploy compatible migration revision. Redis and QStash are optional and currently unused.

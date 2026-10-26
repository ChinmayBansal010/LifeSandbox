# Deployment

For local development, `docker compose up --build -d` starts PostgreSQL, FastAPI, and the polling reminder worker. The frontend runs separately with Vite; see the root README for Windows/Linux setup. The API health endpoints are `/health` and `/ready`. The container uses Python 3.13 and a non-root user. Configure Cloud Run with PostgreSQL, `APP_ENV=production`, production auth integration, provider credentials and private Neon Object Storage bucket as needed. Set secrets through the platform secret manager, never bake `.env` into the image. Run Alembic as a release step before shifting traffic.

For Neon Object Storage, provision a private `uploads` bucket on the Neon branch, then run `neon env pull --file .env` with the Neon CLI linked to that project and branch. Copy the generated `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`, and `AWS_ENDPOINT_URL_S3` values into the deployment secret manager; set `NEON_STORAGE_BUCKET=uploads`. Use a branch credential scoped to `storage:read` and `storage:write`. The bucket is private by default unless explicitly configured otherwise. The Neon endpoint and credentials are branch-specific, so point each deployment environment at its matching branch.

No Cloud Run deployment was performed. PostgreSQL migrations and pgvector operations have not been exercised against a live database. Set a database URL with `postgresql+asyncpg://` for the app; Alembic's synchronous migration URL should be configured for the chosen deployment migration command. Recovery: restore database from managed backups, then redeploy compatible migration revision. Redis and QStash are optional and currently unused.

The Compose worker polls every two seconds, atomically claims due jobs, reclaims stale leases, retries up to three attempts, and records one in-app notification per successful delivery. For a native backend, run `uv run python -m app.jobs.worker` in a separate process. PostgreSQL is required for multiple workers; SQLite is intended for one worker. Reminder recurrence supports daily and weekly in-app delivery. No email, push, or mobile channel is configured. The Compose file currently has no named PostgreSQL volume; `docker compose down` removes its container data, so use `docker compose stop` to pause the local database without removing it.

## Browser Use in Docker Compose

The Docker API image builds with full support for headless public-web GitHub research:

- **System Runtime:** The API image installs system `chromium`, `fonts-liberation`, and `ca-certificates`. The browser executable is placed at `/usr/bin/chromium` and exported via `CHROME_BIN=/usr/bin/chromium` and `CHROME_PATH=/usr/bin/chromium`.
- **Python Extra:** The `browser` dependency extra (`browser-use>=0.13,<0.14`) is installed during the container build step via `uv sync --locked --no-dev --extra browser`.
- **Shared Memory:** The `api` service in `docker-compose.yml` configures `shm_size: '1gb'` to prevent containerized Chromium tab crashes under memory-intensive page evaluations.
- **Safety & Permissions:** The browser runs under non-root `appuser` (uid 10001) with temporary directory profiles (`/tmp/life-sandbox-browser-use`), zero persistent cookies or authenticated sessions, downloads disabled (`accept_downloads=False`), and navigation strictly restricted to `github.com`.

### Build & Startup

1. Enable Browser Use in your `.env`:
   ```bash
   BROWSER_USE_ENABLED=true
   LLM_PROVIDER=openrouter  # or nebius
   OPENROUTER_API_KEY=sk-or-v1-...
   OPENROUTER_MODEL=anthropic/claude-3.5-sonnet
   ```
2. Build and start the container stack:
   ```bash
   docker compose build api
   docker compose up -d
   ```

### Verification Flow

1. Check that the container includes Chromium and verify its version:
   ```bash
   docker compose exec api chromium --version
   # Expected output: Chromium 120+ (Debian package version)
   ```
2. Check that the capabilities endpoint reports Browser Use as ready:
   ```bash
   curl http://localhost:8000/api/v1/capabilities
   # Expected JSON snippet: {"browser_use_enabled": true, ...}
   ```
3. Test a safe GitHub research request:
   ```bash
   curl -X POST http://localhost:8000/api/v1/chat \
     -H "Content-Type: application/json" \
     -d '{"message": "Need ZCU104 FPGA AI accelerator repo for inference", "browse": true}'
   ```
   The response returns HTTP 200 with verified repository citations and extracted hardware/license details.

### Troubleshooting

- **`browser_use_enabled` reports `false` in `/api/v1/capabilities`:**
  - Verify that `BROWSER_USE_ENABLED=true` is set in `.env` or passed into the container environment.
  - Verify that `LLM_PROVIDER` is set to `openrouter` or `nebius` with non-empty API keys and models (`Mock` provider does not satisfy live browser research).
  - Verify that the executable is present: `docker compose exec api which chromium`.
- **HTTP 503 `browser_use_not_configured`:**
  - The API returns HTTP 503 when a user requests `browse: true` but Browser Use is disabled or unconfigured, preserving explicit error boundaries without fallback hallucinations.

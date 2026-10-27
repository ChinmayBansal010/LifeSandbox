# Deployment

The supported low-cost production topology is Cloudflare Pages for the React application, Cloud Run for the FastAPI API and background jobs, and Neon Postgres for durable application data. The configured Nebius Token Factory model is `nvidia/Nemotron-3_5-Lightning`.

```
Browser → Cloudflare Pages + /api proxy → Cloud Run API → Neon Postgres
                                           └──────────→ Nebius Token Factory
Cloud Scheduler ─────────────────────────→ Cloud Run one-shot worker
```

The Pages proxy is deliberate: it makes the browser see a single origin, so secure login cookies and Google OAuth callbacks work correctly. Do not set `VITE_API_BASE_URL` in Pages; configure the Pages secret `API_ORIGIN` with the Cloud Run API URL instead.

## One-time setup

1. Create a Neon Postgres project and copy its **pooled** connection string. Replace `postgresql://` with `postgresql+asyncpg://` for `DATABASE_URL`.
2. In Google Cloud, enable Cloud Run, Cloud Build, Artifact Registry, Secret Manager, and Cloud Scheduler APIs. Billing must be attached even when usage remains within free allowances.
3. Create the three deployment secrets; values are never stored in Git:

   ```bash
   printf '%s' "$DATABASE_URL" | gcloud secrets create life-sandbox-database-url --data-file=-
   printf '%s' "$NEBIUS_API_KEY" | gcloud secrets create life-sandbox-nebius-api-key --data-file=-
   openssl rand -hex 32 | gcloud secrets create life-sandbox-auth-secret --data-file=-
   ```

4. In Cloudflare Pages, import this repository with `frontend` as the project root, `npm run build` as the build command, and `dist` as the output directory. Set the encrypted Pages secret `API_ORIGIN` to the deployed Cloud Run URL, for example `https://life-sandbox-api-<hash>-uc.a.run.app`.
5. Add your Pages address to Google OAuth authorized redirect URIs when Google sign-in is enabled:

   ```text
   https://<your-pages-domain>/api/v1/auth/google/callback
   https://<your-pages-domain>/api/v1/integrations/google/callback
   ```

   Configure the matching `GOOGLE_AUTH_CALLBACK_URL`, `GOOGLE_OAUTH_CALLBACK_URL`, and `GOOGLE_AUTH_FRONTEND_URL` as Cloud Run secrets/environment values before enabling those features.

## Deploy API and worker

From the repository root, after creating the secrets above:

```bash
export GOOGLE_CLOUD_PROJECT="your-project-id"
export FRONTEND_ORIGIN="https://<your-pages-domain>"
./deploy/cloudrun/deploy.sh
```

The script builds an immutable image, runs Alembic before serving traffic, deploys the API with `APP_ENV=production` and JWT-only authentication, and creates the `life-sandbox-worker` Cloud Run Job. It does not create a schedule because the scheduler service account is organization-specific. In Cloud Scheduler, create an authenticated HTTP job every minute that calls the Cloud Run Jobs `:run` endpoint for `life-sandbox-worker`. Grant that service account only the permission to run this job. The worker runs `python -m app.jobs.worker --once`, claims due work atomically, and exits.

After the first deployment, update the Cloudflare Pages `API_ORIGIN` secret with the printed URL and redeploy Pages. Verify:

```bash
curl -fsS "https://<your-pages-domain>/api/v1/capabilities"
curl -fsS "https://<cloud-run-url>/ready"
```

## Production notes

- `NEBIUS_API_KEY`, `DATABASE_URL`, and `AUTH_SECRET` must remain secret-manager values. The API uses the Nebius OpenAI-compatible endpoint `https://api.tokenfactory.nebius.com/v1` and never exposes the key to the browser.
- The API container scales to zero. The recommended 1 GiB limit accommodates the API and optional document processing; keep `BROWSER_USE_ENABLED=false` until Chromium workloads are deliberately tested and budgeted.
- The current interactive `/api/v1/files` endpoint writes to the container filesystem. Do not advertise durable production uploads until it has been migrated to the existing private Neon Object Storage flow; Cloud Run instance files are ephemeral. Application data, conversations, tasks, reminders, and memories are durable in Neon Postgres.
- Run a restore test for the Neon project and check Cloud Run / Cloud Scheduler logs after the first reminder is due.

## Local containers

For local development, `docker compose up --build -d` starts PostgreSQL, FastAPI, and the polling reminder worker. The frontend runs separately with Vite; see the root README for Windows/Linux setup. The API health endpoints are `/health` and `/ready`. The container uses Python 3.13 and a non-root user.

For Neon Object Storage, provision a private `uploads` bucket on the Neon branch, then run `neon env pull --file .env` with the Neon CLI linked to that project and branch. Copy the generated `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`, and `AWS_ENDPOINT_URL_S3` values into the deployment secret manager; set `NEON_STORAGE_BUCKET=uploads`. Use a branch credential scoped to `storage:read` and `storage:write`. The bucket is private by default unless explicitly configured otherwise. The Neon endpoint and credentials are branch-specific, so point each deployment environment at its matching branch.

The deployment script runs PostgreSQL migrations before it deploys the service. Recovery is: restore the Neon database from managed backups, then deploy an image compatible with the restored migration revision. Redis and QStash are optional and currently unused.

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

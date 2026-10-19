# Life Sandbox

Local-first decision-support app with a React/Vite frontend and FastAPI backend, deterministic cash-flow projections, owner-scoped conversation and memory APIs, a LangGraph workflow, and replaceable provider adapters.

## Current status

This repository began empty. The implemented core supports a deterministic mock LLM and SQLite for local development, plus Nebius/OpenRouter chat adapters, Tavily research, private Neon Object Storage presigned uploads, PostgreSQL-compatible SQLAlchemy models, and Alembic migrations. The frontend sends chat requests to the backend; choose a configured provider in `.env` for model-generated replies. The limitations in [docs/architecture.md](docs/architecture.md) are material: this is a working foundation, not the entire production platform envisioned by the brief.

## Run on Windows or Linux

The recommended development setup runs PostgreSQL and the API in Docker, and runs the frontend with Vite on your computer. Python and `uv` are not required for this setup.

### Prerequisites

- Git.
- Docker Desktop with Linux containers on Windows, or Docker Engine and the Docker Compose plugin on Linux. On Windows, Docker Desktop should use the WSL 2 backend.
- Node.js 22.12 or newer and npm for the frontend.

Clone or download the repository, then open a terminal in its root directory (the directory containing `docker-compose.yml`). Create your local environment file. In Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

On Linux, macOS, or Git Bash:

```bash
cp .env.example .env
```

The `.env` file is local configuration and is excluded from Git. Do not commit API keys or other secrets. The example selects `LLM_PROVIDER=mock`, which needs no API credentials and is sufficient to check that the app runs.

### Start the backend

From the repository root, build and start PostgreSQL, FastAPI, and the reminder worker:

```bash
docker compose up --build -d
```

Check service status and API logs with:

```bash
docker compose ps
docker compose logs -f api
docker compose logs -f worker
```

The API is at <http://localhost:8000>; its interactive docs are at <http://localhost:8000/docs>. Check <http://localhost:8000/health> and <http://localhost:8000/ready> to verify the API and database. The database is published on host port `5433` and listens on port `5432` inside Docker. The host port is `5433` to avoid conflicts with a PostgreSQL server already installed on the computer. The API container connects to the Compose database over its private network.

### Start the frontend

Open a second terminal in the repository root and run:

```bash
cd frontend
npm ci
npm run dev
```

Open the URL Vite prints, normally <http://localhost:5173>. The Vite development server proxies `/api` requests to the backend on port `8000`, so both services need to be running. To make the frontend reachable from other devices on your network, run `npm run dev -- --host 0.0.0.0` instead; this is not needed for normal use on the same computer.

To stop the frontend, press `Ctrl+C` in its terminal. Stop the Docker services while keeping their containers with `docker compose stop`, and start them again with `docker compose start`.

> **Database data:** the current Compose file does not define a persistent named volume. `docker compose down` removes the database container and its data. Use `docker compose stop` if you need to stop and later resume this local database. Back up data before removing or replacing containers.

### Run the backend without Docker (optional)

For a native backend, install Python 3.13 and [`uv`](https://docs.astral.sh/uv/getting-started/installation/). From the repository root, copy `.env.example` to `.env` as shown above, then set this value in `.env` to use SQLite:

```dotenv
DATABASE_URL=sqlite+aiosqlite:///./life_sandbox.db
```

Install the Python dependencies and start FastAPI:

```bash
uv sync --locked
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

In development, FastAPI creates the local SQLite schema on startup. Keep the frontend running in a separate terminal using the steps above. If you want the native backend to use the Compose PostgreSQL database instead, start it with `docker compose up -d db` and set `DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5433/lifesandbox` in `.env`; run `uv run alembic upgrade head` before starting the backend. The Docker API service always uses the internal Compose database URL, regardless of the `DATABASE_URL` value in `.env`. Compose applies Alembic migrations before starting the API and worker.

### Applying changes

- Frontend source changes under `frontend/src` are applied by Vite HMR while `npm run dev` is running. Changes to frontend dependencies require `npm ci` and a Vite restart.
- With the Docker backend, Python source changes are **not** applied automatically: the image contains a copy of the source and Compose does not mount the source directory. Rebuild and restart with `docker compose up --build -d` so the migration job and API use the new image.
- Changes to `.env` are **not** applied to an already-running API container. Recreate it with `docker compose up -d --force-recreate api`. If you changed Python dependencies in `pyproject.toml` or `uv.lock`, use `docker compose up --build -d api` instead.
- After editing `docker-compose.yml`, apply the updated service configuration with `docker compose up -d`; add `--build` if the change affects the image.
- The Compose API service explicitly sets `DATABASE_URL` to the internal `db` service address. Changing `DATABASE_URL` in `.env` therefore affects a native backend, but not the Docker API's database connection.
- With the native backend, `uv run uvicorn app.main:app --reload` reloads Python source changes. Changes to `.env` still require stopping and restarting Uvicorn.

### Model and optional features

For model-generated replies, set `LLM_PROVIDER=openrouter` or `LLM_PROVIDER=nebius` in `.env`, and provide that provider's API key and model. Recreate the Docker API after changing these settings. The default `LLM_PROVIDER=mock` is credential-free but produces deterministic demo replies rather than reasoning about prompts.

Optional hosted memory uses Mem0 Platform. Set `MEM0_API_KEY` in `.env`; the chat UI then offers a per-exchange opt-in. Hosted memory also requires permission in `/api/v1/memory-policy`. See [RAG and memory](docs/rag-and-memory.md) for data handling details.

The Memory & tasks panel manages approved local memories, explicit memory requests awaiting review, projects, tasks, reminders, integrations, and action proposals. Approved SQL memories are retrieved across conversations using lexical matching. Compose runs the durable reminder worker; for a native backend, run `uv run python -m app.jobs.worker` in a separate process. Successful reminder delivery creates an in-app notification; email and push reminder delivery are not configured. The approval executor supports validated local task/reminder creation and approval-bound Gmail draft sending when Google OAuth is configured. Calendar writes and purchases have no executor. See [plugin audit](docs/plugin-audit.md) for integration state and verification limits.

Optional Browser Use research requires the browser extra and Chromium. Follow [providers](docs/providers.md); the documented `uv sync --locked --extra browser` and `uv run browser-use install` commands apply to the native Python setup. Set `BROWSER_USE_ENABLED=true` and restart the backend after changing `.env`.

### Research and Google connections

When Tavily is configured, research requests can use `research.search` directly in chat and return cited sources. Google app sign-in and Google Calendar/Gmail connections are separate flows. For sign-in, register `GOOGLE_AUTH_CALLBACK_URL` in the Google OAuth client and set `GOOGLE_AUTH_FRONTEND_URL` plus a long random `AUTH_SECRET`; use the callback URL shown in `.env.example`. Add the existing `GOOGLE_OAUTH_CALLBACK_URL` separately if you also want Calendar/Gmail connections. Enable the Calendar and Gmail APIs in Google Cloud. Generate `GOOGLE_TOKEN_ENCRYPTION_KEY` with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`; protect and back it up separately from the database. The Memory & follow-through panel's Connections tab lets each signed-in user select and authorize provider scopes. Chat supports Calendar reads/free/busy, Gmail search/thread reads and unsent drafts. If the user grants the separate Gmail send scope, sending is an approval-only action that displays exact contents and checks the draft again before execution. Calendar event writes are not available. Live Google OAuth has not been verified in this environment.

Run backend checks with `uv run ruff check .`, `uv run pyright`, and `uv run pytest`. Run the prompt and agent regression eval harness with `npm run eval` or `uv run pytest tests/test_llm_eval_regression.py` (see [docs/evaluation.md](docs/evaluation.md)). Run the frontend production build from `frontend` with `npm run build`.

In development, authentication maps to `local-user`. Before deployment, set `APP_ENV=production` and `AUTH_MODE=jwt` with an appropriate secret, issuer, and audience. The current JWT implementation supports HS256 only; configure a trusted identity integration before production.

## API

See [docs/api.md](docs/api.md). Main capabilities include chat and SSE, conversation/memory/project/task/reminder CRUD, durable reminder jobs, approval records, simulations, research, file upload metadata, feedback, health and readiness.

### Voice and document input

Document uploads work locally without cloud credentials. The chat paperclip uploads PDF, DOCX, TXT, Markdown, CSV, JSON, PNG, and JPEG files to `FILE_STORAGE_DIR` (default `./data/uploads`). Text documents get bounded text extraction; images are stored and can be interpreted when a vision-capable Nebius/OpenRouter model is configured with `VISION_ENABLED=true`. Images are sent to that model only when explicitly attached to a chat. Files are private by authenticated API ownership. Apply Alembic migrations before production use. The existing S3 presigned upload URL remains available for deployments, but that legacy upload route does not yet run document extraction or image processing; use the multipart `/api/v1/files` workflow for processed files.

Speech providers are opt-in and are installed outside the locked base environment: run `uv pip install --python .venv/bin/python 'faster-whisper>=1.1,<2' 'kokoro>=0.9,<1' 'soundfile>=0.13,<1'` (or use your virtualenv's `pip`). Set `STT_PROVIDER=faster_whisper` or `TTS_PROVIDER=kokoro` to enable an endpoint and restart the API. The first use downloads configured model weights (Whisper `tiny`, Kokoro 82M by default), requiring network access and additional disk/RAM. No model weights are bundled. faster-whisper code is MIT licensed and Kokoro code/model are Apache-2.0; transitive runtime and voice assets have separate terms and need review before redistribution. Leave providers disabled to keep the normal installation light. Browser recording requires MediaRecorder and microphone permission; transcript review is required before sending. See `.env.example` for limits and `docs/api.md` for routes.

## Architecture and operations

See [architecture](docs/architecture.md), [database](docs/database.md), [agents](docs/agents.md), [RAG and memory](docs/rag-and-memory.md), [providers](docs/providers.md), [evaluation](docs/evaluation.md), [security](docs/security.md), [deployment](docs/deployment.md), [workflow reliability](docs/WORKFLOW_RELIABILITY.md), [tool security](docs/TOOL_SECURITY_MODEL.md), [rate limiting](docs/RATE_LIMITING.md), [frontend persistence](docs/FRONTEND_PERSISTENCE.md), and [local testing](docs/LOCAL_TESTING.md). Configuration inventory is in `.env.example`.

If a user explicitly asks to send a draft and grants the separate Gmail send scope, chat creates a pending approval that shows the exact recipients, subject, and body. The user must approve and execute it in the Approvals tab. Uncertain provider outcomes are not retried automatically. Calendar event writes remain unavailable.

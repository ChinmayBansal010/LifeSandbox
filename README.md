# Life Sandbox Backend

Local-first FastAPI backend for conversational decision support, with deterministic cash-flow projections, owner-scoped conversation and memory APIs, a LangGraph workflow, and replaceable provider adapters.

## Current status

This repository began empty. The implemented core supports a deterministic mock LLM and SQLite for local development, plus Nebius/OpenRouter chat adapters, Tavily research, private Neon Object Storage presigned uploads, PostgreSQL-compatible SQLAlchemy models and an Alembic initial migration. The frontend sends chat requests to the backend; choose a configured provider in `.env` for model-generated replies. The limitations in [docs/architecture.md](docs/architecture.md) are material: this is a working foundation, not the entire production platform envisioned by the brief.

## Run locally

Install Python 3.13 and `uv`, then start the local PostgreSQL service before migrating. This is required when `DATABASE_URL` points at `localhost:5432` (as in `.env.example`):

```bash
uv sync --locked
cp .env.example .env
docker compose up -d db
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

If PostgreSQL is already running elsewhere, point `DATABASE_URL` at it instead. For a no-Docker local run, use `DATABASE_URL=sqlite+aiosqlite:///./life_sandbox.db` in `.env`.

Open `/docs`, `/health`, or `/ready`. In development, auth maps to `local-user`; set `APP_ENV=production` and `AUTH_MODE=jwt` with an appropriate secret, issuer and audience before any deployment. The JWT implementation currently supports HS256 only; configure a trusted identity integration before production.

For actual model responses, set `LLM_PROVIDER=openrouter` (or `nebius`) in `.env`, and provide that provider's API key and model. `LLM_PROVIDER=mock` is only a credential-free API demo and does not reason about prompts. Restart Uvicorn after changing `.env`.

Optional hosted long-term memory uses Mem0 Platform. Set `MEM0_API_KEY` in `.env`; the chat UI then offers a per-exchange opt-in. Opted-in messages are sent to Mem0 for memory search and the completed exchange is saved for future recall. See [RAG and memory](docs/rag-and-memory.md) for data handling details.

The Memory & tasks panel manages explicitly approved local memories, projects, tasks, reminders and pending action proposals. Local memory retrieval is available across conversations. Configure local retention and hosted-memory permission through `/api/v1/memory-policy`; hosted Mem0 use requires that permission in addition to the per-message opt-in. For durable reminders, run `uv run python -m app.jobs.worker` in a separate process. Successful reminder delivery creates an in-app notification; email and push delivery are not configured.

Optional Browser Use research runs in a local headless Chromium browser. Install the extra and browser with `uv sync --locked --extra browser` and `uv run browser-use install`, select a real Nebius or OpenRouter model, and set `BROWSER_USE_ENABLED=true`. The chat UI then offers per-message browser opt-in. See [providers](docs/providers.md) for details.

Run checks with `uv run ruff check .`, `uv run pyright`, `uv run pytest`. Docker local PostgreSQL: `docker compose up --build` after creating `.env`.

## API

See [docs/api.md](docs/api.md). Main capabilities include chat and SSE, conversation/memory/project/task/reminder CRUD, durable reminder jobs, approval records, simulations, research, file upload metadata, feedback, health and readiness.

## Architecture and operations

See [architecture](docs/architecture.md), [database](docs/database.md), [agents](docs/agents.md), [RAG and memory](docs/rag-and-memory.md), [providers](docs/providers.md), [evaluation](docs/evaluation.md), [security](docs/security.md), and [deployment](docs/deployment.md). Configuration inventory is in `.env.example`.

# Life Sandbox Backend

Local-first FastAPI backend for conversational decision support, with deterministic cash-flow projections, owner-scoped conversation and memory APIs, a LangGraph workflow, and replaceable provider adapters.

## Current status

This repository began empty. The implemented core runs without cloud accounts using a deterministic mock LLM and SQLite for local development. It includes Nebius/OpenRouter chat adapters, Tavily research, private Neon Object Storage presigned uploads, PostgreSQL-compatible SQLAlchemy models and an Alembic initial migration. The limitations in [docs/architecture.md](docs/architecture.md) are material: this is a working foundation, not the entire production platform envisioned by the brief.

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

Run checks with `uv run ruff check .`, `uv run pyright`, `uv run pytest`. Docker local PostgreSQL: `docker compose up --build` after creating `.env`.

## API

See [docs/api.md](docs/api.md). Main capabilities: chat and SSE, conversation CRUD/history, explicit-consent memory CRUD, simulations, research, file upload URL/metadata, feedback, health and readiness.

## Architecture and operations

See [architecture](docs/architecture.md), [database](docs/database.md), [agents](docs/agents.md), [RAG and memory](docs/rag-and-memory.md), [providers](docs/providers.md), [evaluation](docs/evaluation.md), [security](docs/security.md), and [deployment](docs/deployment.md). Configuration inventory is in `.env.example`.

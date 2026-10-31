#!/bin/sh
# Render starts this inside the production image. Keep migrations before the API
# so the deployed application never serves against an older schema.
set -eu

.venv/bin/alembic upgrade head
exec .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-10000}"

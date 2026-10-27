#!/usr/bin/env bash
# Deploy the API, database migration job, and one-shot background worker to Cloud Run.
# Prerequisites and secret creation are documented in docs/deployment.md.
set -euo pipefail

: "${GOOGLE_CLOUD_PROJECT:?Set GOOGLE_CLOUD_PROJECT to the target Google Cloud project.}"
: "${FRONTEND_ORIGIN:?Set FRONTEND_ORIGIN, e.g. https://life-sandbox.pages.dev.}"

REGION="${GOOGLE_CLOUD_REGION:-us-central1}"
REPOSITORY="${ARTIFACT_REPOSITORY:-life-sandbox}"
SERVICE="${CLOUD_RUN_SERVICE:-life-sandbox-api}"
TAG="${IMAGE_TAG:-$(git rev-parse --short HEAD)}"
IMAGE="${REGION}-docker.pkg.dev/${GOOGLE_CLOUD_PROJECT}/${REPOSITORY}/life-sandbox:${TAG}"
COMMON_ENV="APP_ENV=production,AUTH_MODE=jwt,AUTH_ISSUER=life-sandbox,AUTH_AUDIENCE=life-sandbox-web,LLM_PROVIDER=nebius,NEBIUS_BASE_URL=https://api.tokenfactory.nebius.com/v1,NEBIUS_MODEL=nvidia/Nemotron-3_5-Lightning,LLM_TIMEOUT_SECONDS=75,CORS_ORIGINS=[\"${FRONTEND_ORIGIN}\"],TELEGRAM_POLLING_ENABLED=false"
SECRETS="DATABASE_URL=life-sandbox-database-url:latest,NEBIUS_API_KEY=life-sandbox-nebius-api-key:latest,AUTH_SECRET=life-sandbox-auth-secret:latest"

gcloud artifacts repositories describe "$REPOSITORY" --location "$REGION" --project "$GOOGLE_CLOUD_PROJECT" >/dev/null 2>&1 || \
  gcloud artifacts repositories create "$REPOSITORY" --repository-format=docker --location "$REGION" --project "$GOOGLE_CLOUD_PROJECT"

gcloud builds submit --tag "$IMAGE" --project "$GOOGLE_CLOUD_PROJECT"

gcloud run jobs deploy life-sandbox-migrate \
  --image "$IMAGE" --region "$REGION" --project "$GOOGLE_CLOUD_PROJECT" \
  --command .venv/bin/alembic --args upgrade,head --task-timeout 10m \
  --set-env-vars "$COMMON_ENV" --set-secrets "$SECRETS"
gcloud run jobs execute life-sandbox-migrate --region "$REGION" --project "$GOOGLE_CLOUD_PROJECT" --wait

gcloud run deploy "$SERVICE" \
  --image "$IMAGE" --region "$REGION" --project "$GOOGLE_CLOUD_PROJECT" \
  --port 8000 --cpu 1 --memory 1Gi --min-instances 0 --max-instances 2 \
  --allow-unauthenticated --set-env-vars "$COMMON_ENV" --set-secrets "$SECRETS"

gcloud run jobs deploy life-sandbox-worker \
  --image "$IMAGE" --region "$REGION" --project "$GOOGLE_CLOUD_PROJECT" \
  --command .venv/bin/python --args=-m,app.jobs.worker,--once --task-timeout 10m --max-retries 0 \
  --set-env-vars "$COMMON_ENV" --set-secrets "$SECRETS"

gcloud run services describe "$SERVICE" --region "$REGION" --project "$GOOGLE_CLOUD_PROJECT" \
  --format='value(status.url)'

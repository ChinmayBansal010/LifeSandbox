#!/usr/bin/env bash
# Deploy the API, database migration job, and one-shot background worker to Cloud Run.
# Prerequisites and secret creation are documented in docs/deployment.md.
set -euo pipefail

: "${GOOGLE_CLOUD_PROJECT:?Set GOOGLE_CLOUD_PROJECT to the target Google Cloud project.}"
: "${FRONTEND_ORIGIN:?Set FRONTEND_ORIGIN, e.g. https://life-sandbox.pages.dev.}"
: "${GOOGLE_OAUTH_CLIENT_ID:?Set GOOGLE_OAUTH_CLIENT_ID to the Google web OAuth client ID.}"

REGION="${GOOGLE_CLOUD_REGION:-us-central1}"
REPOSITORY="${ARTIFACT_REPOSITORY:-life-sandbox}"
SERVICE="${CLOUD_RUN_SERVICE:-life-sandbox-api}"
TAG="${IMAGE_TAG:-$(git rev-parse --short HEAD)}"
IMAGE="${REGION}-docker.pkg.dev/${GOOGLE_CLOUD_PROJECT}/${REPOSITORY}/life-sandbox:${TAG}"
COMMON_ENV="APP_ENV=production,AUTH_MODE=jwt,AUTH_ISSUER=life-sandbox,AUTH_AUDIENCE=life-sandbox-web,LLM_PROVIDER=nebius,NEBIUS_BASE_URL=https://api.tokenfactory.nebius.com/v1,NEBIUS_MODEL=nvidia/Nemotron-3_5-Lightning,LLM_TIMEOUT_SECONDS=75,CORS_ORIGINS=[\"${FRONTEND_ORIGIN}\"],GOOGLE_OAUTH_CLIENT_ID=${GOOGLE_OAUTH_CLIENT_ID},GOOGLE_AUTH_CALLBACK_URL=${FRONTEND_ORIGIN}/api/v1/auth/google/callback,GOOGLE_AUTH_FRONTEND_URL=${FRONTEND_ORIGIN},TELEGRAM_POLLING_ENABLED=false"
SECRETS="DATABASE_URL=life-sandbox-database-url:latest,NEBIUS_API_KEY=life-sandbox-nebius-api-key:latest,AUTH_SECRET=life-sandbox-auth-secret:latest,GOOGLE_OAUTH_CLIENT_SECRET=life-sandbox-google-oauth-client-secret:latest"
RUNTIME_SERVICE_ACCOUNT="${CLOUD_RUN_SERVICE_ACCOUNT:-$(gcloud projects describe "$GOOGLE_CLOUD_PROJECT" --format='value(projectNumber)')-compute@developer.gserviceaccount.com}"

gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com secretmanager.googleapis.com cloudscheduler.googleapis.com --project "$GOOGLE_CLOUD_PROJECT"

for secret in life-sandbox-database-url life-sandbox-nebius-api-key life-sandbox-auth-secret life-sandbox-google-oauth-client-secret; do
  gcloud secrets add-iam-policy-binding "$secret" --project "$GOOGLE_CLOUD_PROJECT" \
    --member "serviceAccount:${RUNTIME_SERVICE_ACCOUNT}" --role roles/secretmanager.secretAccessor >/dev/null
done

gcloud artifacts repositories describe "$REPOSITORY" --location "$REGION" --project "$GOOGLE_CLOUD_PROJECT" >/dev/null 2>&1 || \
  gcloud artifacts repositories create "$REPOSITORY" --repository-format=docker --location "$REGION" --project "$GOOGLE_CLOUD_PROJECT"

gcloud builds submit --tag "$IMAGE" --project "$GOOGLE_CLOUD_PROJECT"

gcloud run jobs deploy life-sandbox-migrate \
  --image "$IMAGE" --region "$REGION" --project "$GOOGLE_CLOUD_PROJECT" \
  --command .venv/bin/alembic --args upgrade,head --task-timeout 10m \
  --service-account "$RUNTIME_SERVICE_ACCOUNT" --set-env-vars "$COMMON_ENV" --set-secrets "$SECRETS"
gcloud run jobs execute life-sandbox-migrate --region "$REGION" --project "$GOOGLE_CLOUD_PROJECT" --wait

gcloud run deploy "$SERVICE" \
  --image "$IMAGE" --region "$REGION" --project "$GOOGLE_CLOUD_PROJECT" \
  --port 8000 --cpu 1 --memory 1Gi --min-instances 0 --max-instances 2 \
  --service-account "$RUNTIME_SERVICE_ACCOUNT" --allow-unauthenticated --set-env-vars "$COMMON_ENV" --set-secrets "$SECRETS"

gcloud run jobs deploy life-sandbox-worker \
  --image "$IMAGE" --region "$REGION" --project "$GOOGLE_CLOUD_PROJECT" \
  --command .venv/bin/python --args=-m,app.jobs.worker,--once --task-timeout 10m --max-retries 0 \
  --service-account "$RUNTIME_SERVICE_ACCOUNT" --set-env-vars "$COMMON_ENV" --set-secrets "$SECRETS"

gcloud run services describe "$SERVICE" --region "$REGION" --project "$GOOGLE_CLOUD_PROJECT" \
  --format='value(status.url)'

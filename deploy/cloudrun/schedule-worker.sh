#!/usr/bin/env bash
# Configure the Cloud Scheduler trigger after deploy.sh has created the worker job.
set -euo pipefail

: "${GOOGLE_CLOUD_PROJECT:?Set GOOGLE_CLOUD_PROJECT to the target Google Cloud project.}"

REGION="${GOOGLE_CLOUD_REGION:-us-central1}"
SCHEDULER_REGION="${SCHEDULER_REGION:-$REGION}"
JOB="${CLOUD_RUN_WORKER_JOB:-life-sandbox-worker}"
SCHEDULE="${WORKER_SCHEDULE:-* * * * *}"
SCHEDULER_JOB="${CLOUD_SCHEDULER_JOB:-life-sandbox-worker-every-minute}"
PROJECT_NUMBER="$(gcloud projects describe "$GOOGLE_CLOUD_PROJECT" --format='value(projectNumber)')"
INVOKER="${WORKER_INVOKER_SERVICE_ACCOUNT:-${PROJECT_NUMBER}-compute@developer.gserviceaccount.com}"
URI="https://run.googleapis.com/v2/projects/${GOOGLE_CLOUD_PROJECT}/locations/${REGION}/jobs/${JOB}:run"

gcloud run jobs add-iam-policy-binding "$JOB" \
  --region "$REGION" --project "$GOOGLE_CLOUD_PROJECT" \
  --member "serviceAccount:${INVOKER}" --role roles/run.invoker

if gcloud scheduler jobs describe "$SCHEDULER_JOB" --location "$SCHEDULER_REGION" --project "$GOOGLE_CLOUD_PROJECT" >/dev/null 2>&1; then
  gcloud scheduler jobs update http "$SCHEDULER_JOB" \
    --location "$SCHEDULER_REGION" --project "$GOOGLE_CLOUD_PROJECT" \
    --schedule "$SCHEDULE" --uri "$URI" --http-method POST \
    --oauth-service-account-email "$INVOKER"
else
  gcloud scheduler jobs create http "$SCHEDULER_JOB" \
    --location "$SCHEDULER_REGION" --project "$GOOGLE_CLOUD_PROJECT" \
    --schedule "$SCHEDULE" --uri "$URI" --http-method POST \
    --oauth-service-account-email "$INVOKER"
fi

#!/usr/bin/env bash
set -euo pipefail

REGION="${REGION:-us-central1}"
SERVICE="${SERVICE:-wan-video-studio}"
SECRET="${SECRET:-wan-worker-token}"
T2V_SPACE="${T2V_SPACE:-RicasMaravilla/wan-video-studio-t2v}"
I2V_SPACE="${I2V_SPACE:-RicasMaravilla/wan-video-studio-i2v}"
PROJECT_ID="$(gcloud config get-value project 2>/dev/null)"

if [[ -z "$PROJECT_ID" || "$PROJECT_ID" == "(unset)" ]]; then
  echo "No hay un proyecto activo en gcloud. Ejecuta: gcloud config set project TU_PROJECT_ID"
  exit 1
fi

echo "Proyecto: $PROJECT_ID"
echo "Región: $REGION"

gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com

if ! gcloud secrets describe "$SECRET" >/dev/null 2>&1; then
  echo "Creando secreto $SECRET."
  read -rsp "Pega el mismo WORKER_TOKEN que guardaste en GitHub: " WORKER_TOKEN
  echo
  printf '%s' "$WORKER_TOKEN" | gcloud secrets create "$SECRET" --data-file=-
  unset WORKER_TOKEN
else
  echo "El secreto $SECRET ya existe. Se conservará su versión actual."
fi

PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"
RUNTIME_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

gcloud secrets add-iam-policy-binding "$SECRET" \
  --member="serviceAccount:${RUNTIME_SA}" \
  --role="roles/secretmanager.secretAccessor" >/dev/null

gcloud run deploy "$SERVICE" \
  --source . \
  --region "$REGION" \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 2 \
  --timeout 900 \
  --set-env-vars "WORKER_MODE=gradio,HF_SPACE_T2V=${T2V_SPACE},HF_SPACE_I2V=${I2V_SPACE}" \
  --set-secrets "WORKER_TOKEN=${SECRET}:latest"

echo
echo "Despliegue terminado. URL:"
gcloud run services describe "$SERVICE" --region "$REGION" --format='value(status.url)'

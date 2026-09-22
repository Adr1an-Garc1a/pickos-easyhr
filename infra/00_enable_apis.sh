#!/usr/bin/env bash
# Habilita todas las APIs de GCP necesarias para Easy HR (Pick'Os).
# Uso: source variables.env && bash 00_enable_apis.sh
set -euo pipefail

echo ">> Configurando proyecto activo: ${PROJECT_ID}"
gcloud config set project "${PROJECT_ID}"

echo ">> Habilitando APIs..."
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  sqladmin.googleapis.com \
  secretmanager.googleapis.com \
  compute.googleapis.com \
  vpcaccess.googleapis.com \
  servicenetworking.googleapis.com \
  storage.googleapis.com \
  aiplatform.googleapis.com \
  iam.googleapis.com \
  iamcredentials.googleapis.com \
  cloudresourcemanager.googleapis.com \
  logging.googleapis.com \
  monitoring.googleapis.com \
  --project="${PROJECT_ID}"

echo ">> APIs habilitadas correctamente."

#!/usr/bin/env bash
# Construye y sube las 5 imágenes Docker a Artifact Registry usando Cloud
# Build (sin necesidad de Docker local en Cloud Shell).
set -euo pipefail

AR_HOST="${REGION}-docker.pkg.dev"
REPO="${AR_HOST}/${PROJECT_ID}/${AR_REPO_NAME}"

build () {
  local dir="$1"; local image="$2"
  echo ">> Construyendo ${image} desde ${dir} ..."
  gcloud builds submit "${dir}" \
    --project="${PROJECT_ID}" \
    --tag="${REPO}/${image}:latest"
}

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

build "${ROOT_DIR}/services/employee-api"   "employee-api"
build "${ROOT_DIR}/services/birthday-agent" "birthday-agent"
build "${ROOT_DIR}/services/vacation-agent" "vacation-agent"
build "${ROOT_DIR}/services/jobdesc-agent"  "jobdesc-agent"
build "${ROOT_DIR}/services/agent-master"   "agent-master"
build "${ROOT_DIR}/frontend"                "frontend"

echo ">> Todas las imágenes están en ${REPO}"

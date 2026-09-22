#!/usr/bin/env bash
# Habilita todas las APIs de GCP necesarias para Easy HR (Pick'Os) y borra la
# VPC "default" del proyecto (no se usa; este proyecto crea su propia VPC
# dedicada en 01_network.sh, y la "default" solo añade superficie de ataque
# innecesaria con sus firewalls abiertos).
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

echo ">> Revisando si existe la VPC 'default' para borrarla..."
if gcloud compute networks describe default --project="${PROJECT_ID}" >/dev/null 2>&1; then
  echo ">> Borrando reglas de firewall de la VPC 'default'..."
  for fw in $(gcloud compute firewall-rules list --project="${PROJECT_ID}" \
                --filter="network:default" --format="value(name)"); do
    echo "   - ${fw}"
    gcloud compute firewall-rules delete "${fw}" --project="${PROJECT_ID}" --quiet
  done

  echo ">> Borrando rutas personalizadas (si las hay) de la VPC 'default'..."
  for route in $(gcloud compute routes list --project="${PROJECT_ID}" \
                   --filter="network:default AND -name:default-route" --format="value(name)"); do
    gcloud compute routes delete "${route}" --project="${PROJECT_ID}" --quiet || true
  done

  echo ">> Borrando la VPC 'default' (esto elimina sus subredes automáticas)..."
  gcloud compute networks delete default --project="${PROJECT_ID}" --quiet
  echo ">> VPC 'default' eliminada."
else
  echo ">> La VPC 'default' ya no existe en este proyecto. Nada que hacer."
fi

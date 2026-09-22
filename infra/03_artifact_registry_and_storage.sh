#!/usr/bin/env bash
# Crea el repositorio de Artifact Registry (imágenes Docker) y los buckets de
# Cloud Storage. Todos los buckets se crean PRIVADOS (sin acceso público,
# uniform bucket-level access, sin allUsers/allAuthenticatedUsers).
set -euo pipefail

echo ">> Creando repositorio de Artifact Registry ${AR_REPO_NAME}..."
gcloud artifacts repositories create "${AR_REPO_NAME}" \
  --project="${PROJECT_ID}" \
  --repository-format="${AR_FORMAT}" \
  --location="${REGION}" \
  --description="Imagenes Docker de Pick'Os Easy HR"

echo ">> Creando bucket privado para las tarjetas de cumpleaños generadas..."
gcloud storage buckets create "gs://${BUCKET_CARDS}" \
  --project="${PROJECT_ID}" \
  --location="${REGION}" \
  --uniform-bucket-level-access \
  --public-access-prevention

echo ">> Regla de ciclo de vida: borrar tarjetas generadas después de 30 días (control de costo)."
cat > /tmp/lifecycle-cards.json << 'JSON'
{"rule": [{"action": {"type": "Delete"}, "condition": {"age": 30}}]}
JSON
gcloud storage buckets update "gs://${BUCKET_CARDS}" --lifecycle-file=/tmp/lifecycle-cards.json

echo ">> Creando bucket privado para los PDFs de referencia de puestos (Job Description Agent)..."
gcloud storage buckets create "gs://${BUCKET_JOBDESC_REFS}" \
  --project="${PROJECT_ID}" \
  --location="${REGION}" \
  --uniform-bucket-level-access \
  --public-access-prevention

echo ">> Listo. Sube tus PDFs de descripciones de puesto actuales con, por ejemplo:"
echo "   gcloud storage cp ./mis_puestos/*.pdf gs://${BUCKET_JOBDESC_REFS}/"

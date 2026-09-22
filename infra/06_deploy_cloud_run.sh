#!/usr/bin/env bash
# Despliega los 6 servicios a Cloud Run y conecta todo (VPC connector, Cloud
# SQL, secretos, URLs internas entre servicios, IAM de invocación).
#
# Regla de exposición pública:
#   - SOLO el frontend permite acceso sin autenticación (--allow-unauthenticated).
#   - TODOS los demás servicios (employee-api, agent-master, los 3 subagentes)
#     quedan privados (--no-allow-unauthenticated) y solo pueden ser invocados
#     por las cuentas de servicio autorizadas explícitamente más abajo.
#
# Costo: min-instances=0 en todos (escalan a cero cuando nadie los usa),
# CPU/memoria mínimas razonables para un ambiente de prueba.
set -euo pipefail

AR_HOST="${REGION}-docker.pkg.dev"
REPO="${AR_HOST}/${PROJECT_ID}/${AR_REPO_NAME}"
sa_email () { echo "$1@${PROJECT_ID}.iam.gserviceaccount.com"; }

# ---------------------------------------------------------------------------
# 1) employee-api — el único servicio con acceso a Cloud SQL
# ---------------------------------------------------------------------------
echo ">> Desplegando ${CR_EMPLOYEE_API}..."
gcloud run deploy "${CR_EMPLOYEE_API}" \
  --project="${PROJECT_ID}" --region="${REGION}" \
  --image="${REPO}/employee-api:latest" \
  --service-account="$(sa_email ${SA_EMPLOYEE_API})" \
  --vpc-connector="${VPC_CONNECTOR_NAME}" --vpc-egress=private-ranges-only \
  --add-cloudsql-instances="${PROJECT_ID}:${REGION}:${SQL_INSTANCE_NAME}" \
  --set-env-vars="DB_NAME=${DB_NAME},DB_USER=${DB_APP_USER},INSTANCE_CONNECTION_NAME=${PROJECT_ID}:${REGION}:${SQL_INSTANCE_NAME}" \
  --set-secrets="DB_PASSWORD=${SECRET_DB_PASSWORD}:latest" \
  --no-allow-unauthenticated \
  --min-instances=0 --max-instances=2 --cpu=1 --memory=512Mi --concurrency=20 \
  --quiet

EMPLOYEE_API_URL="$(gcloud run services describe "${CR_EMPLOYEE_API}" \
  --project="${PROJECT_ID}" --region="${REGION}" --format='value(status.url)')"
echo "   URL interna: ${EMPLOYEE_API_URL}"

# ---------------------------------------------------------------------------
# 2) Subagentes — cada uno llama a employee-api con ID tokens, ninguno toca SQL
# ---------------------------------------------------------------------------
echo ">> Desplegando ${CR_BIRTHDAY}..."
gcloud run deploy "${CR_BIRTHDAY}" \
  --project="${PROJECT_ID}" --region="${REGION}" \
  --image="${REPO}/birthday-agent:latest" \
  --service-account="$(sa_email ${SA_BIRTHDAY})" \
  --set-env-vars="EMPLOYEE_API_URL=${EMPLOYEE_API_URL},BUCKET_CARDS=${BUCKET_CARDS},GOOGLE_GENAI_USE_VERTEXAI=${GOOGLE_GENAI_USE_VERTEXAI},GOOGLE_CLOUD_PROJECT=${PROJECT_ID},GOOGLE_CLOUD_LOCATION=${REGION},GEMINI_MODEL=${GEMINI_MODEL}" \
  --no-allow-unauthenticated \
  --min-instances=0 --max-instances=2 --cpu=1 --memory=1Gi --concurrency=5 \
  --quiet
BIRTHDAY_URL="$(gcloud run services describe "${CR_BIRTHDAY}" --project="${PROJECT_ID}" --region="${REGION}" --format='value(status.url)')"

echo ">> Desplegando ${CR_VACATION}..."
gcloud run deploy "${CR_VACATION}" \
  --project="${PROJECT_ID}" --region="${REGION}" \
  --image="${REPO}/vacation-agent:latest" \
  --service-account="$(sa_email ${SA_VACATION})" \
  --set-env-vars="EMPLOYEE_API_URL=${EMPLOYEE_API_URL},GOOGLE_GENAI_USE_VERTEXAI=${GOOGLE_GENAI_USE_VERTEXAI},GOOGLE_CLOUD_PROJECT=${PROJECT_ID},GOOGLE_CLOUD_LOCATION=${REGION},GEMINI_MODEL=${GEMINI_MODEL}" \
  --no-allow-unauthenticated \
  --min-instances=0 --max-instances=2 --cpu=1 --memory=512Mi --concurrency=10 \
  --quiet
VACATION_URL="$(gcloud run services describe "${CR_VACATION}" --project="${PROJECT_ID}" --region="${REGION}" --format='value(status.url)')"

echo ">> Desplegando ${CR_JOBDESC}..."
gcloud run deploy "${CR_JOBDESC}" \
  --project="${PROJECT_ID}" --region="${REGION}" \
  --image="${REPO}/jobdesc-agent:latest" \
  --service-account="$(sa_email ${SA_JOBDESC})" \
  --set-env-vars="EMPLOYEE_API_URL=${EMPLOYEE_API_URL},BUCKET_JOBDESC_REFS=${BUCKET_JOBDESC_REFS},GOOGLE_GENAI_USE_VERTEXAI=${GOOGLE_GENAI_USE_VERTEXAI},GOOGLE_CLOUD_PROJECT=${PROJECT_ID},GOOGLE_CLOUD_LOCATION=${REGION},GEMINI_MODEL=${GEMINI_MODEL}" \
  --no-allow-unauthenticated \
  --min-instances=0 --max-instances=2 --cpu=1 --memory=1Gi --concurrency=5 \
  --quiet
JOBDESC_URL="$(gcloud run services describe "${CR_JOBDESC}" --project="${PROJECT_ID}" --region="${REGION}" --format='value(status.url)')"

# ---------------------------------------------------------------------------
# 3) agent-master — coordinador ADK, orquesta a los 3 subagentes
# ---------------------------------------------------------------------------
echo ">> Desplegando ${CR_AGENT_MASTER}..."
gcloud run deploy "${CR_AGENT_MASTER}" \
  --project="${PROJECT_ID}" --region="${REGION}" \
  --image="${REPO}/agent-master:latest" \
  --service-account="$(sa_email ${SA_AGENT_MASTER})" \
  --set-env-vars="BIRTHDAY_AGENT_URL=${BIRTHDAY_URL},VACATION_AGENT_URL=${VACATION_URL},JOBDESC_AGENT_URL=${JOBDESC_URL},GOOGLE_GENAI_USE_VERTEXAI=${GOOGLE_GENAI_USE_VERTEXAI},GOOGLE_CLOUD_PROJECT=${PROJECT_ID},GOOGLE_CLOUD_LOCATION=${REGION},GEMINI_MODEL=${GEMINI_MODEL}" \
  --no-allow-unauthenticated \
  --min-instances=0 --max-instances=3 --cpu=1 --memory=1Gi --concurrency=10 \
  --quiet
AGENT_MASTER_URL="$(gcloud run services describe "${CR_AGENT_MASTER}" --project="${PROJECT_ID}" --region="${REGION}" --format='value(status.url)')"

# ---------------------------------------------------------------------------
# 4) frontend — único servicio público
# ---------------------------------------------------------------------------
echo ">> Desplegando ${CR_FRONTEND} (público)..."
gcloud run deploy "${CR_FRONTEND}" \
  --project="${PROJECT_ID}" --region="${REGION}" \
  --image="${REPO}/frontend:latest" \
  --service-account="$(sa_email ${SA_FRONTEND})" \
  --set-env-vars="AGENT_MASTER_URL=${AGENT_MASTER_URL},EMPLOYEE_API_URL=${EMPLOYEE_API_URL},BIRTHDAY_AGENT_URL=${BIRTHDAY_URL}" \
  --allow-unauthenticated \
  --min-instances=0 --max-instances=3 --cpu=1 --memory=512Mi --concurrency=40 \
  --quiet

FRONTEND_URL="$(gcloud run services describe "${CR_FRONTEND}" --project="${PROJECT_ID}" --region="${REGION}" --format='value(status.url)')"

# ---------------------------------------------------------------------------
# 5) IAM: quién puede invocar a quién (Cloud Run "run.invoker" es la única
#    puerta; nada queda abierto por defecto)
# ---------------------------------------------------------------------------
echo ">> Autorizando invocaciones servicio-a-servicio..."
allow_invoke () {
  local target_service="$1"; local caller_sa="$2"
  gcloud run services add-iam-policy-binding "${target_service}" \
    --project="${PROJECT_ID}" --region="${REGION}" \
    --member="serviceAccount:$(sa_email "${caller_sa}")" \
    --role="roles/run.invoker"
}
allow_invoke "${CR_BIRTHDAY}"     "${SA_AGENT_MASTER}"
allow_invoke "${CR_VACATION}"     "${SA_AGENT_MASTER}"
allow_invoke "${CR_JOBDESC}"      "${SA_AGENT_MASTER}"
allow_invoke "${CR_EMPLOYEE_API}" "${SA_AGENT_MASTER}"
allow_invoke "${CR_EMPLOYEE_API}" "${SA_BIRTHDAY}"
allow_invoke "${CR_EMPLOYEE_API}" "${SA_VACATION}"
allow_invoke "${CR_EMPLOYEE_API}" "${SA_JOBDESC}"
allow_invoke "${CR_EMPLOYEE_API}" "${SA_FRONTEND}"
allow_invoke "${CR_AGENT_MASTER}" "${SA_FRONTEND}"
allow_invoke "${CR_BIRTHDAY}"     "${SA_FRONTEND}"   # para descargar las tarjetas generadas (/files)

echo ""
echo "================================================================"
echo " Easy HR desplegado. URL pública del frontend:"
echo "   ${FRONTEND_URL}"
echo "================================================================"

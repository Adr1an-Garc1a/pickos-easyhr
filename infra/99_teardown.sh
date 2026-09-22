#!/usr/bin/env bash
# =============================================================================
# Pick'Os · Easy HR — TEARDOWN COMPLETO
# Borra TODOS los recursos creados por los scripts 00-07 dentro del MISMO
# proyecto (no borra el proyecto en sí). Úsalo cuando quieras empezar desde
# cero sin cambiar de Project ID.
#
# Uso:
#   cd infra
#   source variables.local.env
#   bash 99_teardown.sh
#
# Te pedirá escribir el PROJECT_ID como confirmación antes de borrar nada.
# =============================================================================
set -uo pipefail   # (sin -e: queremos seguir aunque algún recurso ya no exista)

echo "Esto va a BORRAR PERMANENTEMENTE todos los recursos de Easy HR en:"
echo "  Proyecto: ${PROJECT_ID}"
read -rp "Escribe el PROJECT_ID exacto para confirmar: " CONFIRM
if [[ "${CONFIRM}" != "${PROJECT_ID}" ]]; then
  echo "No coincide. Abortando, no se borró nada."
  exit 1
fi

echo ">> 1/10 Borrando triggers de Cloud Build..."
for name in easyhr-employee-api easyhr-birthday-agent easyhr-vacation-agent easyhr-jobdesc-agent easyhr-agent-master easyhr-frontend; do
  gcloud builds triggers delete "$name" --project="${PROJECT_ID}" --region="${CONNECTION_REGION:-$REGION}" --quiet 2>/dev/null || true
  gcloud builds triggers delete "$name" --project="${PROJECT_ID}" --quiet 2>/dev/null || true
done

echo ">> 2/10 Borrando servicios de Cloud Run..."
for svc in "${CR_FRONTEND:-easyhr-frontend}" "${CR_AGENT_MASTER:-easyhr-agent-master}" "${CR_BIRTHDAY:-easyhr-birthday-agent}" "${CR_VACATION:-easyhr-vacation-agent}" "${CR_JOBDESC:-easyhr-jobdesc-agent}" "${CR_EMPLOYEE_API:-easyhr-employee-api}"; do
  gcloud run services delete "$svc" --project="${PROJECT_ID}" --region="${REGION}" --quiet 2>/dev/null || true
done

echo ">> 3/10 Borrando la instancia de Cloud SQL (puede tardar varios minutos)..."
gcloud sql instances delete "${SQL_INSTANCE_NAME:-easyhr-sql}" --project="${PROJECT_ID}" --quiet 2>/dev/null || true

echo ">> 4/10 Vaciando y borrando buckets de Cloud Storage..."
for bucket in "${BUCKET_CARDS:-}" "${BUCKET_JOBDESC_REFS:-}"; do
  [[ -z "$bucket" ]] && continue
  gcloud storage rm -r "gs://${bucket}/**" --quiet 2>/dev/null || true
  gcloud storage buckets delete "gs://${bucket}" --quiet 2>/dev/null || true
done

echo ">> 5/10 Borrando repositorio de Artifact Registry..."
gcloud artifacts repositories delete "${AR_REPO_NAME:-easyhr-repo}" --project="${PROJECT_ID}" --location="${REGION}" --quiet 2>/dev/null || true

echo ">> 6/10 Borrando secretos de Secret Manager..."
gcloud secrets delete "${SECRET_DB_PASSWORD:-easyhr-db-password}" --project="${PROJECT_ID}" --quiet 2>/dev/null || true
gcloud secrets delete "${SECRET_DB_CONN_NAME:-easyhr-db-connection-name}" --project="${PROJECT_ID}" --quiet 2>/dev/null || true

echo ">> 7/10 Borrando cuentas de servicio..."
for sa in "${SA_FRONTEND:-easyhr-frontend-sa}" "${SA_AGENT_MASTER:-easyhr-agent-master-sa}" "${SA_BIRTHDAY:-easyhr-birthday-agent-sa}" "${SA_VACATION:-easyhr-vacation-agent-sa}" "${SA_JOBDESC:-easyhr-jobdesc-agent-sa}" "${SA_EMPLOYEE_API:-easyhr-employee-api-sa}"; do
  gcloud iam service-accounts delete "${sa}@${PROJECT_ID}.iam.gserviceaccount.com" --project="${PROJECT_ID}" --quiet 2>/dev/null || true
done

echo ">> 8/10 Borrando el conector VPC Access..."
gcloud compute networks vpc-access connectors delete "${VPC_CONNECTOR_NAME:-easyhr-connector}" \
  --region="${REGION}" --project="${PROJECT_ID}" --quiet 2>/dev/null || true

echo ">> 9/10 Borrando firewall, subred y peering de Service Networking..."
gcloud compute firewall-rules delete "${NETWORK_NAME:-easyhr-vpc}-allow-internal" --project="${PROJECT_ID}" --quiet 2>/dev/null || true
gcloud compute networks subnets delete "${SUBNET_NAME:-easyhr-subnet}" --region="${REGION}" --project="${PROJECT_ID}" --quiet 2>/dev/null || true
gcloud services vpc-peerings delete --service=servicenetworking.googleapis.com --network="${NETWORK_NAME:-easyhr-vpc}" --project="${PROJECT_ID}" --quiet 2>/dev/null || true
gcloud compute addresses delete "${PSA_RANGE_NAME:-easyhr-psa-range}" --global --project="${PROJECT_ID}" --quiet 2>/dev/null || true

echo ">> 10/10 Borrando la VPC..."
gcloud compute networks delete "${NETWORK_NAME:-easyhr-vpc}" --project="${PROJECT_ID}" --quiet 2>/dev/null || true

echo ""
echo "================================================================"
echo " Teardown terminado. Revisa la consola por si algo quedó a medias"
echo " (los errores 'not found' de arriba son normales y esperados)."
echo " Cuando quieras, vuelve a correr 00_enable_apis.sh en adelante."
echo "================================================================"

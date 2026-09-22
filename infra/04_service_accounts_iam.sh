#!/usr/bin/env bash
# Crea una cuenta de servicio dedicada por microservicio (mínimo privilegio,
# nada corre con la cuenta de servicio "default de Compute") y les otorga
# solo los permisos que cada una necesita.
set -euo pipefail

create_sa () {
  local name="$1"; local display="$2"
  if gcloud iam service-accounts describe "${name}@${PROJECT_ID}.iam.gserviceaccount.com" \
      --project="${PROJECT_ID}" >/dev/null 2>&1; then
    echo "   SA ${name} ya existe"
  else
    gcloud iam service-accounts create "${name}" \
      --project="${PROJECT_ID}" --display-name="${display}"
  fi
}

echo ">> Creando cuentas de servicio..."
create_sa "${SA_FRONTEND}"      "Easy HR - Frontend"
create_sa "${SA_AGENT_MASTER}"  "Easy HR - Agent Master (coordinador ADK)"
create_sa "${SA_BIRTHDAY}"      "Easy HR - Birthday Agent"
create_sa "${SA_VACATION}"      "Easy HR - Vacation Agent"
create_sa "${SA_JOBDESC}"       "Easy HR - Job Description Agent"
create_sa "${SA_EMPLOYEE_API}"  "Easy HR - Employee CRUD API"

sa_email () { echo "$1@${PROJECT_ID}.iam.gserviceaccount.com"; }

echo ">> Permisos: Employee API necesita hablar con Cloud SQL y leer sus propios secretos."
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:$(sa_email ${SA_EMPLOYEE_API})" \
  --role="roles/cloudsql.client" --condition=None
gcloud secrets add-iam-policy-binding "${SECRET_DB_PASSWORD}" \
  --project="${PROJECT_ID}" \
  --member="serviceAccount:$(sa_email ${SA_EMPLOYEE_API})" \
  --role="roles/secretmanager.secretAccessor"
gcloud secrets add-iam-policy-binding "${SECRET_DB_CONN_NAME}" \
  --project="${PROJECT_ID}" \
  --member="serviceAccount:$(sa_email ${SA_EMPLOYEE_API})" \
  --role="roles/secretmanager.secretAccessor"

echo ">> Nota de diseño: SOLO employee-api tiene acceso a Cloud SQL / secretos de BD."
echo "   Los subagentes NUNCA tocan la base de datos directamente: le piden los"
echo "   datos a employee-api por HTTP autenticado (ID tokens de Cloud Run),"
echo "   así el radio de exposición de las credenciales de BD es mínimo."

echo ">> Permisos: Birthday Agent necesita Vertex AI + escritura en bucket de tarjetas."
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:$(sa_email ${SA_BIRTHDAY})" --role="roles/aiplatform.user" --condition=None
gcloud storage buckets add-iam-policy-binding "gs://${BUCKET_CARDS}" \
  --member="serviceAccount:$(sa_email ${SA_BIRTHDAY})" --role="roles/storage.objectAdmin"

echo ">> Permisos: Vacation Agent necesita Vertex AI (los datos del empleado los pide a employee-api)."
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:$(sa_email ${SA_VACATION})" --role="roles/aiplatform.user" --condition=None

echo ">> Permisos: Job Description Agent necesita Vertex AI + lectura del bucket de referencias."
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:$(sa_email ${SA_JOBDESC})" --role="roles/aiplatform.user" --condition=None
gcloud storage buckets add-iam-policy-binding "gs://${BUCKET_JOBDESC_REFS}" \
  --member="serviceAccount:$(sa_email ${SA_JOBDESC})" --role="roles/storage.objectViewer"

echo ">> Permisos: Agent Master (coordinador) necesita Vertex AI + invocar a los 3 subagentes (Cloud Run)."
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:$(sa_email ${SA_AGENT_MASTER})" --role="roles/aiplatform.user" --condition=None

echo ">> Permisos: Frontend necesita invocar a Agent Master (Cloud Run) y NADA MÁS (ni SQL ni buckets)."
# El binding run.invoker sobre cada servicio se hace en 08_deploy_cloud_run.sh
# una vez que los servicios ya existen (gcloud run services add-iam-policy-binding).

echo ">> Cuentas de servicio e IAM configurados."

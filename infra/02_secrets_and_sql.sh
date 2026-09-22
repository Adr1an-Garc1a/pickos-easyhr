#!/usr/bin/env bash
# Crea los secretos base en Secret Manager y la instancia de Cloud SQL
# (Postgres) con IP PRIVADA únicamente (sin IP pública, sin SSL público que
# gestionar). La contraseña del usuario de aplicación se genera de forma
# aleatoria y se guarda SOLO en Secret Manager: nunca queda en código,
# variables de entorno de texto plano en el repo, ni en logs.
set -euo pipefail

echo ">> Generando password aleatoria para el usuario de la app (no se imprime)..."
DB_APP_PASSWORD="$(openssl rand -base64 24)"

echo ">> Creando secreto ${SECRET_DB_PASSWORD} en Secret Manager..."
if gcloud secrets describe "${SECRET_DB_PASSWORD}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
  echo "   ya existe, se agrega una nueva versión"
  printf '%s' "${DB_APP_PASSWORD}" | gcloud secrets versions add "${SECRET_DB_PASSWORD}" \
    --project="${PROJECT_ID}" --data-file=-
else
  printf '%s' "${DB_APP_PASSWORD}" | gcloud secrets create "${SECRET_DB_PASSWORD}" \
    --project="${PROJECT_ID}" --replication-policy=automatic --data-file=-
fi

echo ">> Creando instancia de Cloud SQL (${SQL_INSTANCE_NAME})... esto puede tardar varios minutos."
gcloud sql instances create "${SQL_INSTANCE_NAME}" \
  --project="${PROJECT_ID}" \
  --database-version="${SQL_DB_VERSION}" \
  --tier="${SQL_TIER}" \
  --region="${REGION}" \
  --storage-size="${SQL_STORAGE_SIZE}" \
  --storage-type="${SQL_STORAGE_TYPE}" \
  --storage-auto-increase \
  --no-assign-ip \
  --network="projects/${PROJECT_ID}/global/networks/${NETWORK_NAME}" \
  --availability-type=ZONAL \
  --backup-start-time=03:00 \
  --retained-backups-count=3

echo ">> Creando base de datos ${DB_NAME}..."
gcloud sql databases create "${DB_NAME}" \
  --project="${PROJECT_ID}" \
  --instance="${SQL_INSTANCE_NAME}"

echo ">> Creando usuario de aplicación ${DB_APP_USER}..."
gcloud sql users create "${DB_APP_USER}" \
  --project="${PROJECT_ID}" \
  --instance="${SQL_INSTANCE_NAME}" \
  --password="${DB_APP_PASSWORD}"

echo ">> Guardando el connection name de la instancia en Secret Manager..."
CONN_NAME="$(gcloud sql instances describe "${SQL_INSTANCE_NAME}" \
  --project="${PROJECT_ID}" --format='value(connectionName)')"

if gcloud secrets describe "${SECRET_DB_CONN_NAME}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
  printf '%s' "${CONN_NAME}" | gcloud secrets versions add "${SECRET_DB_CONN_NAME}" \
    --project="${PROJECT_ID}" --data-file=-
else
  printf '%s' "${CONN_NAME}" | gcloud secrets create "${SECRET_DB_CONN_NAME}" \
    --project="${PROJECT_ID}" --replication-policy=automatic --data-file=-
fi

unset DB_APP_PASSWORD
echo ">> Cloud SQL + Secret Manager listos. Connection name: ${CONN_NAME}"

#!/usr/bin/env bash
# Crea un Cloud Build Trigger POR SERVICIO (6 en total), cada uno disparado
# solo cuando un push modifica archivos dentro de la carpeta de ESE servicio.
#
# Usa una conexión de GitHub de 2da generación (Developer Connect) — la que
# se crea hoy en día al usar "Cloud Build > Triggers > Conectar repositorio"
# desde la consola (ver sección 4.1 del README para el paso a paso).
# Prerrequisito: haber conectado el repositorio una sola vez desde ahí antes
# de correr este script.
set -euo pipefail

# ---------------------------------------------------------------------------
# Cada cloudbuild.yaml hace `gcloud run deploy` y
# `gcloud run services add-iam-policy-binding` por sí mismo (para que el
# CI/CD sea autosuficiente). Eso lo ejecuta la cuenta de servicio de Cloud
# Build, que en proyectos nuevos NO trae permisos de Cloud Run ni de actuar
# como otras cuentas de servicio por default. Se los damos aquí una sola vez.
# ---------------------------------------------------------------------------
PROJECT_NUMBER="$(gcloud projects describe "${PROJECT_ID}" --format='value(projectNumber)')"
CLOUDBUILD_SA="${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com"
COMPUTE_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

echo ">> Otorgando permisos a la cuenta de servicio de Cloud Build (${CLOUDBUILD_SA})..."
for role in roles/run.admin roles/iam.serviceAccountUser roles/artifactregistry.writer; do
  gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="serviceAccount:${CLOUDBUILD_SA}" --role="${role}" --condition=None --quiet
done

# Desde 2024, los triggers creados por consola pueden ejecutarse con la
# cuenta de servicio POR DEFAULT DE COMPUTE ENGINE en vez de la de Cloud
# Build (depende de qué se haya seleccionado al crear el trigger). Como no
# sabemos cuál usará cada trigger, se los damos a ambas por seguridad.
echo ">> Otorgando los mismos permisos a la cuenta de Compute Engine por si los triggers la usan (${COMPUTE_SA})..."
for role in roles/run.admin roles/iam.serviceAccountUser roles/artifactregistry.writer; do
  gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="serviceAccount:${COMPUTE_SA}" --role="${role}" --condition=None --quiet
done

# Región donde vive la CONEXIÓN (no es necesariamente la misma que REGION de
# Cloud Run/Cloud SQL). Ajusta si tu conexión está en otra región.
CONNECTION_REGION="${CONNECTION_REGION:-$REGION}"

echo ">> Buscando conexiones de GitHub en ${CONNECTION_REGION}..."
gcloud builds connections list --region="${CONNECTION_REGION}" --project="${PROJECT_ID}"

echo ""
echo "   OJO: escribe el nombre de la CONEXIÓN (columna NAME de la tabla de"
echo "   arriba, algo como 'adr-garcia-pickos-easyhr-connector') — NO tu"
echo "   usuario de GitHub ni el nombre del repositorio, eso viene después."
read -rp "Nombre exacto de tu conexión: " CONNECTION_NAME

echo ">> Buscando repositorios vinculados a la conexión '${CONNECTION_NAME}'..."
gcloud builds repositories list \
  --connection="${CONNECTION_NAME}" --region="${CONNECTION_REGION}" --project="${PROJECT_ID}"

echo ""
echo "   OJO: el nombre del repositorio normalmente incluye tu usuario de"
echo "   GitHub pegado al inicio (ej. 'Adr1an-Garc1a-pickos-easyhr'), NO es"
echo "   solo el nombre corto del repo. Copia el valor EXACTO de la columna"
echo "   NAME de la tabla de arriba, respetando mayúsculas/minúsculas."
read -rp "Nombre exacto del repositorio: " REPO_RESOURCE_NAME

REPOSITORY="projects/${PROJECT_ID}/locations/${CONNECTION_REGION}/connections/${CONNECTION_NAME}/repositories/${REPO_RESOURCE_NAME}"
echo ">> Usando repositorio: ${REPOSITORY}"

create_trigger () {
  local name="$1"; local dir="$2"
  echo ">> Creando/actualizando trigger ${name}..."
  gcloud builds triggers create github \
    --project="${PROJECT_ID}" \
    --region="${CONNECTION_REGION}" \
    --name="${name}" \
    --repository="${REPOSITORY}" \
    --branch-pattern="${GITHUB_BRANCH}" \
    --included-files="${dir}/**" \
    --build-config="${dir}/cloudbuild.yaml" \
    || echo "   (si ya existe, edítalo desde la consola o bórralo con: gcloud builds triggers delete ${name} --region=${CONNECTION_REGION} --project=${PROJECT_ID})"
}

create_trigger "easyhr-employee-api"   "services/employee-api"
create_trigger "easyhr-birthday-agent" "services/birthday-agent"
create_trigger "easyhr-vacation-agent" "services/vacation-agent"
create_trigger "easyhr-jobdesc-agent"  "services/jobdesc-agent"
create_trigger "easyhr-agent-master"   "services/agent-master"
create_trigger "easyhr-frontend"       "frontend"

echo ""
echo ">> Triggers de CI/CD listos (6 en total). Cada push a la rama que"
echo "   coincida con GITHUB_BRANCH (${GITHUB_BRANCH}) y que toque la"
echo "   carpeta de un servicio disparará el build + deploy de ESE"
echo "   servicio únicamente."

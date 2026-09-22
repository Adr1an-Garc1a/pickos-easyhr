#!/usr/bin/env bash
# Crea un Cloud Build Trigger por servicio, usando una conexión de GitHub de
# 2da generación (Developer Connect) — la que se crea hoy en día al usar
# "Cloud Build > Triggers > Conectar repositorio" desde la consola. Esas
# conexiones ya NO aceptan las flags viejas --repo-name/--repo-owner; hay que
# usar --repository apuntando al recurso completo del repo conectado.
#
# Prerrequisito: haber conectado el repositorio una sola vez desde la consola
# (Cloud Build > Repositorios de 2.ª generación > Conectar repositorio host,
# o Triggers > Crear activador > Conectar nuevo repositorio).
set -euo pipefail

# Región donde vive la CONEXIÓN (no es necesariamente la misma que REGION de
# Cloud Run/Cloud SQL). Ajusta si tu conexión está en otra región.
CONNECTION_REGION="${CONNECTION_REGION:-$REGION}"

echo ">> Buscando conexiones de GitHub en ${CONNECTION_REGION}..."
gcloud builds connections list --region="${CONNECTION_REGION}" --project="${PROJECT_ID}"

read -rp "Nombre exacto de tu conexión (columna NAME de arriba): " CONNECTION_NAME

echo ">> Buscando repositorios vinculados a la conexión '${CONNECTION_NAME}'..."
gcloud builds connections repositories list \
  --connection="${CONNECTION_NAME}" --region="${CONNECTION_REGION}" --project="${PROJECT_ID}"

read -rp "Nombre exacto del repositorio (columna REPOSITORY de arriba, ej. Adr1an-Garc1a-pickos-easyhr): " REPO_RESOURCE_NAME

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

echo ">> Triggers de CI/CD listos. Cada push a la rama que coincida con"
echo "   GITHUB_BRANCH y que toque la carpeta del servicio disparará un build"
echo "   + deploy automático de ESE servicio únicamente."

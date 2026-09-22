#!/usr/bin/env bash
# Conecta el repositorio de GitHub y crea un Cloud Build Trigger por servicio.
# Cada trigger solo se dispara cuando cambian archivos dentro de su carpeta
# (include-logs-path), construye la imagen y hace `gcloud run deploy` con la
# imagen nueva, imagen por commit (SHORT_SHA) para poder hacer rollback.
#
# Prerrequisito: conecta tu repo de GitHub una sola vez desde la consola
# (Cloud Build > Triggers > Conectar repositorio) o con:
#   gcloud builds repositories create ...  (2nd-gen connections, requiere
#   crear antes una conexión con gcloud builds connections create github ...)
# Aquí se asume que la conexión ya existe con el nombre "github-connection".
set -euo pipefail

CONNECTION_NAME="github-connection"

create_trigger () {
  local name="$1"; local dir="$2"; local image="$3"; local sa="$4"; local extra_deploy_args="${5:-}"
  echo ">> Creando/actualizando trigger ${name}..."
  gcloud builds triggers create github \
    --project="${PROJECT_ID}" \
    --name="${name}" \
    --repo-name="${GITHUB_REPO}" \
    --repo-owner="${GITHUB_OWNER}" \
    --branch-pattern="${GITHUB_BRANCH}" \
    --included-files="${dir}/**" \
    --build-config="${dir}/cloudbuild.yaml" \
    --substitutions="_IMAGE=${image},_SERVICE_ACCOUNT=$1,_REGION=${REGION},_REPO=${AR_REPO_NAME},_EXTRA_ARGS=${extra_deploy_args}" \
    || echo "   (si ya existe, edítalo desde la consola o bórralo con gcloud builds triggers delete)"
}

# Nota: cada cloudbuild.yaml (dentro de cada carpeta de servicio) construye
# la imagen, la sube a Artifact Registry y despliega a Cloud Run usando los
# nombres de servicio/variables definidos en variables.env vía substitutions.

create_trigger "easyhr-employee-api"   "services/employee-api"   "employee-api"   "${SA_EMPLOYEE_API}"
create_trigger "easyhr-birthday-agent" "services/birthday-agent" "birthday-agent" "${SA_BIRTHDAY}"
create_trigger "easyhr-vacation-agent" "services/vacation-agent" "vacation-agent" "${SA_VACATION}"
create_trigger "easyhr-jobdesc-agent"  "services/jobdesc-agent"  "jobdesc-agent"  "${SA_JOBDESC}"
create_trigger "easyhr-agent-master"   "services/agent-master"   "agent-master"   "${SA_AGENT_MASTER}"
create_trigger "easyhr-frontend"       "frontend"                "frontend"       "${SA_FRONTEND}"

echo ">> Triggers de CI/CD listos. Cada push a la rama que coincida con"
echo "   GITHUB_BRANCH y que toque la carpeta del servicio disparará un build"
echo "   + deploy automático de ESE servicio únicamente."

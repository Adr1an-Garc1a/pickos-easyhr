#!/usr/bin/env bash
# Crea la VPC dedicada, subred, rango privado para Cloud SQL (Private Services
# Access) y el conector de Acceso VPC sin servidor para que Cloud Run pueda
# hablar con Cloud SQL por IP privada (sin exponer nada públicamente).
#
# NOTA sobre "Shared VPC": Shared VPC es un recurso a nivel de ORGANIZACIÓN
# (un proyecto "host" comparte red con proyectos "service"). Para un ambiente
# de prueba de un solo proyecto no aporta valor y sí añade costo/latencia de
# administración, así que aquí se crea una VPC normal dentro del mismo
# proyecto. Si más adelante separas Dev/Staging/Prod en distintos proyectos,
# puedes convertir este proyecto en host con:
#   gcloud compute shared-vpc enable "${PROJECT_ID}"
#   gcloud compute shared-vpc associated-projects add SERVICE_PROJECT_ID \
#       --host-project="${PROJECT_ID}"
# y los proyectos "service" usarían esta misma VPC/subred vía --network con
# el formato projects/HOST_PROJECT/global/networks/NETWORK.
set -euo pipefail

echo ">> Creando VPC ${NETWORK_NAME} (modo custom, sin subredes automáticas)..."
gcloud compute networks create "${NETWORK_NAME}" \
  --project="${PROJECT_ID}" \
  --subnet-mode=custom \
  --bgp-routing-mode=regional

echo ">> Creando subred ${SUBNET_NAME} en ${REGION}..."
gcloud compute networks subnets create "${SUBNET_NAME}" \
  --project="${PROJECT_ID}" \
  --network="${NETWORK_NAME}" \
  --region="${REGION}" \
  --range="${SUBNET_RANGE}" \
  --enable-private-ip-google-access

echo ">> Firewall: permitir tráfico interno dentro de la VPC..."
gcloud compute firewall-rules create "${NETWORK_NAME}-allow-internal" \
  --project="${PROJECT_ID}" \
  --network="${NETWORK_NAME}" \
  --direction=INGRESS \
  --action=ALLOW \
  --rules=tcp,udp,icmp \
  --source-ranges="${SUBNET_RANGE},${VPC_CONNECTOR_RANGE}"

echo ">> Reservando rango IP privado para Private Service Access (Cloud SQL)..."
gcloud compute addresses create "${PSA_RANGE_NAME}" \
  --project="${PROJECT_ID}" \
  --global \
  --purpose=VPC_PEERING \
  --addresses="$(echo "${PSA_RANGE}" | cut -d/ -f1)" \
  --prefix-length="$(echo "${PSA_RANGE}" | cut -d/ -f2)" \
  --network="${NETWORK_NAME}"

echo ">> Creando el peering de Service Networking (requerido por Cloud SQL con IP privada)..."
gcloud services vpc-peerings connect \
  --project="${PROJECT_ID}" \
  --service=servicenetworking.googleapis.com \
  --ranges="${PSA_RANGE_NAME}" \
  --network="${NETWORK_NAME}"

echo ">> Creando el conector VPC Access para Cloud Run (tamaño mínimo por costo)..."
# Nota: se usa e2-micro y NO f1-micro. f1-micro ha tenido fallas
# intermitentes de Google ("VPC Access connector failed to get healthy")
# en varios proyectos nuevos; e2-micro cuesta prácticamente lo mismo y no
# tiene ese problema.
gcloud compute networks vpc-access connectors create "${VPC_CONNECTOR_NAME}" \
  --project="${PROJECT_ID}" \
  --region="${REGION}" \
  --network="${NETWORK_NAME}" \
  --range="${VPC_CONNECTOR_RANGE}" \
  --machine-type=e2-micro \
  --min-instances=2 \
  --max-instances=3

echo ">> Red lista."

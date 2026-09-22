# Pick'Os · Easy HR

Sistema de Recursos Humanos multiagente para **Pick'Os**, empresa mexicana de
TI / centros de datos que participa en licitaciones públicas. Construido
sobre **Google Cloud (Cloud Run, Cloud SQL, Secret Manager, Artifact
Registry, Cloud Build, Cloud Storage)** y el **Agent Development Kit (ADK)**
de Google para el sistema multiagente.

## 1. Arquitectura

```
Usuario (navegador)
      │  HTTPS pública
      ▼
┌───────────────┐  privado, run.invoker   ┌──────────────────┐
│   frontend    │ ───────────────────────▶│   agent-master   │  (Coordinador ADK)
│ (Cloud Run,   │                         │   (Cloud Run,     │
│  público)     │                         │    privado)       │
└──────┬────────┘                         └───┬───────┬───────┘
       │ run.invoker                          │       │        run.invoker
       ▼                                      ▼       ▼
┌───────────────┐   ┌───────────────┐ ┌───────────────┐ ┌───────────────┐
│ employee-api  │◀──│birthday-agent │ │vacation-agent │ │ jobdesc-agent │
│ (Cloud Run,   │   │ (Cloud Run,   │ │ (Cloud Run,   │ │ (Cloud Run,   │
│  privado)     │   │  privado)     │ │  privado)     │ │  privado)     │
└──────┬────────┘   └───────┬───────┘ └───────────────┘ └───────┬───────┘
       │ VPC connector              │ GCS (tarjetas)             │ GCS (PDFs de referencia)
       ▼                            ▼                            
┌───────────────┐           ┌───────────────┐
│  Cloud SQL    │           │ Cloud Storage │
│  (Postgres,   │           │  (privado)    │
│   IP privada) │           └───────────────┘
└───────────────┘
```

**Regla de oro de seguridad:** `employee-api` es el **único** servicio con
acceso a Cloud SQL / secretos de base de datos. Todos los subagentes y el
frontend le piden los datos por HTTP autenticado (ID tokens de Cloud Run),
nunca tocan la base de datos directamente. Todos los servicios son
`--no-allow-unauthenticated` **excepto el frontend**, que es el único punto
de entrada público.

## 2. Decisiones y supuestos importantes (léelo antes de usar el sistema)

1. **Campo `fecha_nacimiento`**: no estaba en la lista de campos que diste,
   pero es indispensable para que el Birthday Agent funcione. Es el único
   campo agregado fuera de lo solicitado.
2. **Vacaciones**: el cálculo usa la tabla de "vacaciones dignas" del Art. 76
   LFT (vigente desde 2023) y el plazo de disfrute de 6 meses del Art. 81
   LFT. El sistema **no lleva historial de días ya tomados** (no se pidió esa
   tabla), así que el cálculo asume que el periodo vigente completo sigue
   disponible. Esto no sustituye asesoría legal formal.
3. **Estado de conversación multi-turno** (importante para el Job
   Description Agent, que hace preguntas de seguimiento): en vez de depender
   de que cada servicio de Cloud Run recuerde la sesión entre llamadas HTTP
   (frágil con `min-instances=0` y múltiples réplicas), el **frontend
   mantiene el historial de la conversación en el navegador** y lo reenvía
   completo en cada turno. Es la solución más simple y barata para un
   ambiente de prueba. Si más adelante se necesita persistencia real de
   sesiones entre instancias, la evolución natural es un `SessionService`
   respaldado por Firestore o Vertex AI Sessions.
4. **Referencias de puestos (Job Description Agent)**: se implementa como
   búsqueda simple por nombre de archivo sobre los PDFs subidos al bucket
   `BUCKET_JOBDESC_REFS`, no una búsqueda semántica/vectorial (eso añadiría
   costo de infraestructura innecesario para una prueba).
5. **Costos**: Cloud SQL en tier compartido (`db-f1-micro`), almacenamiento
   HDD, todos los Cloud Run con `min-instances=0` (escalan a cero), conector
   VPC Access de tamaño mínimo. Esto implica *cold starts* ocasionales; es la
   compensación esperada por minimizar costo en un ambiente de prueba.
6. **Shared VPC**: no se implementa como tal porque es un concepto de
   *organización* (proyecto host + proyectos service) que no aporta nada en
   un solo proyecto de prueba. `infra/01_network.sh` explica cómo migrar a
   Shared VPC real si más adelante separas Dev/Staging/Prod en proyectos
   distintos.

## 3. Estructura del repositorio

```
infra/                  # Scripts .sh para correr en Cloud Shell (00 → 07, en orden)
db/                      # schema.sql + seed_employees.py (50 empleados dummy)
services/
  employee-api/          # CRUD Flask + Cloud SQL (único servicio con acceso a la BD)
  birthday-agent/         # Agente ADK: cumpleaños + generación de tarjetas PDF/JPG
  vacation-agent/          # Agente ADK: cálculo de vacaciones (LFT México)
  jobdesc-agent/            # Agente ADK: redacción de Job Descriptions
  agent-master/              # Coordinador ADK (decide a qué subagente delegar)
frontend/                # Flask + HTML/CSS/JS, único servicio público
cicd/                    # (reservado para configuración adicional de CI/CD)
```

Cada carpeta de servicio tiene su propio `Dockerfile`, `requirements.txt` y
`cloudbuild.yaml` — son unidades de despliegue independientes.

## 4. Cómo desplegar desde cero (Cloud Shell)

```bash
# 0) Clona este repo dentro de Cloud Shell y entra a la carpeta infra
cd pickos-easyhr/infra
cp variables.env variables.local.env   # edítalo con tu PROJECT_ID real, etc.
source variables.local.env

# 1) Infraestructura base (en este orden)
bash 00_enable_apis.sh
bash 01_network.sh
bash 02_secrets_and_sql.sh
bash 03_artifact_registry_and_storage.sh
bash 04_service_accounts_iam.sh

# 2) (Opcional pero recomendado) sube tus PDFs de descripciones de puesto
#    actuales para que el Job Description Agent tenga referencia:
gcloud storage cp ./mis_puestos/*.pdf gs://${BUCKET_JOBDESC_REFS}/

# 3) Construye las imágenes y despliega los 6 servicios
bash 05_build_images.sh
bash 06_deploy_cloud_run.sh   # imprime la URL pública del frontend al final

# 4) Carga de datos: aplica el esquema y los 50 empleados dummy
#
#    IMPORTANTE: la instancia de Cloud SQL solo tiene IP PRIVADA, y Cloud
#    Shell NO está dentro de tu VPC, así que no puede conectarse directo
#    (ni el conector de Python, ni `gcloud sql connect`, ni psql). La forma
#    más simple es usar Cloud SQL Studio (el editor SQL integrado en la
#    consola, que corre del lado de Google y no requiere ruta de red):
#
#    1. Ve a Cloud SQL > easyhr-sql > Cloud SQL Studio (menú izquierdo).
#    2. Inicia sesión con: base de datos "easyhr", usuario "easyhr_app" y
#       la contraseña que está en Secret Manager (secreto "easyhr-db-password").
#    3. Abre una pestaña nueva de consulta, pega TODO el contenido de
#       db/schema.sql y dale "Run" (esto crea las tablas).
#    4. Abre otra pestaña, pega TODO el contenido de db/seed_data.sql
#       (ya viene con los 50 empleados pre-generados, sin necesidad de
#       correr ningún script de Python) y dale "Run".
#
#    Alternativa (si quieres regenerar los datos dummy tú mismo en vez de
#    usar el seed_data.sql ya incluido): corre `python3 seed_employees.py`
#    desde ALGO que sí esté dentro de la VPC (por ejemplo, una Cloud Run Job
#    con --vpc-connector, o una VM de Compute Engine en la misma red) —
#    nunca desde Cloud Shell.

# 5) (Opcional) CI/CD con GitHub — requiere haber conectado tu repo una vez
#    desde la consola de Cloud Build:
cd ../infra
bash 07_cicd_triggers.sh
```

A partir de ahí, cada push a `main` que toque la carpeta de un servicio
dispara automáticamente su build + deploy (ver `cloudbuild.yaml` de cada
carpeta y `infra/07_cicd_triggers.sh`).

## 5. Probar la API de empleados directamente (CRUD)

`employee-api` es privado; para probarlo desde tu máquina/Cloud Shell:

```bash
TOKEN=$(gcloud auth print-identity-token)
EMPLOYEE_API_URL=$(gcloud run services describe easyhr-employee-api --region=$REGION --format='value(status.url)')

curl -H "Authorization: Bearer $TOKEN" "$EMPLOYEE_API_URL/employees?page=1&page_size=5"
curl -H "Authorization: Bearer $TOKEN" -X POST "$EMPLOYEE_API_URL/employees" \
  -H "Content-Type: application/json" \
  -d '{"nombre":"Ana","apellido_paterno":"Torres","apellido_materno":"Ruiz","fecha_nacimiento":"1995-05-20","fecha_ingreso":"2022-01-10","rol":"Ingeniero de Redes","area":"Ingenieria"}'
```

(Nota: tu identidad de usuario de `gcloud auth` también necesita
`roles/run.invoker` sobre el servicio para probarlo así.)

## 6. Ejecutar un servicio localmente (para desarrollo)

Cada servicio es una app Flask normal:

```bash
cd services/employee-api
pip install -r requirements.txt
export DB_NAME=easyhr DB_USER=easyhr_app DB_PASSWORD=... INSTANCE_CONNECTION_NAME=...
python3 app.py   # http://localhost:8080
```

Para los agentes ADK localmente necesitas además `GOOGLE_CLOUD_PROJECT`,
`GOOGLE_CLOUD_LOCATION` y `GOOGLE_GENAI_USE_VERTEXAI=TRUE`, y haber corrido
`gcloud auth application-default login` para que la librería de Google Gen
AI pueda autenticarse contra Vertex AI con tus credenciales.

## 7. Seguridad — resumen de lo implementado

- Ninguna contraseña ni API key vive en el código o en variables de entorno
  de texto plano en el repo: la contraseña de BD viaja únicamente vía
  `--set-secrets` de Cloud Run, leída de Secret Manager en tiempo de
  ejecución.
- Se usa **Vertex AI con la identidad de la cuenta de servicio** del propio
  servicio (`GOOGLE_GENAI_USE_VERTEXAI=TRUE`) en vez de una API key de
  Gemini, así que no hay ninguna clave de IA que filtrar.
- Cada servicio tiene su propia cuenta de servicio con el mínimo de permisos
  que necesita (principio de mínimo privilegio); ver `infra/04_service_accounts_iam.sh`.
- Todo Cloud Storage es privado (`--public-access-prevention`,
  uniform bucket-level access); los archivos se sirven a través de proxies
  autenticados, nunca con URLs públicas.
- Todos los servicios salvo el frontend son `--no-allow-unauthenticated`;
  las invocaciones servicio-a-servicio requieren `roles/run.invoker`
  otorgado explícitamente (ver el final de `infra/06_deploy_cloud_run.sh`).

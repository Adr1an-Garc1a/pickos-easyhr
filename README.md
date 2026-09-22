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
infra/                  # Scripts .sh para correr en Cloud Shell (00 → 07, en orden; 99 = teardown)
db/                      # schema.sql + seed_data.sql (50 empleados dummy) + seed_employees.py
services/
  employee-api/          # CRUD Flask + Cloud SQL (único servicio con acceso a la BD)
  birthday-agent/         # Agente ADK: cumpleaños + generación de tarjetas PDF/JPG
  vacation-agent/          # Agente ADK: cálculo de vacaciones (LFT México)
  jobdesc-agent/            # Agente ADK: redacción de Job Descriptions
  agent-master/              # Coordinador ADK (decide a qué subagente delegar)
frontend/                # Flask + HTML/CSS/JS, único servicio público
```

Cada carpeta de servicio tiene su propio `Dockerfile`, `requirements.txt` y
`cloudbuild.yaml` — son unidades de despliegue independientes, cada una con
su propio trigger de Cloud Build (ver sección 4.1).

## 4. Cómo desplegar desde cero (Cloud Shell)

```bash
# 0) Clona este repo dentro de Cloud Shell y entra a la carpeta infra
cd pickos-easyhr/infra
cp variables.env variables.local.env   # ya viene pre-configurado para
                                        # adr-garcia-pickos-easyhr; ajusta si
                                        # usas otro proyecto/repo
source variables.local.env

# 1) Infraestructura base (en este orden). 00_enable_apis.sh también borra
#    la VPC "default" del proyecto, ya que se usa una VPC dedicada propia.
bash 00_enable_apis.sh
bash 01_network.sh
bash 02_secrets_and_sql.sh
bash 03_artifact_registry_and_storage.sh
bash 04_service_accounts_iam.sh

# 2) (Opcional pero recomendado) sube tus PDFs de descripciones de puesto
#    actuales para que el Job Description Agent tenga referencia:
gcloud storage cp ./mis_puestos/*.pdf gs://${BUCKET_JOBDESC_REFS}/

# 3) Construye las imágenes y haz el PRIMER despliegue manual de los 6
#    servicios. Esto crea cada Cloud Run con su configuración completa
#    (VPC connector, Cloud SQL, secretos, service account, IAM entre
#    servicios). Los pushes futuros por CI/CD reconstruyen sobre esta base.
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

# 5) CI/CD: conecta tu repo de GitHub (ver el paso a paso detallado en la
#    sección 4.1 más abajo) y luego corre:
bash 07_cicd_triggers.sh
```

A partir de ese último paso, **cada push a `main` dispara el trigger del
servicio cuya carpeta tocaste** (uno de los 6, según qué archivos cambiaste)
y ese build reconstruye la configuración completa de Cloud Run para ese
servicio (VPC, secretos, URLs de sus dependencias obtenidas dinámicamente
con `gcloud run services describe`, permisos de invocación) — no solo
actualiza la imagen. Esto significa que el CI/CD puede incluso recrear un
servicio desde cero si llegaras a borrarlo por error, sin depender de que
alguien vuelva a correr `06_deploy_cloud_run.sh` a mano. Y como cada trigger
está filtrado por carpeta (`--included-files`), tocar un solo servicio no
reconstruye los otros 5.

**Nota sobre permisos de Cloud Build:** como cada `cloudbuild.yaml` hace
`gcloud run deploy` y `add-iam-policy-binding` por sí mismo, la cuenta de
servicio de Cloud Build necesita `roles/run.admin`,
`roles/iam.serviceAccountUser` y `roles/artifactregistry.writer` — el script
`07_cicd_triggers.sh` se los otorga automáticamente antes de crear los 6
triggers, así que no hay que hacerlo a mano.

### 4.1 Cómo conectar tu repositorio de GitHub a Cloud Build (paso a paso)

Esto solo se hace **una vez** por proyecto de GCP. Sin este paso,
`07_cicd_triggers.sh` no va a encontrar ninguna conexión ni repositorio
para usar.

1. En la consola de GCP, ve a **Cloud Build → Triggers**
   (`https://console.cloud.google.com/cloud-build/triggers`), asegurándote
   de tener seleccionado el proyecto correcto (`adr-garcia-pickos-easyhr`)
   arriba a la izquierda.
2. Haz clic en **"Crear activador"** (Create Trigger) — no te preocupes por
   llenar todo el formulario todavía, esto es solo para llegar al flujo de
   conexión.
3. En la sección **"Fuente" (Source)**, en el menú desplegable del
   repositorio, elige **"Conectar nuevo repositorio"** (Connect new
   repository).
4. Elige **GitHub** como proveedor de código fuente y haz clic en
   **"Continuar"**. Te va a pedir iniciar sesión con tu cuenta de GitHub si
   no lo has hecho ya en este navegador.
5. Se abre una ventana de GitHub pidiendo autorizar la app
   **"Google Cloud Build"**. Tienes dos opciones:
   - **"All repositories"**: le da acceso a todos tus repos (más simple).
   - **"Only select repositories"**: elige específicamente
     `Adr1an-Garc1a/pickos-easyhr` (más restrictivo, recomendado).
   Haz clic en **"Install"** (o "Authorize", según el flujo que te muestre).
6. De regreso en la consola de GCP, ahora debería aparecer
   `Adr1an-Garc1a/pickos-easyhr` en la lista de repositorios disponibles.
   Selecciónalo y marca la casilla de aceptar los términos de servicio de
   Cloud Build si te la muestra. Haz clic en **"Conectar"**.
7. En este punto ya tienes la CONEXIÓN creada (el repo está vinculado a tu
   proyecto de GCP). **Puedes cerrar el formulario de "Crear activador" sin
   terminarlo** — el trigger en sí lo va a crear el script
   `07_cicd_triggers.sh` por ti, no hace falta hacerlo a mano aquí.
8. Para confirmar que la conexión quedó bien, ve a Cloud Shell y corre:
   ```bash
   gcloud builds connections list --region=us-central1 --project=adr-garcia-pickos-easyhr
   ```
   Deberías ver una fila con el nombre de tu conexión (algo como
   `github-adr1an-garc1a` o similar, dependiendo de cómo la haya nombrado
   la consola automáticamente). Ese es el nombre que `07_cicd_triggers.sh`
   te va a pedir que escribas cuando lo corras.
9. Corre `bash 07_cicd_triggers.sh` — te va a mostrar esa misma lista de
   conexiones y de repositorios, y solo tienes que copiar/pegar los nombres
   exactos que veas cuando te los pida.

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
  otorgado explícitamente (ver el final de `infra/06_deploy_cloud_run.sh`
  y de cada `cloudbuild.yaml`).

## 8. Empezar desde cero (teardown)

Si necesitas borrar todo y reconstruir desde cero **en el mismo proyecto**:

```bash
cd infra
source variables.local.env
bash 99_teardown.sh   # pide confirmar escribiendo el PROJECT_ID exacto
```

Borra, en orden seguro: triggers de Cloud Build → servicios de Cloud Run →
Cloud SQL → buckets → Artifact Registry → secretos → cuentas de servicio →
conector VPC → firewall/subred/peering → la VPC. Después vuelves a correr
`00_enable_apis.sh` en adelante.

Si prefieres no reusar el mismo Project ID, es más simple borrar el
proyecto completo (`gcloud projects delete PROJECT_ID`) y crear uno nuevo.

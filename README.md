# Pick'Os · Easy HR

**Easy HR** es un sistema de Recursos Humanos multiagente para **Pick'Os**,
una empresa mexicana de infraestructura de centros de datos (data centers) y
servicios para licitaciones públicas. El sistema combina un frontend web, un
agente coordinador y tres subagentes especializados, todo corriendo sobre
**Google Cloud Platform** con el **Agent Development Kit (ADK)** de Google.

## 1. Qué hace el sistema

Desde un chat web, cualquier persona de RH puede pedirle al asistente:

- **Cumpleaños** — quién cumple años en un rango de fechas, y generar
  automáticamente una tarjeta de felicitación personalizada por cada persona
  (PDF o JPG) más una tarjeta general con el listado completo.
- **Vacaciones** — cuántos días de vacaciones tiene disponibles un empleado
  según su antigüedad (conforme a la Ley Federal del Trabajo mexicana), la
  fecha límite para tomarlas, y el proceso interno para solicitarlas.
- **Descripciones de puesto** — redactar una Job Description lista para
  publicar en OCC, LinkedIn, etc., usando como referencia los perfiles y
  documentos de puestos ya existentes en la empresa.

También incluye una pantalla de administración para dar de alta, editar,
consultar y eliminar empleados del directorio de la compañía.

## 2. Arquitectura en Google Cloud

```
                              Usuario (navegador)
                                     │  HTTPS pública
                                     ▼
                          ┌─────────────────────┐
                          │      frontend        │   Cloud Run · único servicio público
                          │  (Flask + HTML/JS)   │
                          └──────────┬───────────┘
                                     │ HTTP autenticado (ID token, IAM run.invoker)
                                     ▼
                          ┌─────────────────────┐
                          │    agent-master      │   Cloud Run · privado
                          │  (Coordinador ADK)   │   Decide a qué subagente delegar
                          └───┬─────────┬────────┘
                 ┌────────────┘         └────────────┐
                 ▼                      ▼             ▼
        ┌────────────────┐   ┌──────────────────┐  ┌──────────────────┐
        │ birthday-agent  │   │ vacation-agent    │  │ jobdesc-agent     │
        │ Cloud Run·ADK   │   │ Cloud Run · ADK   │  │ Cloud Run · ADK   │
        └───────┬─────────┘   └─────────┬─────────┘  └─────────┬─────────┘
                │ HTTP autenticado       │                     │
                └───────────┬────────────┴─────────────────────┘
                             ▼
                   ┌──────────────────┐
                   │   employee-api    │   Cloud Run · privado
                   │  (CRUD Flask)     │   Único servicio con acceso a la BD
                   └─────────┬─────────┘
                             │ VPC Connector (Serverless VPC Access)
                             ▼
                   ┌──────────────────┐        ┌────────────────────┐
                   │    Cloud SQL      │        │  Cloud Storage      │
                   │  (PostgreSQL,     │        │  (tarjetas de       │
                   │   IP privada)     │        │   cumpleaños y PDFs │
                   └──────────────────┘        │   de referencia)    │
                                                 └────────────────────┘

   Todo dentro de una VPC dedicada (easyhr-vpc), con Vertex AI (Gemini)
   como motor de IA de los 4 agentes, Secret Manager para credenciales,
   Artifact Registry para las imágenes Docker, y Cloud Build para CI/CD.
```

**Servicios de Cloud Run (6 en total):**

| Servicio | Rol | Acceso |
|---|---|---|
| `frontend` | Interfaz web (chat + panel de empleados) | Público |
| `agent-master` | Coordinador multiagente | Privado |
| `birthday-agent` | Subagente de cumpleaños | Privado |
| `vacation-agent` | Subagente de vacaciones | Privado |
| `jobdesc-agent` | Subagente de descripciones de puesto | Privado |
| `employee-api` | API CRUD de empleados | Privado |

## 3. El sistema multiagente

El sistema sigue un patrón de **coordinador + subagentes**, implementado con
el **Agent Development Kit (ADK)** de Google:

- **Agent Master (coordinador):** recibe la petición del usuario en lenguaje
  natural, decide cuál de los tres subagentes debe atenderla, y le delega la
  conversación. No accede a datos directamente — su única función es
  enrutar.
- **Birthday Agent:** consulta los cumpleaños próximos, genera las tarjetas
  de felicitación (individuales y una general) y las guarda en Cloud
  Storage.
- **Vacation Agent:** busca al empleado, calcula sus días de vacaciones
  disponibles según su antigüedad y explica el proceso para solicitarlas.
- **Job Description Agent:** conversa con el usuario para reunir los
  detalles del puesto, consulta los perfiles existentes en la empresa (y
  documentos PDF de referencia) y redacta la descripción final.

Cada subagente corre en su propio servicio de Cloud Run y se comunica con
`employee-api` (el único servicio con acceso a la base de datos) por HTTP
autenticado — nunca acceden a Cloud SQL directamente.

## 4. Tecnología usada

- **Cómputo:** Cloud Run (contenedores serverless, uno por servicio)
- **IA / agentes:** Google Agent Development Kit (ADK) + Vertex AI (Gemini)
- **Base de datos:** Cloud SQL para PostgreSQL (IP privada)
- **Almacenamiento:** Cloud Storage (tarjetas generadas, PDFs de referencia)
- **Red:** VPC dedicada + Serverless VPC Access Connector
- **Secretos:** Secret Manager
- **Contenedores:** Artifact Registry + Docker
- **CI/CD:** Cloud Build (triggers conectados a GitHub)
- **Backend:** Python 3.12, Flask, SQLAlchemy, Cloud SQL Python Connector
- **Generación de documentos:** ReportLab (PDF) y Pillow (JPG)
- **Frontend:** HTML, CSS y JavaScript nativos (sin framework)
- **Control de versiones:** GitHub

## 5. Estructura del repositorio

```
infra/                    # Scripts .sh para aprovisionar todo en GCP (00 → 07, en orden; 99 = borrar todo)
db/                        # Esquema de base de datos y datos de ejemplo
services/
  employee-api/            # API CRUD de empleados (Flask + Cloud SQL)
  birthday-agent/           # Subagente ADK de cumpleaños
  vacation-agent/            # Subagente ADK de vacaciones
  jobdesc-agent/              # Subagente ADK de descripciones de puesto
  agent-master/                # Coordinador ADK
frontend/                  # Aplicación web (Flask + HTML/CSS/JS)
```

Cada carpeta de servicio incluye su `Dockerfile`, `requirements.txt` y
`cloudbuild.yaml` propio.

## 6. Cómo replicarlo en tu propio proyecto de GCP

### Requisitos previos

- Una cuenta de Google Cloud con facturación habilitada.
- Un proyecto de GCP nuevo o dedicado para este sistema.
- Un repositorio de GitHub con este código.
- Acceso a Cloud Shell (o `gcloud` CLI instalado localmente).

### Paso a paso

**1. Clona el repositorio y configura las variables**

```bash
git clone <URL-de-tu-repositorio>
cd pickos-easyhr/infra
cp variables.env variables.local.env
# Edita variables.local.env con tu PROJECT_ID, región, y datos de tu repo de GitHub
source variables.local.env
```

**2. Aprovisiona la infraestructura base**

```bash
bash 00_enable_apis.sh                       # Habilita las APIs necesarias
bash 01_network.sh                           # VPC, subred, conector de acceso privado
bash 02_secrets_and_sql.sh                   # Cloud SQL + Secret Manager
bash 03_artifact_registry_and_storage.sh     # Artifact Registry + buckets
bash 04_service_accounts_iam.sh              # Cuentas de servicio y permisos
```

**3. Construye y despliega los 6 servicios**

```bash
bash 05_build_images.sh
bash 06_deploy_cloud_run.sh
```

Al finalizar, este script imprime la URL pública del frontend.

**4. Carga el esquema y los datos**

La instancia de Cloud SQL usa IP privada, así que la forma más simple de
cargar datos es con **Cloud SQL Studio** (consola de GCP → Cloud SQL → tu
instancia → Cloud SQL Studio):

1. Ejecuta el contenido de `db/schema.sql` (crea las tablas).
2. Ejecuta el contenido de `db/seed_data.sql` (carga datos de ejemplo).

**5. Configura el CI/CD**

Conecta tu repositorio de GitHub a Cloud Build desde la consola (Cloud
Build → Triggers → Crear activador → Conectar nuevo repositorio), y luego:

```bash
bash 07_cicd_triggers.sh
```

Esto crea un trigger por servicio: cada push a tu rama principal que
modifique la carpeta de un servicio reconstruye y redespliega
automáticamente ese servicio.

**6. Sube tus propios documentos de referencia (opcional)**

```bash
gcloud storage cp ./mis_puestos/*.pdf gs://${BUCKET_JOBDESC_REFS}/
```

Esto le da al Job Description Agent contexto real de los puestos de tu
empresa.

### Para empezar de cero

Si necesitas borrar todo lo aprovisionado y reconstruir el ambiente:

```bash
cd infra
source variables.local.env
bash 99_teardown.sh
```

"""
Pick'Os · Easy HR — Script de datos Dummy
==========================================
Genera 50 empleados falsos de una empresa ficticia de TI / data centers
(Pick'Os) que participa en licitaciones mexicanas, con áreas de Recursos
Humanos, Legal, Contabilidad, Marketing, Ingeniería, PMO, Calidad y Ventas.

No requiere IP pública ni contraseñas en texto plano en el repo:
  - La contraseña de BD se lee de Secret Manager en tiempo de ejecución.
  - La conexión a Cloud SQL se hace con el Cloud SQL Python Connector
    (mTLS interno de Google), sin necesidad de Cloud SQL Auth Proxy.

Uso (desde Cloud Shell, con las APIs y la instancia ya creadas):
    export PROJECT_ID="tu-proyecto"
    export DB_NAME="easyhr"
    export DB_USER="easyhr_app"
    export INSTANCE_CONNECTION_NAME="tu-proyecto:us-central1:easyhr-sql"
    export SECRET_DB_PASSWORD="easyhr-db-password"
    pip install -r requirements.txt --user
    python3 seed_employees.py
"""

import os
import random
import datetime

from google.cloud.sql.connector import Connector
from google.cloud import secretmanager
from faker import Faker

fake = Faker("es_MX")
random.seed(7)

PROJECT_ID = os.environ["PROJECT_ID"]
DB_NAME = os.environ.get("DB_NAME", "easyhr")
DB_USER = os.environ.get("DB_USER", "easyhr_app")
INSTANCE_CONNECTION_NAME = os.environ["INSTANCE_CONNECTION_NAME"]
SECRET_DB_PASSWORD = os.environ.get("SECRET_DB_PASSWORD", "easyhr-db-password")

AREAS = {
    "Recursos Humanos": ["Generalista de RH", "Reclutador", "Coordinador de Nómina", "Gerente de RH"],
    "Legal": ["Abogado Corporativo", "Paralegal", "Especialista en Licitaciones", "Gerente Legal"],
    "Contabilidad": ["Contador Junior", "Contador Senior", "Analista Fiscal", "Gerente de Contabilidad"],
    "Marketing": ["Diseñador Gráfico", "Especialista en Marketing Digital", "Content Manager", "Gerente de Marketing"],
    "Ingenieria": ["Ingeniero de Data Center", "Ingeniero de Redes", "DevOps Engineer", "Arquitecto de Infraestructura", "Gerente de Ingeniería"],
    "PMO": ["Coordinador de Proyectos", "Project Manager", "Scrum Master", "Gerente de PMO"],
    "Calidad": ["Analista de Calidad", "Auditor ISO", "Especialista en Procesos", "Gerente de Calidad"],
    "Ventas": ["Ejecutivo de Ventas", "Account Manager", "Especialista en Licitaciones Públicas", "Gerente de Ventas"],
}

TOTAL_EMPLOYEES = 50


def random_date(start: datetime.date, end: datetime.date) -> datetime.date:
    delta = (end - start).days
    return start + datetime.timedelta(days=random.randint(0, max(delta, 0)))


def get_db_password() -> str:
    """Obtiene la contraseña de la base de datos DESDE Secret Manager, nunca
    hardcodeada ni pasada como argumento en texto plano."""
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{PROJECT_ID}/secrets/{SECRET_DB_PASSWORD}/versions/latest"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode("UTF-8")


def build_employees():
    today = datetime.date.today()
    employees = []

    # 1) Primero se crean los gerentes de cada área (id se asigna al insertar)
    area_names = list(AREAS.keys())
    for area in area_names:
        nombre, ap, am = fake.first_name(), fake.last_name(), fake.last_name()
        employees.append({
            "nombre": nombre, "apellido_paterno": ap, "apellido_materno": am,
            "fecha_nacimiento": random_date(datetime.date(1975, 1, 1), datetime.date(1990, 12, 31)),
            "fecha_ingreso": random_date(datetime.date(2016, 1, 1), datetime.date(2021, 12, 31)),
            "rol": f"Gerente de {area}" if not AREAS[area][-1].startswith("Gerente") else AREAS[area][-1],
            "area": area,
            "gerente_de_area": area,   # marcador temporal, se resuelve después
            "es_gerente": True,
        })

    # 2) Resto de empleados hasta completar 50, repartidos entre áreas
    while len(employees) < TOTAL_EMPLOYEES:
        area = random.choice(area_names)
        roles_no_gerente = [r for r in AREAS[area] if not r.startswith("Gerente")]
        nombre, ap, am = fake.first_name(), fake.last_name(), fake.last_name()
        employees.append({
            "nombre": nombre, "apellido_paterno": ap, "apellido_materno": am,
            "fecha_nacimiento": random_date(datetime.date(1985, 1, 1), datetime.date(2002, 12, 31)),
            "fecha_ingreso": random_date(datetime.date(2019, 1, 1), today - datetime.timedelta(days=30)),
            "rol": random.choice(roles_no_gerente),
            "area": area,
            "gerente_de_area": None,
            "es_gerente": False,
        })

    # 3) Forzar ~6 cumpleaños dentro de los próximos 7 días para poder probar
    #    el Birthday Agent de inmediato, conservando el año de nacimiento real.
    sample_idx = random.sample(range(len(employees)), k=6)
    for i, idx in enumerate(sample_idx):
        target_day = today + datetime.timedelta(days=i + 1)
        birth_year = employees[idx]["fecha_nacimiento"].year
        try:
            employees[idx]["fecha_nacimiento"] = target_day.replace(year=birth_year)
        except ValueError:
            # 29 de febrero en año no bisiesto, etc.
            employees[idx]["fecha_nacimiento"] = target_day.replace(year=birth_year, day=28)

    return employees, area_names


def main():
    connector = Connector()

    def getconn():
        return connector.connect(
            INSTANCE_CONNECTION_NAME,
            "pg8000",
            user=DB_USER,
            password=get_db_password(),
            db=DB_NAME,
        )

    conn = getconn()
    conn.autocommit = False
    cur = conn.cursor()

    # Asegura catálogo de áreas
    cur.execute("SELECT id, nombre FROM areas")
    area_ids = {nombre: aid for aid, nombre in cur.fetchall()}

    employees, area_names = build_employees()

    # Limpia datos previos de prueba (idempotente para poder re-correr el script)
    cur.execute("TRUNCATE TABLE employees RESTART IDENTITY CASCADE")

    manager_id_by_area = {}
    inserted_ids = []

    # Insertar gerentes primero (sin gerente propio, o podrías apuntarlos a un
    # Director General ficticio; aquí los dejamos como top-level por simplicidad)
    for emp in [e for e in employees if e["es_gerente"]]:
        cur.execute(
            """
            INSERT INTO employees
                (nombre, apellido_paterno, apellido_materno, fecha_nacimiento,
                 fecha_ingreso, rol, area_id, gerente_id, email)
            VALUES (%s,%s,%s,%s,%s,%s,%s,NULL,%s) RETURNING id
            """,
            (
                emp["nombre"], emp["apellido_paterno"], emp["apellido_materno"],
                emp["fecha_nacimiento"], emp["fecha_ingreso"], emp["rol"],
                area_ids[emp["area"]],
                f"{emp['nombre'].lower()}.{emp['apellido_paterno'].lower()}@pickos.com",
            ),
        )
        new_id = cur.fetchone()[0]
        manager_id_by_area[emp["area"]] = new_id
        inserted_ids.append(new_id)

    # Insertar el resto, asignándoles como gerente al de su misma área
    for emp in [e for e in employees if not e["es_gerente"]]:
        cur.execute(
            """
            INSERT INTO employees
                (nombre, apellido_paterno, apellido_materno, fecha_nacimiento,
                 fecha_ingreso, rol, area_id, gerente_id, email)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id
            """,
            (
                emp["nombre"], emp["apellido_paterno"], emp["apellido_materno"],
                emp["fecha_nacimiento"], emp["fecha_ingreso"], emp["rol"],
                area_ids[emp["area"]],
                manager_id_by_area[emp["area"]],
                f"{emp['nombre'].lower()}.{emp['apellido_paterno'].lower()}@pickos.com",
            ),
        )
        inserted_ids.append(cur.fetchone()[0])

    conn.commit()
    cur.close()
    conn.close()
    connector.close()

    print(f"✔ Se insertaron {len(inserted_ids)} empleados dummy en '{DB_NAME}'.")
    print("  6 de ellos tienen cumpleaños dentro de los próximos 7 días (para probar el Birthday Agent).")


if __name__ == "__main__":
    main()

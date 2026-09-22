"""
Conexión a Cloud SQL (Postgres) usando el Cloud SQL Python Connector.
No se usa IP pública ni Cloud SQL Auth Proxy: el Connector abre un túnel
autenticado (mTLS) hacia la instancia usando la identidad de la cuenta de
servicio del propio servicio de Cloud Run.

Ninguna credencial vive en el código: DB_USER / DB_NAME / INSTANCE_CONNECTION_NAME
llegan como variables de entorno normales (no son secretas), y DB_PASSWORD
llega como variable de entorno inyectada por Cloud Run DESDE Secret Manager
(--set-secrets en el deploy), nunca como texto plano en el repo.
"""

import os
from google.cloud.sql.connector import Connector, IPTypes
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

INSTANCE_CONNECTION_NAME = os.environ["INSTANCE_CONNECTION_NAME"]
DB_USER = os.environ["DB_USER"]
DB_NAME = os.environ["DB_NAME"]
DB_PASSWORD = os.environ["DB_PASSWORD"]  # inyectada desde Secret Manager

_connector = Connector()


def _getconn():
    return _connector.connect(
        INSTANCE_CONNECTION_NAME,
        "pg8000",
        user=DB_USER,
        password=DB_PASSWORD,
        db=DB_NAME,
        ip_type=IPTypes.PRIVATE,  # la instancia solo tiene IP privada (--no-assign-ip);
                                  # sin esto el conector intenta usar la IP pública por
                                  # default y falla con CloudSQLIPTypeError.
    )


engine = create_engine("postgresql+pg8000://", creator=_getconn, pool_size=5, max_overflow=2, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

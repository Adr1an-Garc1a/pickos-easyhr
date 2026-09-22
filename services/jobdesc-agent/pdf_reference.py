"""
Lectura de PDFs de referencia (descripciones de puesto actuales de Pick'Os)
guardados en el bucket privado BUCKET_JOBDESC_REFS. El Job Description Agent
usa el texto extraído como contexto para redactar una nueva vacante.

Simplificación consciente de costo: se hace una búsqueda simple por nombre de
archivo (no una búsqueda semántica/vectorial). Para un volumen mayor de PDFs
o resultados más precisos, la siguiente evolución natural sería indexar estos
documentos con Vertex AI Search o un vector store, pero eso implica más
costo/infraestructura del que tiene sentido para este ambiente de prueba.
"""

import os
import re
import unicodedata

from google.cloud import storage
from pypdf import PdfReader
import io

BUCKET_JOBDESC_REFS = os.environ.get("BUCKET_JOBDESC_REFS")
_storage_client = storage.Client()

MAX_CHARS_PER_DOC = 4000


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def listar_pdfs_disponibles() -> list[str]:
    bucket = _storage_client.bucket(BUCKET_JOBDESC_REFS)
    return [b.name for b in bucket.list_blobs() if b.name.lower().endswith(".pdf")]


def buscar_referencia_por_rol(rol: str) -> dict:
    """Busca, dentro del bucket de referencias, el/los PDF(s) cuyo nombre se
    parezca al rol solicitado y extrae su texto como contexto.

    Returns:
        {"encontrado": bool, "archivos": [...], "texto_referencia": str}
    """
    rol_norm = _normalize(rol)
    todos = listar_pdfs_disponibles()
    candidatos = [name for name in todos if rol_norm in _normalize(name)]

    if not candidatos:
        return {"encontrado": False, "archivos": [], "texto_referencia": ""}

    bucket = _storage_client.bucket(BUCKET_JOBDESC_REFS)
    textos = []
    for name in candidatos[:2]:  # como máximo 2 documentos de referencia
        blob = bucket.blob(name)
        data = blob.download_as_bytes()
        try:
            reader = PdfReader(io.BytesIO(data))
            texto = "\n".join((page.extract_text() or "") for page in reader.pages)
        except Exception:
            texto = ""
        textos.append(texto[:MAX_CHARS_PER_DOC])

    return {"encontrado": True, "archivos": candidatos[:2], "texto_referencia": "\n---\n".join(textos)}

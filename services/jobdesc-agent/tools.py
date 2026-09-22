import os

from internal_client import call_internal_service
from pdf_reference import buscar_referencia_por_rol

EMPLOYEE_API_URL = os.environ["EMPLOYEE_API_URL"]


def listar_perfiles_disponibles(area: str = "") -> dict:
    """Lista los perfiles/roles que actualmente existen en Pick'Os, opcionalmente
    filtrados por área (por ejemplo "Ingenieria", "Ventas", "Legal").

    Args:
        area: Nombre exacto del área para filtrar. Vacío = todas las áreas.

    Returns:
        Diccionario con "items": lista de {"rol": ..., "area": ...}.
    """
    params = {"area": area} if area else {}
    items = call_internal_service(EMPLOYEE_API_URL, "/employees/roles", params=params)
    return {"items": items}


def obtener_referencia_de_puesto(rol: str) -> dict:
    """Busca en los documentos históricos de descripciones de puesto de
    Pick'Os (PDFs subidos por RH) contenido de referencia para un rol dado,
    para reutilizar tono, responsabilidades típicas y requisitos ya usados
    antes en la empresa.

    Args:
        rol: Nombre del puesto a buscar (por ejemplo "Ingeniero de Data Center").

    Returns:
        Diccionario con "encontrado" (bool), "archivos" (nombres de PDFs
        usados) y "texto_referencia" (extracto de texto para usar como
        contexto al redactar la nueva descripción).
    """
    return buscar_referencia_por_rol(rol)

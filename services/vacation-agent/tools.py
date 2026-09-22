import os
import datetime

from internal_client import call_internal_service
from vacation_law import calcular_vacaciones, PROCESO_SOLICITUD

EMPLOYEE_API_URL = os.environ["EMPLOYEE_API_URL"]


def buscar_empleado_por_nombre(nombre: str) -> dict:
    """Busca a un empleado de Pick'Os por nombre (o parte del nombre/apellido).

    Args:
        nombre: Nombre o apellido (o parte de ellos) del empleado a buscar.

    Returns:
        Diccionario con "count" y "items" (lista de coincidencias, cada una
        con id, nombre completo, rol, área y fecha_ingreso). Si hay más de
        una coincidencia, pide al usuario que precise cuál es.
    """
    result = call_internal_service(EMPLOYEE_API_URL, "/employees", params={"search": nombre, "page_size": 10})
    return {"count": result["total"], "items": result["items"]}


def calcular_dias_vacaciones(employee_id: int, fecha_referencia: str = "") -> dict:
    """Calcula, para un empleado ya identificado por su ID, cuántos días de
    vacaciones tiene disponibles conforme a la Ley Federal del Trabajo
    mexicana (LFT), su antigüedad, y la fecha límite legal para disfrutarlos.

    Args:
        employee_id: ID del empleado (obtenido con buscar_empleado_por_nombre).
        fecha_referencia: Fecha desde la cual calcular, en formato YYYY-MM-DD.
            Si se deja vacío, se usa la fecha de hoy.

    Returns:
        Diccionario con el desglose completo del cálculo de vacaciones y el
        texto del proceso para solicitarlas.
    """
    employee = call_internal_service(EMPLOYEE_API_URL, f"/employees/{employee_id}")
    fecha_ingreso = datetime.date.fromisoformat(employee["fecha_ingreso"])
    ref = datetime.date.fromisoformat(fecha_referencia) if fecha_referencia else datetime.date.today()

    calculo = calcular_vacaciones(fecha_ingreso, ref)
    calculo["empleado"] = {
        "id": employee["id"],
        "nombre": employee["nombre"],
        "apellido_paterno": employee["apellido_paterno"],
        "rol": employee["rol"],
        "area": employee["area"],
    }
    calculo["proceso_para_solicitar"] = PROCESO_SOLICITUD
    return calculo

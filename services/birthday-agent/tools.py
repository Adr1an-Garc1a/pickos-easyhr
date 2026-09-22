"""
Herramientas (tools) que el Birthday Agent (ADK) puede invocar. ADK genera
automáticamente el esquema de función a partir de la firma (type hints) y el
docstring, así que ambos deben ser claros y completos: el modelo los usa para
decidir cuándo y cómo llamar a cada herramienta.
"""

import os

from internal_client import call_internal_service
import cards

EMPLOYEE_API_URL = os.environ["EMPLOYEE_API_URL"]


def get_upcoming_birthdays(reference_date: str = "", days: int = 7) -> dict:
    """Obtiene la lista de empleados de Pick'Os que cumplen años dentro de los
    próximos `days` días contados a partir de `reference_date`.

    Args:
        reference_date: Fecha de referencia en formato YYYY-MM-DD. Si se deja
            vacío, se usa la fecha de hoy.
        days: Número de días hacia adelante a revisar (por defecto 7).

    Returns:
        Un diccionario con "count" (número de cumpleañeros encontrados) e
        "items" (lista de empleados con su próxima fecha de cumpleaños).
    """
    params = {"days": days}
    if reference_date:
        params["reference_date"] = reference_date
    return call_internal_service(EMPLOYEE_API_URL, "/employees/birthdays", params=params)


def create_individual_birthday_card(employee_id: int, proxima_fecha_cumpleanos: str, output_format: str = "pdf") -> dict:
    """Crea UNA tarjeta de cumpleaños personalizada en PDF o JPG para un solo
    empleado, usando su nombre, rol y área para personalizar el mensaje.

    Args:
        employee_id: ID del empleado (obtenido de get_upcoming_birthdays).
        proxima_fecha_cumpleanos: Fecha del próximo cumpleaños en formato
            YYYY-MM-DD (obtenida de get_upcoming_birthdays).
        output_format: "pdf" o "jpg". Por defecto "pdf".

    Returns:
        Diccionario con la ruta del archivo generado dentro del bucket
        (file_path) para poder descargarlo después con /files/<file_path>.
    """
    employee = call_internal_service(EMPLOYEE_API_URL, f"/employees/{employee_id}")
    employee["proxima_fecha_cumpleanos"] = proxima_fecha_cumpleanos
    return cards.generate_individual_card(employee, output_format=output_format)


def create_general_birthday_card(reference_date: str = "", days: int = 7, output_format: str = "pdf") -> dict:
    """Crea UNA sola tarjeta general que lista a TODOS los empleados que
    cumplen años dentro de los próximos `days` días, con una felicitación
    general (no personalizada por persona).

    Args:
        reference_date: Fecha de referencia en formato YYYY-MM-DD. Vacío = hoy.
        days: Número de días hacia adelante a revisar (por defecto 7).
        output_format: "pdf" o "jpg". Por defecto "pdf".

    Returns:
        Diccionario con la ruta del archivo generado (file_path) y cuántos
        empleados incluye la tarjeta (count).
    """
    data = get_upcoming_birthdays(reference_date=reference_date, days=days)
    ref = data["reference_date"]
    return cards.generate_general_card(data["items"], reference_date=ref, days=days, output_format=output_format)

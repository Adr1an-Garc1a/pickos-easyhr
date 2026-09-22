"""
Herramientas del Agent Master. Cada una de estas "herramientas" en realidad
invoca a un subagente REMOTO que corre como su propio servicio de Cloud Run
(esto refleja la arquitectura: Coordinator Agent -> Subagent invocation, solo
que aquí la invocación es una llamada HTTP autenticada entre servicios en
lugar de una composición in-process).
"""

import os

from internal_client import call_internal_service
from request_context import get_session_id, get_history

BIRTHDAY_AGENT_URL = os.environ["BIRTHDAY_AGENT_URL"]
VACATION_AGENT_URL = os.environ["VACATION_AGENT_URL"]
JOBDESC_AGENT_URL = os.environ["JOBDESC_AGENT_URL"]


def _invoke_subagent(base_url: str, message: str) -> str:
    # session_id e historial se toman del contexto de la petición HTTP
    # actual (ver request_context.py) en vez de pedírselos al LLM: así el
    # modelo solo tiene que decidir el texto a delegar, no reconstruir IDs.
    body = {
        "message": message,
        "session_id": get_session_id(),
        "user_id": "agent-master",
        "history": get_history(),
    }
    result = call_internal_service(base_url, "/invoke", method="POST", json_body=body)
    return result.get("response", "")


def consultar_birthday_agent(mensaje_para_el_subagente: str) -> str:
    """Delega la petición del usuario al Birthday Agent: úsalo cuando el
    usuario pregunte quién cumple años, pida cartas/tarjetas de cumpleaños,
    o cualquier tema relacionado a cumpleaños de empleados.

    Args:
        mensaje_para_el_subagente: La petición del usuario, reformulada si
            hace falta para que el subagente tenga todo el contexto (por
            ejemplo, incluye la fecha si el usuario la mencionó).

    Returns:
        La respuesta en texto del Birthday Agent.
    """
    return _invoke_subagent(BIRTHDAY_AGENT_URL, mensaje_para_el_subagente)


def consultar_vacation_agent(mensaje_para_el_subagente: str) -> str:
    """Delega la petición del usuario al Vacation Agent: úsalo cuando el
    usuario pregunte por días de vacaciones disponibles de algún empleado,
    su antigüedad, o el proceso para solicitar vacaciones.

    Args:
        mensaje_para_el_subagente: La petición del usuario, reformulada si
            hace falta (por ejemplo, asegúrate de incluir el nombre del
            empleado si el usuario lo mencionó).

    Returns:
        La respuesta en texto del Vacation Agent.
    """
    return _invoke_subagent(VACATION_AGENT_URL, mensaje_para_el_subagente)


def consultar_jobdesc_agent(mensaje_para_el_subagente: str) -> str:
    """Delega la petición del usuario al Job Description Agent: úsalo cuando
    el usuario quiera crear/redactar una descripción de puesto (Job
    Description) para publicar en OCC, LinkedIn u otras bolsas de trabajo.
    Este subagente suele necesitar varios turnos de conversación (hace
    preguntas de seguimiento); el historial se reenvía automáticamente.

    Args:
        mensaje_para_el_subagente: La petición o respuesta más reciente del
            usuario dentro de esta subtarea de redacción de vacante.

    Returns:
        La respuesta en texto del Job Description Agent (puede ser una
        pregunta de seguimiento o la Job Description final).
    """
    return _invoke_subagent(JOBDESC_AGENT_URL, mensaje_para_el_subagente)

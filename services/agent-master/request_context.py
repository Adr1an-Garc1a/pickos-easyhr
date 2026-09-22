"""
Contexto de la petición actual, accesible desde las herramientas del agente
sin que el LLM tenga que "adivinar" o repetir session_id/historial en cada
llamada a herramienta (eso reduciría la confiabilidad del function-calling).
Usamos contextvars para que sea seguro con los hilos de gunicorn.
"""

import contextvars

_session_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("session_id", default="")
_history_var: contextvars.ContextVar[list] = contextvars.ContextVar("history", default=[])


def set_request_context(session_id: str, history: list) -> None:
    _session_id_var.set(session_id)
    _history_var.set(history or [])


def get_session_id() -> str:
    return _session_id_var.get()


def get_history() -> list:
    return _history_var.get()

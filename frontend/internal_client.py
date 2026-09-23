"""
Cliente HTTP interno para llamadas servicio-a-servicio en Cloud Run.

Todos los servicios de Easy HR son privados (--no-allow-unauthenticated)
excepto el frontend. Para poder invocarse entre sí, cada llamada debe llevar
un ID token de Google válido cuya audiencia sea la URL del servicio destino;
Cloud Run verifica ese token y el rol roles/run.invoker del llamante ANTES
de que la petición llegue al contenedor.

Este helper obtiene el ID token automáticamente usando la identidad de la
cuenta de servicio del servicio (metadata server de Cloud Run) — no hay
ninguna credencial estática involucrada.
"""

import requests
import google.auth.transport.requests
import google.oauth2.id_token


def _get_id_token(audience: str) -> str:
    auth_req = google.auth.transport.requests.Request()
    return google.oauth2.id_token.fetch_id_token(auth_req, audience)


def call_internal_service(base_url: str, path: str, method: str = "GET", json_body: dict | None = None, params: dict | None = None, timeout: int = 240):
    """Llama a otro servicio de Cloud Run de la plataforma Easy HR con un ID
    token fresco. `base_url` debe ser la URL raíz del servicio (audiencia)."""
    token = _get_id_token(base_url)
    headers = {"Authorization": f"Bearer {token}"}
    url = base_url.rstrip("/") + path
    response = requests.request(method=method, url=url, headers=headers, json=json_body, params=params, timeout=timeout)
    response.raise_for_status()
    return response.json()

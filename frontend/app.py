"""
Pick'Os · Easy HR — Frontend
=============================
Único servicio público del sistema. Todo lo demás (employee-api,
agent-master y los 3 subagentes) es privado; este frontend es quien tiene
permiso para invocarlos (roles/run.invoker) y actúa como proxy autenticado
hacia ellos, sin exponer nunca sus URLs internas ni credenciales al navegador.
"""

import os

from flask import Flask, render_template, request, jsonify, Response, abort

from internal_client import call_internal_service

AGENT_MASTER_URL = os.environ["AGENT_MASTER_URL"]
EMPLOYEE_API_URL = os.environ["EMPLOYEE_API_URL"]
BIRTHDAY_AGENT_URL = os.environ.get("BIRTHDAY_AGENT_URL", "")

app = Flask(__name__)


@app.after_request
def _set_security_headers(response):
    """Cabeceras de seguridad básicas (defensa en profundidad contra XSS,
    clickjacking y sniffing de tipo de contenido)."""
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self'; "
        "img-src 'self' data:; object-src 'none'; base-uri 'self'; "
        "frame-ancestors 'none'"
    )
    return response


@app.get("/")
def index():
    return render_template("index.html", active="chat")


@app.get("/empleados")
def empleados_page():
    return render_template("employees.html", active="empleados")


# --------------------------------------------------------------------------
# Proxy del chat -> Agent Master
# --------------------------------------------------------------------------
@app.post("/api/chat")
def api_chat():
    data = request.get_json(silent=True) or {}
    message = data.get("message", "").strip()
    if not message:
        return jsonify({"error": "Mensaje vacío"}), 400

    body = {
        "message": message,
        "session_id": data.get("session_id", ""),
        "history": data.get("history", []),
        "user_id": "web-frontend",
    }
    try:
        result = call_internal_service(AGENT_MASTER_URL, "/invoke", method="POST", json_body=body)
    except Exception as exc:  # pragma: no cover - defensivo para la demo
        return jsonify({"error": f"No se pudo contactar al Agent Master: {exc}"}), 502

    return jsonify(result)


# --------------------------------------------------------------------------
# Descarga de tarjetas de cumpleaños generadas (proxy hacia birthday-agent)
# --------------------------------------------------------------------------
@app.get("/download/tarjeta/<path:file_path>")
def download_tarjeta(file_path: str):
    if not BIRTHDAY_AGENT_URL:
        abort(404)
    import google.auth.transport.requests
    import google.oauth2.id_token
    import requests as _requests

    token = google.oauth2.id_token.fetch_id_token(google.auth.transport.requests.Request(), BIRTHDAY_AGENT_URL)
    resp = _requests.get(
        f"{BIRTHDAY_AGENT_URL}/files/{file_path}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    if resp.status_code != 200:
        abort(404)
    return Response(resp.content, mimetype=resp.headers.get("Content-Type", "application/octet-stream"))


# --------------------------------------------------------------------------
# Proxy del CRUD de empleados -> employee-api (para la pantalla /empleados)
# --------------------------------------------------------------------------
@app.get("/api/employees")
def api_list_employees():
    params = {k: v for k, v in request.args.items()}
    result = call_internal_service(EMPLOYEE_API_URL, "/employees", params=params)
    return jsonify(result)


@app.get("/api/employees/<int:employee_id>")
def api_get_employee(employee_id: int):
    result = call_internal_service(EMPLOYEE_API_URL, f"/employees/{employee_id}")
    return jsonify(result)


@app.post("/api/employees")
def api_create_employee():
    body = request.get_json(silent=True) or {}
    result = call_internal_service(EMPLOYEE_API_URL, "/employees", method="POST", json_body=body)
    return jsonify(result), 201


@app.put("/api/employees/<int:employee_id>")
def api_update_employee(employee_id: int):
    body = request.get_json(silent=True) or {}
    result = call_internal_service(EMPLOYEE_API_URL, f"/employees/{employee_id}", method="PUT", json_body=body)
    return jsonify(result)


@app.delete("/api/employees/<int:employee_id>")
def api_delete_employee(employee_id: int):
    hard = request.args.get("hard", "false")
    result = call_internal_service(EMPLOYEE_API_URL, f"/employees/{employee_id}", method="DELETE", params={"hard": hard})
    return jsonify(result)


@app.get("/api/areas")
def api_areas():
    result = call_internal_service(EMPLOYEE_API_URL, "/areas")
    return jsonify(result)


@app.get("/health")
def health():
    return {"status": "ok", "service": "frontend"}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False)

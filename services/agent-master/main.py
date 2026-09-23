"""
Envoltura HTTP (Flask) para el Agent Master (coordinador ADK). Es el único
punto de entrada al sistema multiagente que el frontend público conoce.

Endpoint principal:
    POST /invoke
        { "message": "...", "session_id": "...", "history": [ {role, text}, ... ] }
        -> { "response": "...", "session_id": "..." }
"""

import asyncio
import uuid

from flask import Flask, request, jsonify

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from agent import root_agent
from request_context import set_request_context

APP_NAME = "agent_master"
app = Flask(__name__)


@app.after_request
def _set_security_headers(response):
    """Cabeceras de seguridad básicas (defensa en profundidad)."""
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
    return response

session_service = InMemorySessionService()
runner = Runner(agent=root_agent, app_name=APP_NAME, session_service=session_service)


def _build_message_with_history(message: str, history: list) -> str:
    if not history:
        return message
    lines = [f"{turn.get('role', 'usuario')}: {turn.get('text', '')}" for turn in history]
    lines.append(f"usuario: {message}")
    return "\n".join(lines)


async def _run_agent(user_id: str, session_id: str, message_text: str) -> str:
    await session_service.create_session(app_name=APP_NAME, user_id=user_id, session_id=session_id)
    content = types.Content(role="user", parts=[types.Part(text=message_text)])
    final_text_parts = []
    async for event in runner.run_async(user_id=user_id, session_id=session_id, new_message=content):
        if event.is_final_response() and event.content and event.content.parts:
            for part in event.content.parts:
                if part.text:
                    final_text_parts.append(part.text)
    return "\n".join(final_text_parts) if final_text_parts else "No se generó respuesta."


@app.get("/health")
def health():
    return {"status": "ok", "service": APP_NAME}


@app.post("/invoke")
def invoke():
    data = request.get_json(silent=True) or {}
    message = data.get("message")
    if not message:
        return jsonify({"error": "Falta 'message'"}), 400

    user_id = data.get("user_id", "frontend")
    session_id = data.get("session_id", uuid.uuid4().hex)
    history = data.get("history", [])

    # Deja disponible el session_id/historial para las tools (ver tools.py +
    # request_context.py) antes de correr al agente.
    set_request_context(session_id, history)

    full_message = _build_message_with_history(message, history)
    response_text = asyncio.run(_run_agent(user_id, session_id, full_message))
    return jsonify({"response": response_text, "session_id": session_id})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False)

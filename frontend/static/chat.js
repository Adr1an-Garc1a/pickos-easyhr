(function () {
  const log = document.getElementById("chat-log");
  const form = document.getElementById("chat-form");
  const input = document.getElementById("chat-input");

  // session_id de la conversación en el navegador (no depende de cookies ni
  // de estado en el servidor: el frontend reenvía el historial completo en
  // cada turno, ver README para el porqué de esta decisión de diseño).
  const sessionId = crypto.randomUUID();
  const history = [];

  function escapeHtml(str) {
    return str.replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    }[c]));
  }

  // Convierte el marcador especial que usan los agentes,
  // [Descargar tarjeta X](tarjeta:ruta/al/archivo.pdf), en un link real hacia
  // el proxy de descarga del frontend.
  function renderAgentText(text) {
    let safe = escapeHtml(text);
    safe = safe.replace(/\[([^\]]+)\]\(tarjeta:([^)]+)\)/g, (_, label, path) => {
      return `<a href="/download/tarjeta/${encodeURIComponent(path)}" target="_blank" rel="noopener">${label}</a>`;
    });
    return safe.replace(/\n/g, "<br/>");
  }

  function addBubble(role, text) {
    const div = document.createElement("div");
    div.className = `chat-bubble chat-bubble--${role === "usuario" ? "user" : "agent"}`;
    div.innerHTML = role === "usuario" ? escapeHtml(text) : renderAgentText(text);
    log.appendChild(div);
    log.scrollTop = log.scrollHeight;
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const message = input.value.trim();
    if (!message) return;

    addBubble("usuario", message);
    input.value = "";
    input.disabled = true;

    const thinking = document.createElement("div");
    thinking.className = "chat-bubble chat-bubble--agent";
    thinking.textContent = "Easy HR está pensando...";
    log.appendChild(thinking);
    log.scrollTop = log.scrollHeight;

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message, session_id: sessionId, history }),
      });
      const data = await res.json();
      thinking.remove();

      if (!res.ok) {
        addBubble("agente", `Ocurrió un error: ${data.error || "intenta de nuevo."}`);
      } else {
        history.push({ role: "usuario", text: message });
        history.push({ role: "agente", text: data.response });
        addBubble("agente", data.response);
      }
    } catch (err) {
      thinking.remove();
      addBubble("agente", "No se pudo contactar al asistente. Intenta de nuevo en un momento.");
    } finally {
      input.disabled = false;
      input.focus();
    }
  });
})();

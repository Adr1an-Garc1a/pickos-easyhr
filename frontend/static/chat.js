(function () {
  const log = document.getElementById("chat-log");
  const form = document.getElementById("chat-form");
  const input = document.getElementById("chat-input");
  const chips = document.querySelectorAll(".quick-chip");

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
      return `<a href="/download/tarjeta/${encodeURIComponent(path)}" target="_blank" rel="noopener">📎 ${label}</a>`;
    });
    return safe.replace(/\n/g, "<br/>");
  }

  function addBubble(role, text) {
    const isUser = role === "usuario";
    const row = document.createElement("div");
    row.className = `chat-row chat-row--${isUser ? "user" : "agent"} chat-row--enter`;

    const avatar = document.createElement("span");
    avatar.className = `avatar avatar--${isUser ? "user" : "agent"}`;
    avatar.textContent = isUser ? "Tú" : "P";

    const bubble = document.createElement("div");
    bubble.className = `chat-bubble chat-bubble--${isUser ? "user" : "agent"}`;
    bubble.innerHTML = isUser ? escapeHtml(text) : renderAgentText(text);

    if (isUser) {
      row.appendChild(bubble);
      row.appendChild(avatar);
    } else {
      row.appendChild(avatar);
      row.appendChild(bubble);
    }

    log.appendChild(row);
    log.scrollTop = log.scrollHeight;
    // dispara la animación de entrada en el siguiente frame
    requestAnimationFrame(() => row.classList.add("chat-row--visible"));
    return row;
  }

  function addTypingIndicator() {
    const row = document.createElement("div");
    row.className = "chat-row chat-row--agent chat-row--enter";
    row.innerHTML = `
      <span class="avatar avatar--agent">P</span>
      <div class="chat-bubble chat-bubble--agent typing-bubble">
        <span class="typing-dot"></span><span class="typing-dot"></span><span class="typing-dot"></span>
      </div>`;
    log.appendChild(row);
    log.scrollTop = log.scrollHeight;
    requestAnimationFrame(() => row.classList.add("chat-row--visible"));
    return row;
  }

  async function sendMessage(message) {
    addBubble("usuario", message);
    input.value = "";
    input.disabled = true;

    const thinking = addTypingIndicator();

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
  }

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const message = input.value.trim();
    if (!message) return;
    sendMessage(message);
  });

  chips.forEach((chip) => {
    chip.addEventListener("click", () => {
      const prompt = chip.dataset.prompt || "";
      // Si el prompt termina en espacio, es una plantilla a completar
      // (ej. "Necesito una descripción de puesto para "): la ponemos en el
      // input para que la persona termine de escribir, en vez de enviarla.
      if (prompt.endsWith(" ")) {
        input.value = prompt;
        input.focus();
      } else {
        sendMessage(prompt);
      }
    });
  });
})();

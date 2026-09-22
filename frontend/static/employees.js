(function () {
  const tbody = document.getElementById("employees-tbody");
  const searchInput = document.getElementById("search-input");
  const areaFilter = document.getElementById("area-filter");
  const pagination = document.getElementById("pagination");
  const dialog = document.getElementById("employee-dialog");
  const form = document.getElementById("employee-form");
  const dialogTitle = document.getElementById("dialog-title");
  const areaSelect = document.getElementById("f-area");

  let currentPage = 1;
  let searchTimeout = null;

  async function loadAreas() {
    const res = await fetch("/api/areas");
    const areas = await res.json();
    for (const a of areas) {
      areaFilter.insertAdjacentHTML("beforeend", `<option value="${a.nombre}">${a.nombre}</option>`);
      areaSelect.insertAdjacentHTML("beforeend", `<option value="${a.nombre}">${a.nombre}</option>`);
    }
  }

  async function loadEmployees(page = 1) {
    currentPage = page;
    const params = new URLSearchParams({ page, page_size: 10 });
    if (searchInput.value.trim()) params.set("search", searchInput.value.trim());
    if (areaFilter.value) params.set("area", areaFilter.value);

    const res = await fetch(`/api/employees?${params.toString()}`);
    const data = await res.json();

    tbody.innerHTML = data.items.map((e) => `
      <tr>
        <td>${e.id}</td>
        <td>${e.nombre} ${e.apellido_paterno} ${e.apellido_materno}</td>
        <td>${e.rol}</td>
        <td>${e.area}</td>
        <td>${e.gerente_nombre || "—"}</td>
        <td>${e.fecha_ingreso}</td>
        <td>${e.fecha_nacimiento}</td>
        <td>
          <span class="link-action" data-edit="${e.id}">Editar</span>
          <span class="link-action danger" data-delete="${e.id}">Eliminar</span>
        </td>
      </tr>
    `).join("");

    const totalPages = Math.max(Math.ceil(data.total / data.page_size), 1);
    pagination.innerHTML = Array.from({ length: totalPages }, (_, i) => i + 1)
      .map((p) => `<button class="${p === currentPage ? "is-active" : ""}" data-page="${p}">${p}</button>`)
      .join("");
  }

  function openDialog(employee) {
    form.reset();
    document.getElementById("f-id").value = employee?.id || "";
    dialogTitle.textContent = employee ? `Editar: ${employee.nombre}` : "Nuevo empleado";
    document.getElementById("f-nombre").value = employee?.nombre || "";
    document.getElementById("f-apellido-paterno").value = employee?.apellido_paterno || "";
    document.getElementById("f-apellido-materno").value = employee?.apellido_materno || "";
    document.getElementById("f-fecha-nacimiento").value = employee?.fecha_nacimiento || "";
    document.getElementById("f-fecha-ingreso").value = employee?.fecha_ingreso || "";
    document.getElementById("f-rol").value = employee?.rol || "";
    document.getElementById("f-area").value = employee?.area || "";
    document.getElementById("f-gerente-id").value = employee?.gerente_id || "";
    document.getElementById("f-email").value = employee?.email || "";
    dialog.showModal();
  }

  document.getElementById("btn-new-employee").addEventListener("click", () => openDialog(null));
  document.getElementById("btn-cancel").addEventListener("click", () => dialog.close());

  tbody.addEventListener("click", async (event) => {
    const editId = event.target.dataset.edit;
    const deleteId = event.target.dataset.delete;

    if (editId) {
      const res = await fetch(`/api/employees/${editId}`);
      openDialog(await res.json());
    }

    if (deleteId) {
      if (!confirm("¿Eliminar (baja lógica) a este empleado?")) return;
      await fetch(`/api/employees/${deleteId}`, { method: "DELETE" });
      loadEmployees(currentPage);
    }
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const id = document.getElementById("f-id").value;
    const payload = {
      nombre: document.getElementById("f-nombre").value,
      apellido_paterno: document.getElementById("f-apellido-paterno").value,
      apellido_materno: document.getElementById("f-apellido-materno").value,
      fecha_nacimiento: document.getElementById("f-fecha-nacimiento").value,
      fecha_ingreso: document.getElementById("f-fecha-ingreso").value,
      rol: document.getElementById("f-rol").value,
      area: document.getElementById("f-area").value,
      email: document.getElementById("f-email").value || undefined,
    };
    const gerenteId = document.getElementById("f-gerente-id").value;
    if (gerenteId) payload.gerente_id = parseInt(gerenteId, 10);

    if (id) {
      await fetch(`/api/employees/${id}`, {
        method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
      });
    } else {
      await fetch("/api/employees", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
      });
    }
    dialog.close();
    loadEmployees(currentPage);
  });

  pagination.addEventListener("click", (event) => {
    if (event.target.dataset.page) loadEmployees(parseInt(event.target.dataset.page, 10));
  });

  searchInput.addEventListener("input", () => {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => loadEmployees(1), 350);
  });
  areaFilter.addEventListener("change", () => loadEmployees(1));

  loadAreas();
  loadEmployees();
})();

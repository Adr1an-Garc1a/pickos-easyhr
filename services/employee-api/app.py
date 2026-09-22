"""
Pick'Os · Easy HR — Employee CRUD API
======================================
API REST en Flask para dar de alta, editar, borrar y consultar empleados.
Este es el ÚNICO servicio con acceso a Cloud SQL: los subagentes (Birthday,
Vacation, Job Description) y el frontend consumen esta API en vez de tocar
la base de datos directamente, lo que reduce la superficie de exposición de
credenciales a un solo lugar.

Este servicio se despliega PRIVADO (--no-allow-unauthenticated). Cloud Run
exige un ID token válido con el rol roles/run.invoker antes de que la
petición llegue siquiera a este código, así que no hay endpoint alcanzable
sin autenticación de por medio.

Endpoints:
    GET    /health
    GET    /areas
    GET    /employees?area=Ingenieria&search=juan&page=1&page_size=25
    GET    /employees/<id>
    POST   /employees
    PUT    /employees/<id>
    DELETE /employees/<id>
    GET    /employees/birthdays?reference_date=YYYY-MM-DD&days=7
    GET    /employees/roles?area=Ingenieria      (para el Job Description Agent)
"""

import datetime
from flask import Flask, request, jsonify
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from db import SessionLocal

app = Flask(__name__)

REQUIRED_FIELDS = [
    "nombre", "apellido_paterno", "apellido_materno",
    "fecha_nacimiento", "fecha_ingreso", "rol", "area",
]


def _parse_date(value: str, field: str) -> datetime.date:
    try:
        return datetime.date.fromisoformat(value)
    except (TypeError, ValueError):
        raise ValueError(f"Campo '{field}' debe tener formato YYYY-MM-DD")


def _row_to_dict(row) -> dict:
    return {
        "id": row.id,
        "nombre": row.nombre,
        "apellido_paterno": row.apellido_paterno,
        "apellido_materno": row.apellido_materno,
        "fecha_nacimiento": row.fecha_nacimiento.isoformat(),
        "fecha_ingreso": row.fecha_ingreso.isoformat(),
        "rol": row.rol,
        "area": row.area,
        "area_id": row.area_id,
        "gerente_id": row.gerente_id,
        "gerente_nombre": row.gerente_nombre,
        "email": row.email,
        "activo": row.activo,
    }


@app.get("/health")
def health():
    return {"status": "ok", "service": "employee-api"}


@app.get("/areas")
def list_areas():
    with SessionLocal() as db:
        rows = db.execute(text("SELECT id, nombre FROM areas ORDER BY nombre")).fetchall()
        return jsonify([{"id": r.id, "nombre": r.nombre} for r in rows])


@app.get("/employees")
def list_employees():
    area = request.args.get("area")
    search = request.args.get("search")
    page = max(int(request.args.get("page", 1)), 1)
    page_size = min(max(int(request.args.get("page_size", 25)), 1), 100)
    offset = (page - 1) * page_size

    filters = ["e.activo = TRUE"]
    params = {}
    if area:
        filters.append("e.area = :area")
        params["area"] = area
    if search:
        filters.append(
            "(LOWER(e.nombre) LIKE :q OR LOWER(e.apellido_paterno) LIKE :q "
            "OR LOWER(e.apellido_materno) LIKE :q)"
        )
        params["q"] = f"%{search.lower()}%"

    where_clause = " AND ".join(filters)

    with SessionLocal() as db:
        total = db.execute(
            text(f"SELECT COUNT(*) FROM v_employees e WHERE {where_clause}"), params,
        ).scalar()

        params.update({"limit": page_size, "offset": offset})
        rows = db.execute(
            text(f"""
                SELECT * FROM v_employees e
                WHERE {where_clause}
                ORDER BY e.id
                LIMIT :limit OFFSET :offset
            """), params,
        ).fetchall()

        return jsonify({
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": [_row_to_dict(r) for r in rows],
        })


@app.get("/employees/<int:employee_id>")
def get_employee(employee_id: int):
    with SessionLocal() as db:
        row = db.execute(
            text("SELECT * FROM v_employees WHERE id = :id"), {"id": employee_id}
        ).fetchone()
        if not row:
            return jsonify({"error": "Empleado no encontrado"}), 404
        return jsonify(_row_to_dict(row))


@app.post("/employees")
def create_employee():
    data = request.get_json(silent=True) or {}
    missing = [f for f in REQUIRED_FIELDS if not data.get(f)]
    if missing:
        return jsonify({"error": f"Faltan campos requeridos: {', '.join(missing)}"}), 400

    try:
        fecha_nacimiento = _parse_date(data["fecha_nacimiento"], "fecha_nacimiento")
        fecha_ingreso = _parse_date(data["fecha_ingreso"], "fecha_ingreso")
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    with SessionLocal() as db:
        area_row = db.execute(
            text("SELECT id FROM areas WHERE nombre = :nombre"), {"nombre": data["area"]}
        ).fetchone()
        if not area_row:
            return jsonify({"error": f"Área '{data['area']}' no existe"}), 400

        gerente_id = data.get("gerente_id")
        if gerente_id is not None:
            exists = db.execute(
                text("SELECT 1 FROM employees WHERE id = :id"), {"id": gerente_id}
            ).fetchone()
            if not exists:
                return jsonify({"error": f"gerente_id {gerente_id} no existe"}), 400

        email = data.get("email") or (
            f"{data['nombre'].split()[0].lower()}."
            f"{data['apellido_paterno'].lower()}@pickos.com"
        )

        try:
            result = db.execute(
                text("""
                    INSERT INTO employees
                        (nombre, apellido_paterno, apellido_materno, fecha_nacimiento,
                         fecha_ingreso, rol, area_id, gerente_id, email)
                    VALUES (:nombre, :ap, :am, :fnac, :fing, :rol, :area_id, :gerente_id, :email)
                    RETURNING id
                """),
                {
                    "nombre": data["nombre"], "ap": data["apellido_paterno"],
                    "am": data["apellido_materno"], "fnac": fecha_nacimiento,
                    "fing": fecha_ingreso, "rol": data["rol"],
                    "area_id": area_row.id, "gerente_id": gerente_id, "email": email,
                },
            )
            new_id = result.fetchone()[0]
            db.commit()
        except IntegrityError as e:
            db.rollback()
            return jsonify({"error": "No se pudo crear el empleado (posible email duplicado)", "detail": str(e.orig)}), 409

        return jsonify({"id": new_id, "message": "Empleado creado"}), 201


@app.put("/employees/<int:employee_id>")
def update_employee(employee_id: int):
    data = request.get_json(silent=True) or {}
    if not data:
        return jsonify({"error": "Cuerpo vacío"}), 400

    allowed_fields = {
        "nombre", "apellido_paterno", "apellido_materno", "fecha_nacimiento",
        "fecha_ingreso", "rol", "area", "gerente_id", "email", "activo",
    }
    unknown = set(data.keys()) - allowed_fields
    if unknown:
        return jsonify({"error": f"Campos no reconocidos: {', '.join(unknown)}"}), 400

    with SessionLocal() as db:
        exists = db.execute(text("SELECT 1 FROM employees WHERE id = :id"), {"id": employee_id}).fetchone()
        if not exists:
            return jsonify({"error": "Empleado no encontrado"}), 404

        set_clauses = []
        params = {"id": employee_id}

        for field in ("nombre", "apellido_paterno", "apellido_materno", "rol", "email"):
            if field in data:
                set_clauses.append(f"{field} = :{field}")
                params[field] = data[field]

        for date_field in ("fecha_nacimiento", "fecha_ingreso"):
            if date_field in data:
                try:
                    params[date_field] = _parse_date(data[date_field], date_field)
                except ValueError as e:
                    return jsonify({"error": str(e)}), 400
                set_clauses.append(f"{date_field} = :{date_field}")

        if "area" in data:
            area_row = db.execute(text("SELECT id FROM areas WHERE nombre = :n"), {"n": data["area"]}).fetchone()
            if not area_row:
                return jsonify({"error": f"Área '{data['area']}' no existe"}), 400
            set_clauses.append("area_id = :area_id")
            params["area_id"] = area_row.id

        if "gerente_id" in data:
            if data["gerente_id"] is not None:
                if data["gerente_id"] == employee_id:
                    return jsonify({"error": "Un empleado no puede ser su propio gerente"}), 400
                exists_g = db.execute(text("SELECT 1 FROM employees WHERE id = :id"), {"id": data["gerente_id"]}).fetchone()
                if not exists_g:
                    return jsonify({"error": f"gerente_id {data['gerente_id']} no existe"}), 400
            set_clauses.append("gerente_id = :gerente_id")
            params["gerente_id"] = data["gerente_id"]

        if "activo" in data:
            set_clauses.append("activo = :activo")
            params["activo"] = bool(data["activo"])

        if not set_clauses:
            return jsonify({"error": "No hay campos válidos para actualizar"}), 400

        set_clauses.append("actualizado_en = now()")
        try:
            db.execute(text(f"UPDATE employees SET {', '.join(set_clauses)} WHERE id = :id"), params)
            db.commit()
        except IntegrityError as e:
            db.rollback()
            return jsonify({"error": "No se pudo actualizar (posible email duplicado)", "detail": str(e.orig)}), 409

        return jsonify({"message": "Empleado actualizado"})


@app.delete("/employees/<int:employee_id>")
def delete_employee(employee_id: int):
    """Borrado lógico por default (activo=false); usar ?hard=true para borrar
    el registro físico (los subordinados quedan con gerente_id = NULL)."""
    hard = request.args.get("hard", "false").lower() == "true"
    with SessionLocal() as db:
        exists = db.execute(text("SELECT 1 FROM employees WHERE id = :id"), {"id": employee_id}).fetchone()
        if not exists:
            return jsonify({"error": "Empleado no encontrado"}), 404

        if hard:
            db.execute(text("DELETE FROM employees WHERE id = :id"), {"id": employee_id})
        else:
            db.execute(text("UPDATE employees SET activo = FALSE, actualizado_en = now() WHERE id = :id"), {"id": employee_id})
        db.commit()
        return jsonify({"message": "Empleado eliminado", "hard": hard})


@app.get("/employees/birthdays")
def upcoming_birthdays():
    """Usado por el Birthday Agent. Devuelve empleados cuyo cumpleaños cae
    dentro de los próximos `days` días a partir de `reference_date`."""
    days = int(request.args.get("days", 7))
    ref_str = request.args.get("reference_date")
    reference_date = _parse_date(ref_str, "reference_date") if ref_str else datetime.date.today()

    with SessionLocal() as db:
        rows = db.execute(text("SELECT * FROM v_employees WHERE activo = TRUE")).fetchall()

    results = []
    for r in rows:
        for offset in range(days + 1):
            check_date = reference_date + datetime.timedelta(days=offset)
            if (r.fecha_nacimiento.month, r.fecha_nacimiento.day) == (check_date.month, check_date.day):
                item = _row_to_dict(r)
                item["proxima_fecha_cumpleanos"] = check_date.isoformat()
                item["dias_para_cumplir"] = offset
                results.append(item)
                break

    results.sort(key=lambda x: x["dias_para_cumplir"])
    return jsonify({
        "reference_date": reference_date.isoformat(),
        "days": days,
        "count": len(results),
        "items": results,
    })


@app.get("/employees/roles")
def list_roles():
    """Usado por el Job Description Agent para saber qué perfiles existen."""
    area = request.args.get("area")
    with SessionLocal() as db:
        if area:
            rows = db.execute(
                text("""
                    SELECT DISTINCT e.rol, a.nombre AS area FROM employees e
                    JOIN areas a ON a.id = e.area_id
                    WHERE a.nombre = :area AND e.activo = TRUE
                    ORDER BY e.rol
                """), {"area": area},
            ).fetchall()
        else:
            rows = db.execute(
                text("""
                    SELECT DISTINCT e.rol, a.nombre AS area FROM employees e
                    JOIN areas a ON a.id = e.area_id
                    WHERE e.activo = TRUE
                    ORDER BY a.nombre, e.rol
                """)
            ).fetchall()
        return jsonify([{"rol": r.rol, "area": r.area} for r in rows])


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False)

"""
Generación de tarjetas de cumpleaños (PDF o JPG) con la identidad visual de
Pick'Os (azul y blanco). Las tarjetas se guardan en Cloud Storage (bucket
privado) y se sirven a través del endpoint /files de este mismo servicio.
"""

import io
import os
import uuid
import datetime

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import landscape, A5
from reportlab.lib.colors import HexColor
from reportlab.pdfgen import canvas
from google.cloud import storage

PICKOS_BLUE = "#0B3D91"
PICKOS_LIGHT_BLUE = "#3E7CB1"
PICKOS_WHITE = "#FFFFFF"

BUCKET_CARDS = os.environ.get("BUCKET_CARDS")
_storage_client = storage.Client()


def _personalized_message(employee: dict) -> str:
    nombre = employee["nombre"]
    rol = employee["rol"]
    area = employee["area"]
    return (
        f"¡Feliz cumpleaños, {nombre}!\n\n"
        f"Como {rol} del área de {area}, tu compromiso y talento son parte "
        f"fundamental de lo que hace grande a Pick'Os. Que este nuevo año de "
        f"vida venga cargado de éxitos, salud y muchos momentos para celebrar.\n\n"
        f"— Con cariño, tu familia Pick'Os"
    )


def _upload_bytes(data: bytes, filename: str, content_type: str) -> str:
    bucket = _storage_client.bucket(BUCKET_CARDS)
    blob = bucket.blob(filename)
    blob.upload_from_string(data, content_type=content_type)
    return filename


def _render_pdf(title: str, body_lines: list[str]) -> bytes:
    buf = io.BytesIO()
    page_size = landscape(A5)
    c = canvas.Canvas(buf, pagesize=page_size)
    width, height = page_size

    c.setFillColor(HexColor(PICKOS_BLUE))
    c.rect(0, 0, width, height, fill=1, stroke=0)
    c.setFillColor(HexColor(PICKOS_WHITE))
    c.roundRect(20, 20, width - 40, height - 40, 16, fill=1, stroke=0)

    c.setFillColor(HexColor(PICKOS_BLUE))
    c.setFont("Helvetica-Bold", 22)
    c.drawCentredString(width / 2, height - 60, "Pick'Os · Easy HR")
    c.setFont("Helvetica-Bold", 18)
    c.drawCentredString(width / 2, height - 90, title)

    c.setFont("Helvetica", 12)
    text_obj = c.beginText(45, height - 130)
    text_obj.setFillColor(HexColor("#1A1A1A"))
    for line in body_lines:
        for wrapped in _wrap_text(line, 70):
            text_obj.textLine(wrapped)
        text_obj.textLine("")
    c.drawText(text_obj)

    c.showPage()
    c.save()
    return buf.getvalue()


def _wrap_text(text: str, width: int) -> list[str]:
    words = text.split(" ")
    lines, current = [], ""
    for w in words:
        if len(current) + len(w) + 1 <= width:
            current = f"{current} {w}".strip()
        else:
            lines.append(current)
            current = w
    if current:
        lines.append(current)
    return lines or [""]


def _render_jpg(title: str, body_lines: list[str]) -> bytes:
    width, height = 1200, 800
    img = Image.new("RGB", (width, height), PICKOS_BLUE)
    draw = ImageDraw.Draw(img)
    margin = 40
    draw.rounded_rectangle([margin, margin, width - margin, height - margin], radius=24, fill=PICKOS_WHITE)

    try:
        font_title = ImageFont.truetype("DejaVuSans-Bold.ttf", 34)
        font_subtitle = ImageFont.truetype("DejaVuSans-Bold.ttf", 26)
        font_body = ImageFont.truetype("DejaVuSans.ttf", 20)
    except OSError:
        font_title = font_subtitle = font_body = ImageFont.load_default()

    draw.text((width / 2, 90), "Pick'Os · Easy HR", fill=PICKOS_BLUE, font=font_title, anchor="mm")
    draw.text((width / 2, 140), title, fill=PICKOS_LIGHT_BLUE, font=font_subtitle, anchor="mm")

    y = 200
    for line in body_lines:
        for wrapped in _wrap_text(line, 60):
            draw.text((margin + 30, y), wrapped, fill="#1A1A1A", font=font_body)
            y += 30
        y += 14

    out = io.BytesIO()
    img.save(out, format="JPEG", quality=90)
    return out.getvalue()


def generate_individual_card(employee: dict, output_format: str = "pdf") -> dict:
    """Genera una tarjeta de cumpleaños personalizada para UN empleado."""
    title = f"Cumpleaños de {employee['nombre']} {employee['apellido_paterno']}"
    body = [_personalized_message(employee), f"Fecha de cumpleaños: {employee.get('proxima_fecha_cumpleanos', employee['fecha_nacimiento'])}"]

    fmt = output_format.lower()
    filename = f"individual/{employee['id']}-{uuid.uuid4().hex[:8]}.{'pdf' if fmt == 'pdf' else 'jpg'}"

    if fmt == "pdf":
        data = _render_pdf(title, body)
        content_type = "application/pdf"
    else:
        data = _render_jpg(title, body)
        content_type = "image/jpeg"

    _upload_bytes(data, filename, content_type)
    return {"employee_id": employee["id"], "nombre": employee["nombre"], "file_path": filename, "format": fmt}


def generate_general_card(employees: list[dict], reference_date: str, days: int, output_format: str = "pdf") -> dict:
    """Genera UNA tarjeta general con el listado de todos los cumpleañeros del periodo."""
    title = f"Cumpleaños de los próximos {days} días"
    body_lines = [
        "¡Estas son las personas de Pick'Os que están de cumpleaños esta semana! "
        "Acompáñanos a felicitarlas."
    ]
    for emp in employees:
        fecha = emp.get("proxima_fecha_cumpleanos", emp["fecha_nacimiento"])
        body_lines.append(f"• {emp['nombre']} {emp['apellido_paterno']} ({emp['rol']}, {emp['area']}) — {fecha}")

    fmt = output_format.lower()
    filename = f"general/{reference_date}-{uuid.uuid4().hex[:8]}.{'pdf' if fmt == 'pdf' else 'jpg'}"

    if fmt == "pdf":
        data = _render_pdf(title, body_lines)
        content_type = "application/pdf"
    else:
        data = _render_jpg(title, body_lines)
        content_type = "image/jpeg"

    _upload_bytes(data, filename, content_type)
    return {"file_path": filename, "format": fmt, "count": len(employees)}


def download_bytes(file_path: str) -> tuple[bytes, str]:
    bucket = _storage_client.bucket(BUCKET_CARDS)
    blob = bucket.blob(file_path)
    data = blob.download_as_bytes()
    content_type = blob.content_type or "application/octet-stream"
    return data, content_type

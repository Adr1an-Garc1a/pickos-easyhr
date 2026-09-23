"""
Generación de tarjetas de cumpleaños (PDF o JPG) con la identidad visual de
Pick'Os: logo de la empresa, colores pastel, texto CENTRADO, y una escena
festiva (personitas celebrando + pastelito con vela + globos + confeti) en
la parte inferior — tanto en la tarjeta individual como en la general.

Nota de diseño: todo lo decorativo (personitas, pastelito, globos, confeti)
se dibuja con formas vectoriales en vez de usar emojis Unicode, porque los
emojis de color normalmente NO se renderizan en PDFs/imágenes generados en
servidor (las fuentes por default no incluyen glifos de emoji a color) —
esto garantiza que la tarjeta se vea bien sin depender de qué fuentes tenga
instaladas el contenedor.
"""

import io
import os
import uuid

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import landscape, A5
from reportlab.lib.colors import HexColor
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from google.cloud import storage

BUCKET_CARDS = os.environ.get("BUCKET_CARDS")
_storage_client = storage.Client()

LOGO_PATH = os.path.join(os.path.dirname(__file__), "assets", "pickos_logo_cropped.jpg")

PALETTES = [
    {"bg": "#FFE1EC", "accent": "#FF8FB1", "accent2": "#FFC1D6", "text": "#5C2A3A"},  # rosa
    {"bg": "#FFF6D8", "accent": "#FFD166", "accent2": "#FFE8A3", "text": "#6B4E00"},  # amarillo
    {"bg": "#DFF7E3", "accent": "#6FCF97", "accent2": "#B7F0C9", "text": "#1F5C3A"},  # menta
    {"bg": "#ECE1FF", "accent": "#B79CFF", "accent2": "#D9CBFF", "text": "#3B2A6B"},  # lavanda
    {"bg": "#DCEEFF", "accent": "#6FB1FF", "accent2": "#BFE0FF", "text": "#1F3B6B"},  # cielo
]

# Tonos de piel y de ropa para las personitas festejando — un set fijo,
# independiente de la paleta pastel de fondo, para que siempre resalten.
PEOPLE = [
    {"skin": "#F4C08C", "shirt": "#FF6B6B"},
    {"skin": "#C68642", "shirt": "#4C9F9A"},
    {"skin": "#8D5524", "shirt": "#FFC145"},
    {"skin": "#FFDBAC", "shirt": "#6C5CE7"},
]


def _palette_for(seed):
    return PALETTES[seed % len(PALETTES)]


def _personalized_message(employee):
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


def _upload_bytes(data, filename, content_type):
    bucket = _storage_client.bucket(BUCKET_CARDS)
    blob = bucket.blob(filename)
    blob.upload_from_string(data, content_type=content_type)
    return filename


def _layout_centered(paragraphs, avail_width, center_x, start_y,
                      line_step, paragraph_gap, measure_fn, space_width, draw_fn):
    """Motor de texto CENTRADO compartido entre PDF y JPG: cada línea (ya
    ajustada al ancho disponible) se centra respecto a `center_x`."""
    y = start_y
    for block in paragraphs:
        for raw in block.split("\n"):
            raw = raw.strip()
            if raw == "":
                y += paragraph_gap
                continue

            words = raw.split(" ")
            lines, current, current_width = [], [], 0.0
            for w in words:
                ww = measure_fn(w)
                added = ww if not current else ww + space_width
                if current and current_width + added > avail_width:
                    lines.append((current, current_width))
                    current, current_width = [w], ww
                else:
                    current.append(w)
                    current_width += added
            if current:
                lines.append((current, current_width))

            for line_words, line_width in lines:
                x = center_x - line_width / 2
                for w in line_words:
                    draw_fn(w, x, y)
                    x += measure_fn(w) + space_width
                y += line_step
        y += paragraph_gap
    return y


# =============================================================================
# Decoraciones vectoriales — PDF (reportlab)
# =============================================================================

def _pdf_confetti(c, x_min, x_max, y_min, y_max, palette, seed=0):
    import random
    rnd = random.Random(seed)
    colors = [palette["accent"], palette["accent2"], "#FFFFFF"]
    for _ in range(22):
        cx = rnd.uniform(x_min, x_max)
        cy = rnd.uniform(y_min, y_max)
        size = rnd.uniform(3, 6)
        color = rnd.choice(colors)
        c.setFillColor(HexColor(color))
        if rnd.random() < 0.5:
            c.circle(cx, cy, size, fill=1, stroke=0)
        else:
            c.saveState()
            c.translate(cx, cy)
            c.rotate(rnd.uniform(0, 360))
            c.rect(-size, -size / 2, size * 2, size, fill=1, stroke=0)
            c.restoreState()


def _pdf_balloon(c, x, y, scale, color):
    c.setFillColor(HexColor(color))
    c.ellipse(x - 9 * scale, y, x + 9 * scale, y + 24 * scale, fill=1, stroke=0)
    p = c.beginPath()
    p.moveTo(x - 2 * scale, y)
    p.lineTo(x + 2 * scale, y)
    p.lineTo(x, y - 4 * scale)
    p.close()
    c.drawPath(p, fill=1, stroke=0)
    c.setStrokeColor(HexColor(color))
    c.setLineWidth(0.7)
    c.line(x, y - 4 * scale, x - 2 * scale, y - 16 * scale)


def _pdf_cupcake(c, x, y, scale, palette):
    base_w_top, base_w_bottom, base_h = 40 * scale, 29 * scale, 21 * scale

    c.setFillColor(HexColor(palette["accent2"]))
    p = c.beginPath()
    p.moveTo(x - base_w_bottom / 2, y)
    p.lineTo(x + base_w_bottom / 2, y)
    p.lineTo(x + base_w_top / 2, y + base_h)
    p.lineTo(x - base_w_top / 2, y + base_h)
    p.close()
    c.drawPath(p, fill=1, stroke=0)

    c.setStrokeColor(HexColor(palette["accent"]))
    c.setLineWidth(1)
    for i in range(-2, 3):
        c.line(x + i * base_w_bottom / 6, y, x + i * base_w_top / 6, y + base_h)

    c.setFillColor(HexColor(palette["accent"]))
    top_y = y + base_h
    for dx in [-11, -4, 4, 11]:
        r = (8.5 - abs(dx) * 0.2) * scale
        c.circle(x + dx * scale, top_y + 5 * scale, r, fill=1, stroke=0)
    c.setFillColor(HexColor("#FFFFFF"))
    c.circle(x, top_y + 14 * scale, 7 * scale, fill=1, stroke=0)

    c.setFillColor(HexColor("#FFFFFF"))
    c.rect(x - 1.5 * scale, top_y + 16 * scale, 3 * scale, 12 * scale, fill=1, stroke=0)
    c.setStrokeColor(HexColor(palette["accent"]))
    c.setLineWidth(0.8)
    c.line(x - 1.5 * scale, top_y + 21 * scale, x + 1.5 * scale, top_y + 21 * scale)
    c.line(x - 1.5 * scale, top_y + 25 * scale, x + 1.5 * scale, top_y + 25 * scale)

    c.setFillColor(HexColor("#FFC24B"))
    c.ellipse(x - 2.4 * scale, top_y + 28 * scale, x + 2.4 * scale, top_y + 37 * scale, fill=1, stroke=0)
    c.setFillColor(HexColor("#FF8A3D"))
    c.ellipse(x - 1.3 * scale, top_y + 29 * scale, x + 1.3 * scale, top_y + 34 * scale, fill=1, stroke=0)


def _pdf_person(c, x, y, scale, skin, shirt):
    """Personita festejando con los brazos arriba. Ancla: (x, y) = centro de
    la base (los pies), crece hacia arriba."""
    body_w, body_h = 20 * scale, 26 * scale

    c.setStrokeColor(HexColor(skin))
    c.setLineWidth(3.2 * scale)
    c.line(x - body_w / 2, y + body_h * 0.65, x - body_w * 0.95, y + body_h * 1.35)
    c.line(x + body_w / 2, y + body_h * 0.65, x + body_w * 0.95, y + body_h * 1.35)
    c.setFillColor(HexColor(skin))
    c.circle(x - body_w * 0.95, y + body_h * 1.35, 2.6 * scale, fill=1, stroke=0)
    c.circle(x + body_w * 0.95, y + body_h * 1.35, 2.6 * scale, fill=1, stroke=0)

    c.setFillColor(HexColor(shirt))
    c.roundRect(x - body_w / 2, y, body_w, body_h, 5 * scale, fill=1, stroke=0)

    head_r = 9.5 * scale
    head_cy = y + body_h + head_r * 0.95
    c.setFillColor(HexColor(skin))
    c.circle(x, head_cy, head_r, fill=1, stroke=0)

    c.setFillColor(HexColor("#3A2E2E"))
    c.circle(x - head_r * 0.4, head_cy + head_r * 0.15, 0.9 * scale, fill=1, stroke=0)
    c.circle(x + head_r * 0.4, head_cy + head_r * 0.15, 0.9 * scale, fill=1, stroke=0)
    c.setStrokeColor(HexColor("#3A2E2E"))
    c.setLineWidth(1)
    c.arc(x - head_r * 0.45, head_cy - head_r * 0.55, x + head_r * 0.45, head_cy + head_r * 0.05, 200, 140)


def _draw_logo_chip_pdf(c, width, height, top_margin):
    logo = ImageReader(LOGO_PATH)
    iw, ih = logo.getSize()
    target_h = 40
    target_w = target_h * (iw / ih)
    chip_w, chip_h = target_w + 22, target_h + 14
    chip_x = (width - chip_w) / 2
    chip_y = height - top_margin - chip_h
    c.setFillColor(HexColor("#FFFFFF"))
    c.roundRect(chip_x, chip_y, chip_w, chip_h, 10, fill=1, stroke=0)
    c.drawImage(logo, chip_x + 11, chip_y + 7, width=target_w, height=target_h,
                preserveAspectRatio=True, mask='auto')
    return chip_y


def _render_pdf(title, body_paragraphs, palette, seed):
    buf = io.BytesIO()
    page_size = landscape(A5)
    c = canvas.Canvas(buf, pagesize=page_size)
    width, height = page_size

    CARD_MARGIN = 18
    SIDE_MARGIN = 40
    FONT_SIZE = 10.5
    LINE_STEP = 14.5

    c.setFillColor(HexColor(palette["bg"]))
    c.rect(0, 0, width, height, fill=1, stroke=0)
    c.setFillColor(HexColor("#FFFFFF"))
    c.roundRect(CARD_MARGIN, CARD_MARGIN, width - 2 * CARD_MARGIN, height - 2 * CARD_MARGIN, 16, fill=1, stroke=0)

    _pdf_confetti(c, CARD_MARGIN + 10, width * 0.32, height - 95, height - CARD_MARGIN - 10, palette, seed)
    _pdf_confetti(c, width * 0.68, width - CARD_MARGIN - 10, height - 95, height - CARD_MARGIN - 10, palette, seed + 1)

    logo_chip_y = _draw_logo_chip_pdf(c, width, height, top_margin=14)

    _pdf_balloon(c, CARD_MARGIN + 34, logo_chip_y + 4, 0.85, palette["accent"])
    _pdf_balloon(c, width - CARD_MARGIN - 34, logo_chip_y + 10, 0.7, palette["accent2"])

    c.setFillColor(HexColor(palette["text"]))
    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(width / 2, logo_chip_y - 20, title)

    text_top_y = logo_chip_y - 42
    text_avail_width = width - 2 * SIDE_MARGIN

    c.setFont("Helvetica", FONT_SIZE)
    c.setFillColor(HexColor(palette["text"]))
    _layout_centered(
        body_paragraphs, text_avail_width, width / 2, text_top_y,
        -LINE_STEP, -7,
        lambda w: c.stringWidth(w, "Helvetica", FONT_SIZE),
        c.stringWidth(" ", "Helvetica", FONT_SIZE),
        lambda w, x, y: c.drawString(x, y, w),
    )

    scene_y = CARD_MARGIN + 14
    scene_center = width / 2
    _pdf_person(c, scene_center - 62, scene_y, 0.95, PEOPLE[seed % 4]["skin"], PEOPLE[seed % 4]["shirt"])
    _pdf_cupcake(c, scene_center, scene_y, 1.15, palette)
    _pdf_person(c, scene_center + 62, scene_y, 0.95, PEOPLE[(seed + 2) % 4]["skin"], PEOPLE[(seed + 2) % 4]["shirt"])

    c.showPage()
    c.save()
    return buf.getvalue()


# =============================================================================
# Decoraciones vectoriales — JPG (Pillow)
# =============================================================================

def _pil_confetti(draw, x_min, x_max, y_min, y_max, palette, seed=0):
    import random
    rnd = random.Random(seed)
    colors = [palette["accent"], palette["accent2"], "#FFFFFF"]
    for _ in range(20):
        cx = rnd.uniform(x_min, x_max)
        cy = rnd.uniform(y_min, y_max)
        size = rnd.uniform(4, 9)
        color = rnd.choice(colors)
        if rnd.random() < 0.5:
            draw.ellipse([cx - size, cy - size, cx + size, cy + size], fill=color)
        else:
            draw.rectangle([cx - size, cy - size / 2, cx + size, cy + size / 2], fill=color)


def _pil_balloon(draw, x, y, scale, color):
    w, h = 30 * scale, 40 * scale
    draw.ellipse([x - w / 2, y - h, x + w / 2, y], fill=color)
    draw.polygon([(x - 4 * scale, y), (x + 4 * scale, y), (x, y + 8 * scale)], fill=color)
    draw.line([(x, y + 8 * scale), (x - 4 * scale, y + 34 * scale)], fill=color, width=2)


def _pil_cupcake(draw, x, y, scale, palette):
    base_w_top, base_w_bottom, base_h = 76 * scale, 55 * scale, 40 * scale

    draw.polygon([
        (x - base_w_bottom / 2, y),
        (x + base_w_bottom / 2, y),
        (x + base_w_top / 2, y - base_h),
        (x - base_w_top / 2, y - base_h),
    ], fill=palette["accent2"])

    for i in range(-2, 3):
        draw.line([(x + i * base_w_bottom / 6, y), (x + i * base_w_top / 6, y - base_h)],
                   fill=palette["accent"], width=2)

    top_y = y - base_h
    for dx in [-21, -7, 7, 21]:
        r = (17 - abs(dx) * 0.2) * scale
        draw.ellipse([x + dx * scale - r, top_y - 9 * scale - r, x + dx * scale + r, top_y - 9 * scale + r],
                     fill=palette["accent"])
    r = 14 * scale
    draw.ellipse([x - r, top_y - 26 * scale - r, x + r, top_y - 26 * scale + r], fill="#FFFFFF")

    draw.rectangle([x - 3 * scale, top_y - 50 * scale, x + 3 * scale, top_y - 26 * scale], fill="#FFFFFF")
    draw.line([(x - 3 * scale, top_y - 43 * scale), (x + 3 * scale, top_y - 43 * scale)], fill=palette["accent"], width=2)
    draw.line([(x - 3 * scale, top_y - 36 * scale), (x + 3 * scale, top_y - 36 * scale)], fill=palette["accent"], width=2)

    fr = 7 * scale
    fy = top_y - 58 * scale
    draw.ellipse([x - fr, fy - fr * 1.4, x + fr, fy + fr * 1.4], fill="#FFC24B")
    fr2 = 4 * scale
    draw.ellipse([x - fr2, fy - fr2 * 1.2, x + fr2, fy + fr2 * 1.2], fill="#FF8A3D")


def _pil_person(draw, x, y, scale, skin, shirt):
    """Personita festejando con los brazos arriba. Ancla: (x, y) = centro de
    la base (los pies); y crece hacia ABAJO."""
    body_w, body_h = 46 * scale, 60 * scale

    draw.line([(x - body_w / 2, y - body_h * 0.65), (x - body_w * 0.95, y - body_h * 1.35)],
               fill=skin, width=int(7 * scale))
    draw.line([(x + body_w / 2, y - body_h * 0.65), (x + body_w * 0.95, y - body_h * 1.35)],
               fill=skin, width=int(7 * scale))
    r_hand = 6 * scale
    draw.ellipse([x - body_w * 0.95 - r_hand, y - body_h * 1.35 - r_hand,
                  x - body_w * 0.95 + r_hand, y - body_h * 1.35 + r_hand], fill=skin)
    draw.ellipse([x + body_w * 0.95 - r_hand, y - body_h * 1.35 - r_hand,
                  x + body_w * 0.95 + r_hand, y - body_h * 1.35 + r_hand], fill=skin)

    draw.rounded_rectangle([x - body_w / 2, y - body_h, x + body_w / 2, y], radius=11 * scale, fill=shirt)

    head_r = 21 * scale
    head_cy = y - body_h - head_r * 0.95
    draw.ellipse([x - head_r, head_cy - head_r, x + head_r, head_cy + head_r], fill=skin)

    eye_off_x, eye_off_y = head_r * 0.4, head_r * 0.15
    er = 2 * scale
    draw.ellipse([x - eye_off_x - er, head_cy - eye_off_y - er, x - eye_off_x + er, head_cy - eye_off_y + er], fill="#3A2E2E")
    draw.ellipse([x + eye_off_x - er, head_cy - eye_off_y - er, x + eye_off_x + er, head_cy - eye_off_y + er], fill="#3A2E2E")
    draw.arc([x - head_r * 0.45, head_cy - head_r * 0.05, x + head_r * 0.45, head_cy + head_r * 0.55],
              start=20, end=160, fill="#3A2E2E", width=max(int(1.6 * scale), 1))


def _paste_logo_chip_pil(img, width, top_margin):
    logo = Image.open(LOGO_PATH).convert("RGB")
    target_h = 96
    target_w = int(target_h * (logo.width / logo.height))
    logo = logo.resize((target_w, target_h))

    chip_w, chip_h = target_w + 44, target_h + 26
    chip_x = (width - chip_w) // 2
    chip_y = top_margin

    chip = Image.new("RGB", (chip_w, chip_h), "#FFFFFF")
    ImageDraw.Draw(chip).rounded_rectangle([0, 0, chip_w - 1, chip_h - 1], radius=18, fill="#FFFFFF")
    chip.paste(logo, (22, 13))

    mask = Image.new("L", (chip_w, chip_h), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, chip_w - 1, chip_h - 1], radius=18, fill=255)
    img.paste(chip, (chip_x, chip_y), mask)
    return chip_y + chip_h


def _render_jpg(title, body_paragraphs, palette, seed):
    width, height = 1200, 800
    img = Image.new("RGB", (width, height), palette["bg"])
    draw = ImageDraw.Draw(img)

    CARD_MARGIN = 40
    SIDE_MARGIN = 90
    FONT_SIZE = 20

    draw.rounded_rectangle([CARD_MARGIN, CARD_MARGIN, width - CARD_MARGIN, height - CARD_MARGIN],
                            radius=28, fill="#FFFFFF")

    _pil_confetti(draw, CARD_MARGIN + 15, width * 0.3, CARD_MARGIN + 15, CARD_MARGIN + 130, palette, seed)
    _pil_confetti(draw, width * 0.7, width - CARD_MARGIN - 15, CARD_MARGIN + 15, CARD_MARGIN + 130, palette, seed + 1)

    logo_bottom = _paste_logo_chip_pil(img, width, CARD_MARGIN + 18)
    draw = ImageDraw.Draw(img)

    _pil_balloon(draw, CARD_MARGIN + 75, logo_bottom - 20, 1.05, palette["accent"])
    _pil_balloon(draw, width - CARD_MARGIN - 75, logo_bottom - 5, 0.85, palette["accent2"])

    try:
        font_title = ImageFont.truetype("DejaVuSans-Bold.ttf", 28)
        font_body = ImageFont.truetype("DejaVuSans.ttf", FONT_SIZE)
    except OSError:
        font_title = font_body = ImageFont.load_default()

    text_color = palette["text"]
    draw.text((width / 2, logo_bottom + 24), title, fill=text_color, font=font_title, anchor="mm")

    text_top_y = logo_bottom + 62
    text_avail_width = width - 2 * SIDE_MARGIN

    _layout_centered(
        body_paragraphs, text_avail_width, width / 2, text_top_y,
        30, 13,
        lambda w: font_body.getlength(w),
        font_body.getlength(" "),
        lambda w, x, y: draw.text((x, y), w, fill=text_color, font=font_body),
    )

    scene_y = height - CARD_MARGIN - 24
    scene_center = width / 2
    _pil_person(draw, scene_center - 150, scene_y, 0.95, PEOPLE[seed % 4]["skin"], PEOPLE[seed % 4]["shirt"])
    _pil_cupcake(draw, scene_center, scene_y, 1.25, palette)
    _pil_person(draw, scene_center + 150, scene_y, 0.95, PEOPLE[(seed + 2) % 4]["skin"], PEOPLE[(seed + 2) % 4]["shirt"])

    out = io.BytesIO()
    img.save(out, format="JPEG", quality=92)
    return out.getvalue()


# =============================================================================
# API pública del módulo
# =============================================================================

def generate_individual_card(employee, output_format="pdf"):
    """Genera una tarjeta de cumpleaños personalizada para UN empleado."""
    title = f"¡Feliz cumpleaños, {employee['nombre']}!"
    body = [_personalized_message(employee),
            f"Fecha de cumpleaños: {employee.get('proxima_fecha_cumpleanos', employee['fecha_nacimiento'])}"]
    palette = _palette_for(employee["id"])

    fmt = output_format.lower()
    filename = f"individual/{employee['id']}-{uuid.uuid4().hex[:8]}.{'pdf' if fmt == 'pdf' else 'jpg'}"

    if fmt == "pdf":
        data = _render_pdf(title, body, palette, employee["id"])
        content_type = "application/pdf"
    else:
        data = _render_jpg(title, body, palette, employee["id"])
        content_type = "image/jpeg"

    _upload_bytes(data, filename, content_type)
    return {"employee_id": employee["id"], "nombre": employee["nombre"], "file_path": filename, "format": fmt}


def generate_general_card(employees, reference_date, days, output_format="pdf"):
    """Genera UNA tarjeta general con el listado de todos los cumpleañeros del periodo."""
    title = f"¡Cumpleaños de los próximos {days} días en Pick'Os!"
    body_paragraphs = [
        "¡Estas son las personas de Pick'Os que están de cumpleaños esta semana! "
        "Acompáñanos a felicitarlas.\n"
    ]
    for emp in employees:
        fecha = emp.get("proxima_fecha_cumpleanos", emp["fecha_nacimiento"])
        body_paragraphs.append(
            f"{emp['nombre']} {emp['apellido_paterno']} ({emp['rol']}, {emp['area']}) — {fecha}"
        )

    palette = _palette_for(hash(reference_date) % 5)

    fmt = output_format.lower()
    filename = f"general/{reference_date}-{uuid.uuid4().hex[:8]}.{'pdf' if fmt == 'pdf' else 'jpg'}"

    if fmt == "pdf":
        data = _render_pdf(title, body_paragraphs, palette, len(employees))
        content_type = "application/pdf"
    else:
        data = _render_jpg(title, body_paragraphs, palette, len(employees))
        content_type = "image/jpeg"

    _upload_bytes(data, filename, content_type)
    return {"file_path": filename, "format": fmt, "count": len(employees)}


def download_bytes(file_path):
    bucket = _storage_client.bucket(BUCKET_CARDS)
    blob = bucket.blob(file_path)
    data = blob.download_as_bytes()
    content_type = blob.content_type or "application/octet-stream"
    return data, content_type

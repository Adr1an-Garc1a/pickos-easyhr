"""
Cálculo de días de vacaciones conforme a la Ley Federal del Trabajo (LFT)
mexicana, reforma de "vacaciones dignas" vigente desde el 1 de enero de 2023
(Art. 76 LFT) y a la fecha límite de disfrute del Art. 81 LFT.

IMPORTANTE — esto no es asesoría legal: la tabla y el plazo de disfrute se
implementan de la forma más común de interpretar la ley; ante un caso real,
Recursos Humanos / Legal de Pick'Os debe validar cualquier cálculo antes de
comunicarlo formalmente al colaborador.

Tabla de días por año de antigüedad cumplido (Art. 76 LFT):
    año 1: 12, año 2: 14, año 3: 16, año 4: 18, año 5: 20,
    años 6-10: 22, años 11-15: 24, años 16-20: 26, ... (+2 cada 5 años)
"""

import datetime


def dias_por_antiguedad(anios_cumplidos: int) -> int:
    if anios_cumplidos <= 0:
        return 0
    tabla = {1: 12, 2: 14, 3: 16, 4: 18, 5: 20}
    if anios_cumplidos in tabla:
        return tabla[anios_cumplidos]
    if anios_cumplidos <= 10:
        return 22
    # A partir del año 11, +2 días cada bloque adicional de 5 años,
    # iniciando en 24 para el bloque 11-15.
    bloque_extra = (anios_cumplidos - 11) // 5
    return 24 + (bloque_extra * 2)


def _anios_completos(fecha_ingreso: datetime.date, fecha_referencia: datetime.date) -> int:
    anios = fecha_referencia.year - fecha_ingreso.year
    aniversario_este_anio = fecha_ingreso.replace(year=fecha_referencia.year)
    if fecha_referencia < aniversario_este_anio:
        anios -= 1
    return max(anios, 0)


def calcular_vacaciones(fecha_ingreso: datetime.date, fecha_referencia: datetime.date | None = None) -> dict:
    fecha_referencia = fecha_referencia or datetime.date.today()
    anios_cumplidos = _anios_completos(fecha_ingreso, fecha_referencia)
    dias = dias_por_antiguedad(anios_cumplidos)

    try:
        ultimo_aniversario = fecha_ingreso.replace(year=fecha_ingreso.year + anios_cumplidos)
    except ValueError:
        ultimo_aniversario = fecha_ingreso.replace(year=fecha_ingreso.year + anios_cumplidos, day=28)

    fecha_limite_disfrute = ultimo_aniversario + datetime.timedelta(days=182)  # ~6 meses, Art. 81 LFT
    dias_restantes_para_limite = (fecha_limite_disfrute - fecha_referencia).days
    vencido = dias_restantes_para_limite < 0

    meses_antiguedad_total = (fecha_referencia.year - fecha_ingreso.year) * 12 + (fecha_referencia.month - fecha_ingreso.month)

    return {
        "fecha_ingreso": fecha_ingreso.isoformat(),
        "fecha_referencia": fecha_referencia.isoformat(),
        "antiguedad_anios_cumplidos": anios_cumplidos,
        "antiguedad_aproximada_meses": max(meses_antiguedad_total, 0),
        "dias_vacaciones_disponibles": dias,
        "ultimo_aniversario_laboral": ultimo_aniversario.isoformat(),
        "fecha_limite_para_disfrutarlas": fecha_limite_disfrute.isoformat(),
        "dias_restantes_para_limite": dias_restantes_para_limite,
        "periodo_vencido_segun_art81": vencido,
        "nota": (
            "Este cálculo asume que aún no se ha disfrutado ningún día del "
            "periodo vigente, ya que Easy HR todavía no lleva un historial de "
            "vacaciones tomadas. Si la persona ya tomó días de este periodo, "
            "RH debe descontarlos manualmente."
        ),
    }


PROCESO_SOLICITUD = (
    "Para solicitar tus vacaciones en Pick'Os: (1) llena el formato de "
    "solicitud de vacaciones, (2) entrégalo a tu gerente directo con al menos "
    "15 días naturales de anticipación a la fecha en que planeas salir, "
    "(3) espera la confirmación por escrito de tu gerente y de RH antes de "
    "hacer cualquier compromiso (viajes, reservaciones, etc.)."
)

"""
Los gráficos del tablero de delegación (guía de la evaluación 3: «dashboard
con filtros y gráficos que permitan interpretar avance, cumplimiento, estado
de compromisos, carga de trabajo y tendencias»).

El avance y el cumplimiento ya se ven en la tabla por funcionario. Aquí se
calculan los otros tres:

* carga de trabajo: cuántas actividades tiene cada persona y en qué situación;
* estado de los compromisos de la delegación;
* tendencia: actividades registradas y aprobadas por semana del período.

Se dibujan en el servidor, con HTML y SVG, sin bibliotecas externas: así se
ven igual sin conexión a internet y cada barra lleva su número escrito, que
es lo que permite leerlas con un lector de pantalla y sin distinguir colores.
"""

from datetime import date, timedelta

from django.db.models import Count, Q

from gestion.modelos_actividad import Actividad
from gestion.modelos_agenda import Compromiso
from gestion.semanas import lunes_de

#: Las situaciones de una actividad en la carga de trabajo, en el orden en
#: que se apilan, con su clase de color.
SITUACIONES = [
    ("aprobadas", "Aprobadas", "ok", [Actividad.Estado.APROBADA]),
    ("pendientes", "En revisión", "info", [Actividad.Estado.PENDIENTE]),
    ("corregir", "Por corregir o completar", "warn",
     [Actividad.Estado.RECHAZADA, Actividad.Estado.ANTECEDENTES]),
    ("sin_evidencia", "Sin evidencia", "neu", [Actividad.Estado.BORRADOR]),
]


def carga_de_trabajo(delegacion, periodo, personas):
    """
    Una fila por persona con sus actividades del período por situación.

    El ancho de cada barra es relativo a quien más tiene, para comparar la
    carga entre personas; cada tramo lleva su número.
    """
    usuarios = [perfil.usuario_id for perfil in personas]
    conteos = {}
    filas_bd = (Actividad.objects
                .filter(periodo=periodo, delegacion=delegacion, funcionario_id__in=usuarios)
                .exclude(estado=Actividad.Estado.ANULADA)
                .values("funcionario_id", "estado").annotate(n=Count("pk")))
    for fila in filas_bd:
        conteos.setdefault(fila["funcionario_id"], {})[fila["estado"]] = fila["n"]

    filas = []
    for perfil in personas:
        suyos = conteos.get(perfil.usuario_id, {})
        tramos = []
        for clave, rotulo, clase, estados in SITUACIONES:
            n = sum(suyos.get(e, 0) for e in estados)
            tramos.append({"clave": clave, "rotulo": rotulo, "clase": clase, "n": n})
        filas.append({"perfil": perfil, "tramos": tramos, "total": sum(t["n"] for t in tramos)})

    maximo = max((f["total"] for f in filas), default=0) or 1
    for fila in filas:
        fila["ancho"] = round(fila["total"] * 100 / maximo, 2)
        for tramo in fila["tramos"]:
            tramo["ancho"] = round(tramo["n"] * 100 / fila["total"], 2) if fila["total"] else 0
    filas.sort(key=lambda f: -f["total"])
    return {
        "filas": [f for f in filas if f["total"]],
        # Quienes no tienen actividades van en una línea aparte, no como barras vacías.
        "sin_actividades": [f["perfil"] for f in filas if not f["total"]],
        "leyenda": [(r, c) for _, r, c, _ in SITUACIONES],
    }


def estado_de_compromisos(delegacion, periodo, al_dia=None):
    """Los compromisos de la delegación por estado, y cuántos abiertos están vencidos."""
    hoy = al_dia or date.today()
    consulta = Compromiso.que_cuentan(
        Compromiso.objects.filter(periodo=periodo, delegacion=delegacion))
    por_estado = dict(consulta.values_list("estado").annotate(n=Count("pk")))
    vencidos = consulta.filter(estado__in=Compromiso.ABIERTOS, vencimiento__lt=hoy).count()
    orden = [
        (Compromiso.Estado.REALIZADO, "ok"),
        (Compromiso.Estado.EN_PROCESO, "info"),
        (Compromiso.Estado.PENDIENTE, "warn"),
        (Compromiso.Estado.INGRESADO, "neu"),
        (Compromiso.Estado.ANULADO, "off"),
    ]
    total = sum(por_estado.values())
    tramos = [{
        "rotulo": estado.label, "clase": clase, "n": por_estado.get(estado, 0),
        "ancho": round(por_estado.get(estado, 0) * 100 / total, 2) if total else 0,
    } for estado, clase in orden]
    return {"tramos": tramos, "total": total, "vencidos": vencidos}


def tendencia_semanal(delegacion, periodo, al_dia=None):
    """
    Actividades registradas y aprobadas por semana, desde el inicio del
    período hasta hoy (o su término, si ya terminó).

    Se cuentan por la fecha de la actividad, no por cuándo se aprobó: la
    pregunta es cuánto trabajo hubo cada semana y cuánto de ese trabajo ya
    está respaldado.
    """
    hoy = al_dia or date.today()
    fin = min(periodo.termino, hoy)
    if fin < periodo.inicio:
        return {"semanas": [], "maximo": 0}
    actividades = (Actividad.objects
                   .filter(periodo=periodo, delegacion=delegacion,
                           fecha__gte=periodo.inicio, fecha__lte=fin)
                   .exclude(estado=Actividad.Estado.ANULADA)
                   .values_list("fecha", "estado"))
    semanas = {}
    lunes = lunes_de(periodo.inicio)
    while lunes <= fin:
        semanas[lunes] = {"inicio": lunes, "registradas": 0, "aprobadas": 0}
        lunes += timedelta(days=7)
    for fecha, estado in actividades:
        semana = semanas.get(lunes_de(fecha))
        if semana is None:
            continue
        semana["registradas"] += 1
        if estado == Actividad.Estado.APROBADA:
            semana["aprobadas"] += 1
    lista = list(semanas.values())
    maximo = max((s["registradas"] for s in lista), default=0)
    return {"semanas": lista, "maximo": maximo, "svg": _svg_tendencia(lista, maximo)}


def _svg_tendencia(semanas, maximo):
    """Barras por semana: el total registrado y, encima, la parte aprobada."""
    if not semanas:
        return ""
    ancho_barra, separacion, alto = 26, 10, 150
    arriba = 18                      # espacio para el número sobre la barra más alta
    base = arriba + alto
    ancho = len(semanas) * (ancho_barra + separacion) + separacion
    tope = maximo or 1
    resumen = "; ".join(
        f'semana del {s["inicio"]:%d-%m}: {s["registradas"]} registradas, {s["aprobadas"]} aprobadas'
        for s in semanas)
    partes = [
        f'<svg class="gr-tend" viewBox="0 0 {ancho} {base + 24}" role="img" '
        f'aria-label="Actividades por semana. {resumen}." preserveAspectRatio="xMinYMin meet">'
    ]
    partes.append(f'<line x1="0" y1="{base}" x2="{ancho}" y2="{base}" class="eje"/>')
    for i, s in enumerate(semanas):
        x = separacion + i * (ancho_barra + separacion)
        h_reg = round(s["registradas"] * alto / tope, 1)
        h_apr = round(s["aprobadas"] * alto / tope, 1)
        titulo = (f'Semana del {s["inicio"]:%d-%m}: {s["registradas"]} registradas, '
                  f'{s["aprobadas"]} aprobadas')
        partes.append(f'<g><title>{titulo}</title>')
        partes.append(f'<rect x="{x}" y="{base - h_reg}" width="{ancho_barra}" height="{h_reg}" '
                      f'rx="3" class="reg"/>')
        partes.append(f'<rect x="{x}" y="{base - h_apr}" width="{ancho_barra}" height="{h_apr}" '
                      f'rx="3" class="apr"/>')
        if s["registradas"]:
            partes.append(f'<text x="{x + ancho_barra / 2}" y="{base - h_reg - 5}" '
                          f'class="num">{s["registradas"]}</text>')
        partes.append(f'<text x="{x + ancho_barra / 2}" y="{base + 16}" class="sem">'
                      f'{s["inicio"]:%d/%m}</text></g>')
    partes.append("</svg>")
    return "".join(partes)

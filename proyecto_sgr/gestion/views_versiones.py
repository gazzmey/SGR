"""
Historial de parámetros (HU-38, CU-66).

Qué metas, ponderadores, ítems y reglas estuvieron vigentes y cuándo
cambiaron, con su autor. Es de solo lectura —una versión no se edita ni se
borra— y lo consultan quienes configuran la medición: coordinador y
administrador en los roles de ejemplo. A cualquier otra persona se le
deniega (criterio 3 de la HU-38).
"""

from django.db.models import Q
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html, format_html_join

from comun import permisos as P
from comun.mantenedor import Columna, Filtro, ListaMantenedor
from gestion.modelos_versiones import VersionParametro
from gestion.models import Periodo


def _cambios_html(v):
    if v.origen == VersionParametro.Origen.PREVIO:
        return format_html('<span class="soft">Cómo estaba antes del primer cambio registrado</span>')
    if not v.cambios:
        if v.origen == VersionParametro.Origen.CIERRE:
            return format_html('<span class="soft">Congelada al cerrar el período</span>')
        return format_html('<span class="soft">Primera versión</span>')
    return format_html_join(
        "", '<div><b>{}</b>: {} → {}</div>',
        ((campo, antes, despues) for campo, antes, despues in v.cambios),
    )


def _periodos():
    return [(p.pk, p.nombre) for p in Periodo.objects.order_by("-inicio")]


class HistorialParametros(ListaMantenedor):
    model = VersionParametro
    permiso = P.CONFIGURAR_PERIODO
    menu = "historial"
    titulo = "Historial de parámetros"
    bajada = (
        "Cada cambio de un ítem, una meta, un ponderador o una regla de "
        "cálculo, con su vigencia, su autor y lo que había antes. Es lo que "
        "explica por qué un resultado histórico se calculó como se calculó."
    )
    singular = "versión"
    plural = "versiones"
    genero = "la"
    placeholder = "Parámetro: ítem, cargo, período o regla"
    busca = ["etiqueta", "vigencia"]
    orden_inicial = "-creada"
    url_lista = "gestion:historial"

    filtros = [
        Filtro("tipo", "Parámetro", VersionParametro.Tipo.choices, vacio="Todos"),
        Filtro("periodo", "Período", _periodos, vacio="Todos"),
        Filtro("origen", "Origen", VersionParametro.Origen.choices, vacio="Todos"),
    ]

    columnas = [
        Columna("etiqueta", "Parámetro", orden="etiqueta", clase="w",
                celda=lambda v: format_html(
                    '<b>{}</b><span class="t2">{} · versión {}</span>',
                    v.etiqueta, v.get_tipo_display(), v.version),
                valor=lambda v: v.etiqueta),
        Columna("version", "Versión", alineado="r", valor=lambda v: v.version),
        Columna("cambios", "Qué cambió", orden="", clase="w", celda=_cambios_html,
                valor=lambda v: "; ".join(f"{c}: {a} → {d}" for c, a, d in v.cambios)
                or v.get_origen_display()),
        Columna("vigencia", "Vigencia", orden="", clase="w",
                celda=lambda v: format_html('<span style="white-space: normal">{}</span>', v.vigencia),
                valor=lambda v: v.vigencia),
        Columna("creada", "Autor y fecha",
                celda=lambda v: format_html(
                    '{}<span class="t2">{}</span>', v.autor_nombre,
                    timezone.localtime(v.creada).strftime("%d-%m-%Y %H:%M")),
                valor=lambda v: f"{v.autor_nombre} · "
                                f"{timezone.localtime(v.creada):%d-%m-%Y %H:%M}"),
    ]

    nota = (
        "<b>Una versión no se edita ni se borra.</b> Cuando se cierra un "
        "período, su regla queda congelada como copia propia y ya no se puede "
        "cambiar sin reabrirlo; las metas del período quedan igual de fijas. "
        "Por eso ningún cambio posterior altera un resultado cerrado."
    )

    def base_queryset(self):
        consulta = VersionParametro.objects.select_related("autor", "periodo")
        objeto = (self.request.GET.get("objeto") or "").strip()
        if objeto.isdigit():
            consulta = consulta.filter(objeto_id=int(objeto))
        return consulta

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["url_nueva"] = ""
        return contexto


def enlace_historial(obj):
    """«3 versiones · Ver historial», para las fichas de ítem, meta y regla."""
    from gestion.versiones import cuantas_versiones

    n = cuantas_versiones(obj)
    url = reverse("gestion:historial") + f"?tipo={obj.TIPO_VERSION}&objeto={obj.pk}"
    if not n:
        texto = "Sin cambios desde que se registra el historial"
    else:
        texto = f"{n} versión" if n == 1 else f"{n} versiones"
    return format_html('{} · <a class="link" href="{}">Ver historial</a>', texto, url)

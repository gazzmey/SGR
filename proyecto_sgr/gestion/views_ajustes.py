"""
Felicitaciones, reclamos y ausencias: los registros que ajustan el resultado.

Son mantenedores con el patrón de siempre, limitados a las delegaciones que
el perfil autoriza. Los registra quien tiene el permiso «Registrar ajustes»
—el delegado y el coordinador en los roles de ejemplo—, no la persona
afectada: nadie se pone sus propias felicitaciones ni se borra sus reclamos.
"""

from django.db.models import Q
from django.utils.html import format_html

from comun import permisos as P
from comun.mantenedor import (
    CambiarEstado,
    Columna,
    CrearMantenedor,
    DetalleMantenedor,
    EditarMantenedor,
    Filtro,
    ListaMantenedor,
    chip_estado,
    enlace_nombre,
    filtro_estado,
)
from gestion import reglas as R
from gestion.forms_ajustes import AusenciaForm, ReconocimientoForm
from gestion.modelos_ajustes import Ausencia, Reconocimiento
from gestion.models import Periodo


class _ConAlcanceEnFormulario:
    """Le pasa al formulario a quiénes se puede elegir y quién registra."""

    def get_form_kwargs(self):
        datos = super().get_form_kwargs()
        datos["permitidas"] = self.delegaciones_permitidas()
        datos["usuario"] = self.request.user
        return datos


def _periodos():
    return [(p.pk, p.nombre) for p in Periodo.objects.filter(activo=True).order_by("-inicio")]


# =========================================================================
# Felicitaciones y reclamos
# =========================================================================


#: El medio en una palabra, para que quepa bajo la fecha en el listado.
MEDIO_CORTO = {
    Reconocimiento.Medio.CORREO: "Correo",
    Reconocimiento.Medio.WHATSAPP: "WhatsApp",
    Reconocimiento.Medio.LIBRO: "Libro de la oficina",
    Reconocimiento.Medio.CARTA: "Carta",
}


def _chip_tipo(obj):
    if obj.es_reclamo:
        return format_html('<span class="chip bad">Reclamo</span>')
    return format_html('<span class="chip ok">Felicitación</span>')


def _efecto(obj):
    """Cuántos puntos mueve, según la regla del período."""
    regla = R.vigente(obj.periodo)
    if obj.es_reclamo:
        return f"−{regla.valor_reclamo} puntos"
    return f"+{regla.valor_felicitacion} puntos (cuentan hasta {regla.max_felicitaciones})"


class ReconocimientosLista(ListaMantenedor):
    model = Reconocimiento
    permiso = P.REGISTRAR_AJUSTE
    campo_delegacion = "delegacion_id"
    menu = "reconocimientos"
    titulo = "Felicitaciones y reclamos"
    bajada = (
        "Lo que la comunidad escribió sobre la atención de cada funcionario. "
        "Cada felicitación suma y cada reclamo resta al cumplimiento ponderado."
    )
    singular = "registro"
    plural = "felicitaciones y reclamos"
    genero = "el"
    placeholder = "Código, funcionario, quién escribió o situación"
    rotulo_nuevo = "Nuevo registro"
    busca = ["codigo", "funcionario__first_name", "funcionario__last_name",
             "presentado_por", "situacion"]
    orden_inicial = "-fecha"

    url_lista = "gestion:reconocimientos"
    url_nueva = "gestion:reconocimiento_nuevo"
    url_editar = "gestion:reconocimiento_editar"
    url_detalle = "gestion:reconocimiento_detalle"
    url_estado = "gestion:reconocimiento_estado"

    filtros = [
        Filtro("tipo", "Tipo", Reconocimiento.Tipo.choices, vacio="Todos"),
        Filtro("periodo", "Período", _periodos, vacio="Todos"),
        filtro_estado(),
    ]

    columnas = [
        Columna("codigo", "Código", clase="mono"),
        Columna(
            "funcionario", "Funcionario", orden="funcionario__first_name", clase="w",
            celda=lambda o: enlace_nombre(
                o, "gestion:reconocimiento_detalle",
                extra=format_html('<span class="t2">{}</span>', o.delegacion.nombre),
            ),
            valor=lambda o: o.nombre_funcionario,
        ),
        Columna("tipo", "Tipo", celda=_chip_tipo, valor=lambda o: o.get_tipo_display()),
        Columna("fecha", "Fecha",
                celda=lambda o: format_html('{}<span class="t2">{}</span>',
                                            o.fecha.strftime("%d-%m-%Y"),
                                            MEDIO_CORTO.get(o.medio, o.get_medio_display())),
                valor=lambda o: o.fecha.strftime("%d-%m-%Y")),
        Columna("estado", "Estado", orden="activo", celda=chip_estado,
                valor=lambda o: "Vigente" if o.activo else "Desactivado"),
    ]

    # El Excel lleva todo: la pantalla deja el medio bajo la fecha y el
    # período en el filtro para que la tabla quepa sin desplazarse.
    excel_columnas = [
        Columna("codigo", "Código"),
        Columna("funcionario", "Funcionario", valor=lambda o: o.nombre_funcionario),
        Columna("delegacion", "Delegación", valor=lambda o: o.delegacion.nombre),
        Columna("tipo", "Tipo", valor=lambda o: o.get_tipo_display()),
        Columna("fecha", "Fecha", valor=lambda o: o.fecha.strftime("%d-%m-%Y")),
        Columna("medio", "Medio escrito", valor=lambda o: o.get_medio_display()),
        Columna("presentado_por", "Quién lo escribió"),
        Columna("respaldo", "Dónde consta"),
        Columna("situacion", "Situación"),
        Columna("periodo", "Período", valor=lambda o: o.periodo.nombre),
        Columna("estado", "Estado", valor=lambda o: "Vigente" if o.activo else "Desactivado"),
    ]

    nota = (
        "<b>Solo cuenta lo que consta por escrito.</b> Correo o WhatsApp al "
        "delegado, o el libro de observaciones de la oficina. Los reclamos "
        "tienen que ser por mala atención del funcionario. Desactivar un "
        "registro lo saca del cálculo, pero queda en el historial."
    )

    def base_queryset(self):
        return Reconocimiento.objects.select_related("funcionario", "delegacion", "periodo")


SECCIONES_RECONOCIMIENTO = [
    ("Qué es y a quién", "La felicitación o el reclamo, y la persona a la que se refiere.",
     ["tipo", "funcionario", "periodo", "fecha"]),
    ("El escrito", "De dónde sale. Sin el escrito no cuenta.",
     ["medio", "presentado_por", "respaldo", "situacion", "informado_a"]),
]


class ReconocimientoNuevo(_ConAlcanceEnFormulario, CrearMantenedor):
    model = Reconocimiento
    form_class = ReconocimientoForm
    permiso = P.REGISTRAR_AJUSTE
    campo_delegacion = "delegacion_id"
    menu = "reconocimientos"
    singular = "registro"
    plural = "felicitaciones y reclamos"
    url_lista = "gestion:reconocimientos"
    url_detalle = "gestion:reconocimiento_detalle"
    lateral = "gestion/_lateral_reconocimiento.html"
    secciones = SECCIONES_RECONOCIMIENTO

    def get_initial(self):
        inicial = super().get_initial()
        tipo = self.request.GET.get("tipo")
        if tipo in Reconocimiento.Tipo.values:
            inicial["tipo"] = tipo
        return inicial


class ReconocimientoEditar(_ConAlcanceEnFormulario, EditarMantenedor):
    model = Reconocimiento
    form_class = ReconocimientoForm
    permiso = P.REGISTRAR_AJUSTE
    campo_delegacion = "delegacion_id"
    menu = "reconocimientos"
    singular = "registro"
    plural = "felicitaciones y reclamos"
    url_lista = "gestion:reconocimientos"
    url_detalle = "gestion:reconocimiento_detalle"
    lateral = "gestion/_lateral_reconocimiento.html"
    secciones = SECCIONES_RECONOCIMIENTO


class ReconocimientoDetalle(DetalleMantenedor):
    model = Reconocimiento
    permiso = P.REGISTRAR_AJUSTE
    campo_delegacion = "delegacion_id"
    menu = "reconocimientos"
    singular = "registro"
    plural = "felicitaciones y reclamos"
    url_lista = "gestion:reconocimientos"
    url_editar = "gestion:reconocimiento_editar"
    url_estado = "gestion:reconocimiento_estado"
    campos = [
        ("Código", "codigo", {"mono": True}),
        ("Tipo", "tipo"),
        ("Funcionario", lambda o: o.nombre_funcionario),
        ("Delegación", lambda o: o.delegacion.nombre),
        ("Período", lambda o: o.periodo.nombre),
        ("Fecha del escrito", lambda o: o.fecha.strftime("%d-%m-%Y")),
        ("Medio escrito", "medio"),
        ("Quién lo escribió", "presentado_por"),
        ("Dónde consta", "respaldo", {"ancho": True}),
        ("Situación", "situacion", {"ancho": True}),
        ("Informado a", lambda o: o.informado_a or "—"),
        ("Registrado por", lambda o: (o.registrado_por.get_full_name()
                                      if o.registrado_por_id else "—")),
    ]
    kpis = [
        ("Efecto en el resultado",
         lambda o: _efecto(o) if o.activo else "Ninguno: está desactivado",
         "Según la regla de cálculo del período"),
        ("Del mismo tipo en el período",
         lambda o: Reconocimiento.objects.filter(
             funcionario_id=o.funcionario_id, periodo_id=o.periodo_id,
             tipo=o.tipo, activo=True).count(),
         "Vigentes, para esta persona"),
    ]
    pie = (
        "El ajuste se aplica sobre el cumplimiento ponderado de la persona, y "
        "el total queda entre cero y el tope de la regla."
    )

    def get_queryset(self):
        return super().get_queryset().select_related(
            "funcionario", "delegacion", "periodo", "registrado_por")


class ReconocimientoEstado(CambiarEstado):
    model = Reconocimiento
    permiso = P.REGISTRAR_AJUSTE
    campo_delegacion = "delegacion_id"
    url_lista = "gestion:reconocimientos"
    singular = "registro"


# =========================================================================
# Ausencias
# =========================================================================


def _rango(obj):
    if obj.desde == obj.hasta:
        return obj.desde.strftime("%d-%m-%Y")
    return f"{obj.desde:%d-%m-%Y} al {obj.hasta:%d-%m-%Y}"


class AusenciasLista(ListaMantenedor):
    model = Ausencia
    permiso = P.REGISTRAR_AJUSTE
    campo_delegacion = "delegacion_id"
    menu = "ausencias"
    titulo = "Ausencias"
    bajada = (
        "Licencias, vacaciones, emergencias y compensatorios. Los días de "
        "ausencia se descuentan del avance que se espera de cada persona."
    )
    singular = "ausencia"
    plural = "ausencias"
    genero = "la"
    placeholder = "Código, funcionario u observación"
    rotulo_nuevo = "Nueva ausencia"
    busca = ["codigo", "funcionario__first_name", "funcionario__last_name",
             "observacion", "delegacion__nombre"]
    orden_inicial = "-desde"

    url_lista = "gestion:ausencias"
    url_nueva = "gestion:ausencia_nueva"
    url_editar = "gestion:ausencia_editar"
    url_detalle = "gestion:ausencia_detalle"
    url_estado = "gestion:ausencia_estado"

    filtros = [
        Filtro("tipo", "Tipo", Ausencia.Tipo.choices, vacio="Todos"),
        Filtro("alcance", "A quién",
               [("persona", "Una persona"), ("delegacion", "Toda la delegación")],
               consulta=lambda v: Q(funcionario__isnull=(v == "delegacion")),
               vacio="Todas"),
        filtro_estado(femenino=True),
    ]

    columnas = [
        Columna("codigo", "Código", clase="mono"),
        Columna(
            "funcionario", "A quién", orden="funcionario__first_name", clase="w",
            celda=lambda o: enlace_nombre(
                o, "gestion:ausencia_detalle",
                extra=format_html('<span class="t2">{}</span>', o.delegacion.nombre),
                femenino=True,
            ),
            valor=lambda o: o.a_quien,
        ),
        Columna("tipo", "Tipo", valor=lambda o: o.get_tipo_display()),
        Columna("desde", "Fechas",
                celda=lambda o: format_html(
                    '{}<span class="t2">{} día{}</span>', _rango(o),
                    o.dias_calendario, "" if o.dias_calendario == 1 else "s"),
                valor=_rango),
        Columna("estado", "Estado", orden="activo",
                celda=lambda o: chip_estado(o, femenino=True),
                valor=lambda o: "Activa" if o.activo else "Inactiva"),
    ]

    excel_columnas = [
        Columna("codigo", "Código"),
        Columna("funcionario", "A quién", valor=lambda o: o.nombre),
        Columna("delegacion", "Delegación", valor=lambda o: o.delegacion.nombre),
        Columna("tipo", "Tipo", valor=lambda o: o.get_tipo_display()),
        Columna("desde", "Desde", valor=lambda o: o.desde.strftime("%d-%m-%Y")),
        Columna("hasta", "Hasta", valor=lambda o: o.hasta.strftime("%d-%m-%Y")),
        Columna("dias", "Días", valor=lambda o: o.dias_calendario),
        Columna("observacion", "Observación"),
        Columna("estado", "Estado", valor=lambda o: "Activa" if o.activo else "Inactiva"),
    ]

    nota = (
        "<b>El descuento sigue la hoja SEMAFORO de la matriz.</b> El objetivo "
        "al día de hoy es (días transcurridos − días de ausencia) ÷ días del "
        "período. Un mismo día se descuenta una sola vez, aunque una "
        "emergencia de la delegación caiga encima de unas vacaciones."
    )

    def base_queryset(self):
        return Ausencia.objects.select_related("funcionario", "delegacion")


SECCIONES_AUSENCIA = [
    ("A quién", "Una persona, o toda la delegación si el trabajo se detuvo para todos.",
     ["delegacion", "funcionario", "tipo"]),
    ("Cuándo", "El primer y el último día, ambos incluidos.",
     ["desde", "hasta", "observacion"]),
]


class AusenciaNueva(_ConAlcanceEnFormulario, CrearMantenedor):
    model = Ausencia
    form_class = AusenciaForm
    permiso = P.REGISTRAR_AJUSTE
    campo_delegacion = "delegacion_id"
    menu = "ausencias"
    singular = "ausencia"
    plural = "ausencias"
    genero = "la"
    url_lista = "gestion:ausencias"
    url_detalle = "gestion:ausencia_detalle"
    lateral = "gestion/_lateral_ausencia.html"
    secciones = SECCIONES_AUSENCIA


class AusenciaEditar(_ConAlcanceEnFormulario, EditarMantenedor):
    model = Ausencia
    form_class = AusenciaForm
    permiso = P.REGISTRAR_AJUSTE
    campo_delegacion = "delegacion_id"
    menu = "ausencias"
    singular = "ausencia"
    plural = "ausencias"
    genero = "la"
    url_lista = "gestion:ausencias"
    url_detalle = "gestion:ausencia_detalle"
    lateral = "gestion/_lateral_ausencia.html"
    secciones = SECCIONES_AUSENCIA


class AusenciaDetalle(DetalleMantenedor):
    model = Ausencia
    permiso = P.REGISTRAR_AJUSTE
    campo_delegacion = "delegacion_id"
    menu = "ausencias"
    singular = "ausencia"
    plural = "ausencias"
    genero = "la"
    url_lista = "gestion:ausencias"
    url_editar = "gestion:ausencia_editar"
    url_estado = "gestion:ausencia_estado"
    campos = [
        ("Código", "codigo", {"mono": True}),
        ("A quién", lambda o: o.nombre),
        ("Delegación", lambda o: o.delegacion.nombre),
        ("Tipo", "tipo"),
        ("Fechas", _rango),
        ("Observación", lambda o: o.observacion or "—", {"ancho": True}),
        ("Registrada por", lambda o: (o.registrado_por.get_full_name()
                                      if o.registrado_por_id else "—")),
    ]
    kpis = [
        ("Días de calendario", lambda o: o.dias_calendario,
         "Con solo días hábiles, los fines de semana no se descuentan"),
        ("Personas afectadas",
         lambda o: 1 if o.funcionario_id else o.delegacion.perfiles.filter(activo=True).count(),
         "Las activas de la delegación, si es para todas"),
    ]
    pie = (
        "Una ausencia no cambia la meta: cambia cuánto se espera llevar a la "
        "fecha. Es lo que hace la hoja SEMAFORO de la matriz."
    )

    def get_queryset(self):
        return super().get_queryset().select_related(
            "funcionario", "delegacion", "registrado_por")


class AusenciaEstado(CambiarEstado):
    model = Ausencia
    permiso = P.REGISTRAR_AJUSTE
    campo_delegacion = "delegacion_id"
    url_lista = "gestion:ausencias"
    singular = "ausencia"
    genero = "la"

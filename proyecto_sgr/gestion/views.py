"""
Mantenedores de períodos, cargos y metas.

Mismo patrón que los seis anteriores. Lo propio de aquí es la **transición
de estado del período**: abrir, cerrar y reabrir no son el activo/inactivo
de los demás mantenedores, sino pasos de un ciclo que tiene consecuencias
—cerrar congela las metas y los resultados—, y por eso van en su propia
vista con su propia confirmación.
"""

from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views import View

from catalogos.models import Item
from comun import permisos as P
from comun.auditoria import registrar
from comun.models import EventoAuditoria
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
from comun.permisos import redirect_al_login, tiene_permiso
from comun.resultado import anunciar
from django.utils.html import format_html
from gestion.forms import (
    CargoForm,
    MetaPeriodoForm,
    PeriodoForm,
    ReglaCalculoForm,
)
from gestion.models import Cargo, MetaPeriodo, Periodo
from gestion.reglas import ReglaCalculo


# =========================================================================
# Períodos
# =========================================================================


CHIP_PERIODO = {
    Periodo.Estado.BORRADOR: ("line", "En preparación"),
    Periodo.Estado.ABIERTO: ("ok", "Abierto"),
    Periodo.Estado.CERRADO: ("off", "Cerrado"),
}


def _chip_periodo(periodo):
    clase, texto = CHIP_PERIODO[periodo.estado]
    return format_html('<span class="chip {}">{}</span>', clase, texto)


def _fechas(periodo):
    return format_html(
        '{}<span class="t2">{} días</span>',
        f"{periodo.inicio:%d-%m-%Y} al {periodo.termino:%d-%m-%Y}",
        periodo.dias_totales,
    )


class PeriodosLista(ListaMantenedor):
    model = Periodo
    permiso = P.CONFIGURAR_PERIODO
    menu = "periodos"
    titulo = "Períodos"
    bajada = (
        "La ventana de tiempo sobre la que se mide. Todo lo que el sistema "
        "calcula ocurre dentro de un período."
    )
    singular = "período"
    plural = "períodos"
    genero = "el"
    placeholder = "Nombre o código"
    rotulo_nuevo = "Nuevo período"
    busca = ["codigo", "nombre", "observacion"]
    orden_inicial = "-inicio"

    url_lista = "gestion:periodos"
    url_nueva = "gestion:periodo_nuevo"
    url_editar = "gestion:periodo_editar"
    url_detalle = "gestion:periodo_detalle"
    url_estado = "gestion:periodo_estado"

    filtros = [
        Filtro("periodo_estado", "Situación", Periodo.Estado.choices,
               campo="estado", vacio="Todas"),
        filtro_estado(),
    ]

    columnas = [
        Columna("codigo", "Código", clase="mono"),
        Columna(
            "nombre", "Período", orden="nombre",
            celda=lambda o: enlace_nombre(o, "gestion:periodo_detalle"),
        ),
        Columna("fechas", "Fechas", orden="inicio", celda=_fechas,
                valor=lambda o: f"{o.inicio:%d-%m-%Y} al {o.termino:%d-%m-%Y}"),
        Columna("situacion", "Situación", orden="estado", celda=_chip_periodo,
                valor=lambda o: o.get_estado_display()),
        Columna("metas", "Metas", orden="", alineado="r",
                valor=lambda o: o.metas.filter(activo=True).count()),
        Columna("estado", "Registro", orden="activo", celda=chip_estado,
                valor=lambda o: "Activo" if o.activo else "Inactivo"),
    ]

    nota = (
        "<b>Cerrar un período congela sus metas y su resultado.</b> Es lo que "
        "permite que el informe de un período cerrado siga cuadrando aunque "
        "después se reconfiguren las metas del siguiente. Reabrirlo es "
        "posible, queda registrado y solo lo puede hacer quien configura "
        "períodos."
    )


class PeriodoNuevo(CrearMantenedor):
    model = Periodo
    form_class = PeriodoForm
    permiso = P.CONFIGURAR_PERIODO
    menu = "periodos"
    singular = "período"
    plural = "períodos"
    genero = "el"
    url_lista = "gestion:periodos"
    url_detalle = "gestion:periodo_detalle"
    lateral = "gestion/_lateral_periodo.html"
    secciones = [
        ("Identificación", "Cómo se le llama en los informes.", ["codigo", "nombre"]),
        ("Fechas", "Definen cuántos días dura y, con eso, el avance esperado de cada día.",
         ["inicio", "termino"]),
        ("Observación", "Opcional. Queda en el historial del período.", ["observacion"]),
    ]


class PeriodoEditar(EditarMantenedor):
    model = Periodo
    form_class = PeriodoForm
    permiso = P.CONFIGURAR_PERIODO
    menu = "periodos"
    singular = "período"
    plural = "períodos"
    genero = "el"
    url_lista = "gestion:periodos"
    url_detalle = "gestion:periodo_detalle"
    lateral = "gestion/_lateral_periodo.html"
    secciones = PeriodoNuevo.secciones


class PeriodoDetalle(DetalleMantenedor):
    model = Periodo
    permiso = P.CONFIGURAR_PERIODO
    menu = "periodos"
    singular = "período"
    plural = "períodos"
    genero = "el"
    url_lista = "gestion:periodos"
    url_editar = "gestion:periodo_editar"
    url_estado = "gestion:periodo_estado"
    template_name = "gestion/periodo_detalle.html"
    campos = [
        ("Código", "codigo", {"mono": True}),
        ("Nombre", "nombre"),
        ("Situación", "estado"),
        ("Inicio", lambda o: f"{o.inicio:%d-%m-%Y}"),
        ("Término", lambda o: f"{o.termino:%d-%m-%Y}"),
        ("Duración", lambda o: f"{o.dias_totales} días de calendario"),
        ("Transcurrido", lambda o: f"{o.dias_transcurridos()} días"),
        ("Avance esperado hoy", lambda o: f"{o.avance_esperado():.2f} %".replace(".", ",")),
        ("Observación", "observacion", {"ancho": True}),
    ]
    kpis = [
        ("Metas configuradas", lambda o: o.metas.filter(activo=True).count(),
         "Cruces de cargo e ítem"),
        ("Cargos con metas",
         lambda o: o.metas.filter(activo=True).values("cargo").distinct().count(),
         "Cada uno debe sumar 100 %"),
    ]
    pie = "Las metas de un período cerrado no se modifican."


class PeriodoEstado(CambiarEstado):
    model = Periodo
    permiso = P.CONFIGURAR_PERIODO
    url_lista = "gestion:periodos"
    singular = "período"
    genero = "el"


class PeriodoTransicion(View):
    """
    Abre, cierra o reabre un período.

    Es distinto de activar y desactivar: eso dice si el registro se ofrece;
    esto dice en qué punto de su ciclo está. Cerrar tiene consecuencias
    —las metas quedan congeladas— y reabrir queda registrado con quién lo
    hizo, que es lo que pide el caso PAR-05.
    """

    PASOS = {
        "abrir": (Periodo.Estado.ABIERTO, "Período abierto",
                  "Desde ahora se pueden registrar actividades en él."),
        "cerrar": (Periodo.Estado.CERRADO, "Período cerrado",
                   "Las metas y el resultado quedan congelados tal como están."),
        "reabrir": (Periodo.Estado.ABIERTO, "Período reabierto",
                    "Vuelve a recibir actividades. La reapertura queda registrada."),
    }

    def post(self, request, pk, paso):
        if not request.user.is_authenticated:
            return redirect_al_login(request)
        if not tiene_permiso(request.user, P.CONFIGURAR_PERIODO):
            raise PermissionDenied("No tienes permiso para configurar períodos.")
        if paso not in self.PASOS:
            raise PermissionDenied("Ese paso no existe.")

        periodo = get_object_or_404(Periodo, pk=pk)
        destino, titulo, texto = self.PASOS[paso]

        impedimento = self._impedimento(periodo, paso)
        if impedimento:
            anunciar(request, "No se puede " + paso, impedimento, icono="error")
            return redirect("gestion:periodo_detalle", pk=pk)

        estado_previo = periodo.estado
        periodo.estado = destino
        campos = ["estado", "cerrado_el", "cerrado_por"]
        if paso == "cerrar":
            periodo.cerrado_el = timezone.localdate()
            periodo.cerrado_por = request.user
        else:
            # Reabrir borra el cierre, y con él se iría la única huella de
            # que este período estuvo cerrado alguna vez. El caso PAR-05 pide
            # que la reapertura quede auditada, así que antes de limpiar esos
            # campos se escribe en la observación quién reabrió, cuándo y
            # desde qué cierre. Se agrega al texto que ya hubiera: la
            # observación es un historial, no un campo que se pisa.
            if paso == "reabrir":
                quien = request.user.get_full_name() or request.user.get_username()
                antes = (f"cerrado el {periodo.cerrado_el:%d-%m-%Y}"
                         if periodo.cerrado_el else "cerrado sin fecha registrada")
                linea = (
                    "[%s] Reabierto por %s. Estaba %s%s."
                    % (timezone.localdate().strftime("%d-%m-%Y"), quien, antes,
                       f" por {periodo.cerrado_por.get_full_name() or periodo.cerrado_por.get_username()}"
                       if periodo.cerrado_por_id else "")
                )
                periodo.observacion = (
                    f"{periodo.observacion}\n{linea}" if periodo.observacion else linea
                )
                campos.append("observacion")
            periodo.cerrado_el = None
            periodo.cerrado_por = None
        periodo.save(update_fields=campos)

        # El ciclo del período es de lo más delicado que tiene el sistema:
        # cerrar congela resultados y reabrir los vuelve a poner en juego.
        # Los tres pasos quedan en la auditoría con el estado de origen.
        registrar(request, EventoAuditoria.Accion.PERIODO,
                  entidad="Período", objeto=periodo,
                  antes=dict(Periodo.Estado.choices).get(estado_previo, estado_previo),
                  despues=dict(Periodo.Estado.choices).get(destino, destino),
                  detalle=texto)

        anunciar(request, titulo, f"«{periodo.nombre}»: {texto}")
        return redirect("gestion:periodo_detalle", pk=pk)

    @staticmethod
    def _impedimento(periodo, paso):
        """Por qué ese paso no corresponde ahora, o cadena vacía."""
        if paso == "abrir":
            if periodo.estado != Periodo.Estado.BORRADOR:
                return "Solo se abre un período que está en preparación."
            if not periodo.metas.filter(activo=True).exists():
                return (
                    "No tiene ninguna meta configurada. Un período sin metas "
                    "recibiría actividades que no suman a nada."
                )
        if paso == "cerrar" and periodo.estado != Periodo.Estado.ABIERTO:
            return "Solo se cierra un período abierto."
        if paso == "reabrir" and periodo.estado != Periodo.Estado.CERRADO:
            return "Solo se reabre un período cerrado."
        return ""


# =========================================================================
# Cargos
# =========================================================================


class CargosLista(ListaMantenedor):
    model = Cargo
    permiso = P.DEFINIR_META
    menu = "cargos"
    titulo = "Cargos"
    bajada = (
        "La función que cumple una persona. Es lo que decide con qué ítems y "
        "con qué metas se la mide."
    )
    singular = "cargo"
    plural = "cargos"
    genero = "el"
    placeholder = "Nombre, código o descripción"
    rotulo_nuevo = "Nuevo cargo"
    busca = ["codigo", "nombre", "descripcion"]
    orden_inicial = "codigo"

    url_lista = "gestion:cargos"
    url_nueva = "gestion:cargo_nuevo"
    url_editar = "gestion:cargo_editar"
    url_detalle = "gestion:cargo_detalle"
    url_estado = "gestion:cargo_estado"

    filtros = [filtro_estado()]

    columnas = [
        Columna("codigo", "Código", clase="mono"),
        Columna(
            "nombre", "Cargo", orden="nombre", clase="w",
            celda=lambda o: enlace_nombre(
                o, "gestion:cargo_detalle",
                extra=format_html('<span class="t2">{}</span>', o.descripcion),
            ),
        ),
        Columna("usuarios", "Usuarios", orden="", alineado="r",
                valor=lambda o: o.perfiles.filter(activo=True).count()),
        Columna("metas", "Metas", orden="", alineado="r",
                valor=lambda o: o.metas.filter(activo=True).count()),
        Columna("estado", "Estado", orden="activo", celda=chip_estado,
                valor=lambda o: "Activo" if o.activo else "Inactivo"),
    ]

    nota = (
        "<b>El cargo no es el rol.</b> El rol dice qué pantallas puede usar "
        "una persona; el cargo, con qué se le mide. Un verificador y un "
        "funcionario pueden compartir cargo, y dos personas del mismo cargo "
        "pueden tener roles distintos."
    )


class CargoNuevo(CrearMantenedor):
    model = Cargo
    form_class = CargoForm
    permiso = P.DEFINIR_META
    menu = "cargos"
    singular = "cargo"
    plural = "cargos"
    genero = "el"
    url_lista = "gestion:cargos"
    url_detalle = "gestion:cargo_detalle"
    secciones = [
        ("Identificación", "Cómo se llama el cargo.", ["codigo", "nombre"]),
        ("Qué hace", "Con qué se le mide a quien lo ocupa.", ["descripcion"]),
    ]


class CargoEditar(EditarMantenedor):
    model = Cargo
    form_class = CargoForm
    permiso = P.DEFINIR_META
    menu = "cargos"
    singular = "cargo"
    plural = "cargos"
    genero = "el"
    url_lista = "gestion:cargos"
    url_detalle = "gestion:cargo_detalle"
    secciones = CargoNuevo.secciones


class CargoDetalle(DetalleMantenedor):
    model = Cargo
    permiso = P.DEFINIR_META
    menu = "cargos"
    singular = "cargo"
    plural = "cargos"
    genero = "el"
    url_lista = "gestion:cargos"
    url_editar = "gestion:cargo_editar"
    url_estado = "gestion:cargo_estado"
    campos = [
        ("Código", "codigo", {"mono": True}),
        ("Nombre", "nombre"),
        ("Qué hace", "descripcion", {"ancho": True}),
        ("Ítems con meta",
         lambda o: ", ".join(
             sorted({m.item.nombre for m in o.metas.filter(activo=True)})
         ) or "Todavía ninguno",
         {"ancho": True}),
    ]
    kpis = [
        ("Usuarios con este cargo", lambda o: o.perfiles.filter(activo=True).count(),
         "Se miden con sus metas"),
        ("Metas configuradas", lambda o: o.metas.filter(activo=True).count(),
         "En todos los períodos"),
    ]
    pie = "Las metas se configuran por período, en Metas y ponderadores."


class CargoEstado(CambiarEstado):
    model = Cargo
    permiso = P.DEFINIR_META
    url_lista = "gestion:cargos"
    singular = "cargo"
    genero = "el"


# =========================================================================
# Metas y ponderadores
# =========================================================================


def _celda_cumple(meta):
    """Avisa si el cargo no llega a 100 % en ese período."""
    total = meta.periodo.suma_ponderadores(meta.cargo)
    if total == 100:
        return format_html('<span class="chip ok">{} %</span>', meta.ponderador)
    return format_html(
        '{} %<span class="t2">el cargo suma {} %</span>', meta.ponderador, total
    )


class MetasLista(ListaMantenedor):
    model = MetaPeriodo
    permiso = P.DEFINIR_META
    menu = "metas"
    titulo = "Metas y ponderadores"
    bajada = (
        "Cuánto se le exige a cada cargo en cada ítem, dentro de un período. "
        "Los ponderadores de un cargo suman 100 %."
    )
    singular = "meta"
    plural = "metas"
    genero = "la"
    placeholder = "Ítem, cargo o período"
    rotulo_nuevo = "Nueva meta"
    busca = ["item__nombre", "cargo__nombre", "periodo__nombre"]
    orden_inicial = "periodo"

    url_lista = "gestion:metas"
    url_nueva = "gestion:meta_nueva"
    url_editar = "gestion:meta_editar"
    url_detalle = "gestion:meta_detalle"
    url_estado = "gestion:meta_estado"

    filtros = [
        Filtro("periodo", "Período",
               lambda: [(p.pk, p.nombre) for p in Periodo.objects.filter(activo=True)],
               campo="periodo_id", vacio="Todos"),
        Filtro("cargo", "Cargo",
               lambda: [(c.pk, c.nombre) for c in Cargo.objects.filter(activo=True)],
               campo="cargo_id", vacio="Todos"),
        filtro_estado(femenino=True),
    ]

    columnas = [
        Columna("periodo", "Período", orden="periodo__inicio",
                valor=lambda o: o.periodo.nombre),
        Columna("cargo", "Cargo", orden="cargo__nombre", valor=lambda o: o.cargo.nombre),
        Columna("item", "Ítem", orden="item__nombre", clase="w",
                valor=lambda o: o.item.nombre),
        Columna("meta", "Meta", alineado="r",
                valor=lambda o: f"{o.meta} {o.item.get_unidad_display().lower()}"),
        Columna("ponderador", "Ponderador", alineado="r", celda=_celda_cumple,
                valor=lambda o: o.ponderador),
        Columna("estado", "Estado", orden="activo",
                celda=lambda o: chip_estado(o, femenino=True),
                valor=lambda o: "Activa" if o.activo else "Inactiva"),
    ]

    nota = (
        "<b>Cada cargo suma por separado.</b> Un cargo con 100 % está "
        "configurado; uno que no llega todavía se puede completar. Pasarse de "
        "100 % no se guarda: el resultado quedaría calculado sobre una base "
        "distinta de 100."
    )

    def base_queryset(self):
        return MetaPeriodo.objects.select_related("periodo", "cargo", "item")


class MetaNueva(CrearMantenedor):
    model = MetaPeriodo
    form_class = MetaPeriodoForm
    permiso = P.DEFINIR_META
    menu = "metas"
    singular = "meta"
    plural = "metas"
    genero = "la"
    url_lista = "gestion:metas"
    url_detalle = "gestion:meta_detalle"
    lateral = "gestion/_lateral_meta.html"
    secciones = [
        ("A quién y cuándo", "El cruce que define la meta.", ["periodo", "cargo", "item"]),
        ("Cuánto", "La meta va en la unidad del ítem; el ponderador, en puntos porcentuales.",
         ["meta", "ponderador"]),
    ]

    def get_initial(self):
        """Hereda el período y el cargo del listado filtrado."""
        inicial = super().get_initial()
        for campo in ("periodo", "cargo"):
            valor = self.request.GET.get(campo)
            if valor:
                inicial[campo] = valor
        return inicial


class MetaEditar(EditarMantenedor):
    """
    Edición de una meta, salvo si su período ya se cerró.

    El bloqueo vive en la vista y no solo en el formulario porque es una
    regla de negocio, no una comodidad de pantalla: al cerrarse un período
    sus metas quedan congeladas como el registro de con qué reglas se midió.
    Es lo que pide el caso PAR-04 —«P0 mantiene parámetros y resultados
    originales»— y si se pudieran editar, el resultado de un período cerrado
    cambiaría meses después sin que nadie supiera por qué.

    Se comprueba en ``get`` y también en ``post``: esconder el formulario no
    impide enviarlo.
    """

    model = MetaPeriodo
    form_class = MetaPeriodoForm
    permiso = P.DEFINIR_META
    menu = "metas"
    singular = "meta"
    plural = "metas"
    genero = "la"
    url_lista = "gestion:metas"
    url_detalle = "gestion:meta_detalle"
    lateral = "gestion/_lateral_meta.html"
    secciones = MetaNueva.secciones

    def _congelada(self, request):
        """El desvío si la meta pertenece a un período cerrado, o None."""
        meta = self.get_object()
        if meta.periodo.estado == Periodo.Estado.CERRADO:
            anunciar(
                request,
                "Esta meta quedó congelada",
                meta.motivo_bloqueo(),
                icono="error",
            )
            return redirect("gestion:meta_detalle", pk=meta.pk)
        return None

    def get(self, request, *args, **kwargs):
        return self._congelada(request) or super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        return self._congelada(request) or super().post(request, *args, **kwargs)


class MetaDetalle(DetalleMantenedor):
    model = MetaPeriodo
    permiso = P.DEFINIR_META
    menu = "metas"
    singular = "meta"
    plural = "metas"
    genero = "la"
    url_lista = "gestion:metas"
    url_editar = "gestion:meta_editar"
    url_estado = "gestion:meta_estado"
    campos = [
        ("Período", lambda o: o.periodo.nombre),
        ("Cargo", lambda o: o.cargo.nombre),
        ("Ítem", lambda o: o.item.nombre, {"ancho": True}),
        ("Meta", lambda o: f"{o.meta} {o.item.get_unidad_display().lower()}"),
        ("Ponderador", lambda o: f"{o.ponderador} %"),
        ("Suma del cargo en el período",
         lambda o: f"{o.periodo.suma_ponderadores(o.cargo)} %"),
    ]
    pie = "Mientras el período no se cierre, la meta se puede ajustar."

    def get_queryset(self):
        return MetaPeriodo.objects.select_related("periodo", "cargo", "item")

    def get_context_data(self, **kwargs):
        """
        Con el período cerrado, se retira el botón de editar.

        La protección de verdad está en ``MetaEditar``, que rechaza también
        la petición enviada a mano. Esto es lo otro que hay que hacer: no
        ofrecer un botón que después se va a negar. El motivo ya se muestra
        solo, porque el motor del mantenedor publica ``motivo_bloqueo()``.
        """
        ctx = super().get_context_data(**kwargs)
        if ctx["obj"].periodo.estado == Periodo.Estado.CERRADO:
            ctx["url_editar"] = ""
        return ctx


class MetaEstado(CambiarEstado):
    model = MetaPeriodo
    permiso = P.DEFINIR_META
    url_lista = "gestion:metas"
    singular = "meta"
    genero = "la"


# =========================================================================
# Reglas de cálculo
# =========================================================================
# El plan de pruebas deja pendientes de aprobación formal las reglas con que
# se calcula (sección B3), y el requisito RNF-015 exige poder cambiarlas sin
# editar código. Este mantenedor es las dos cosas a la vez: la pantalla donde
# se configuran, y el lugar donde queda escrito que todavía son una
# propuesta y quién las aprobaría.


def _chip_aprobada(regla):
    if regla.aprobada:
        return format_html('<span class="chip ok">Aprobada</span>')
    return format_html('<span class="chip warn">Propuesta</span>')


def _celda_alcance(regla):
    if regla.periodo_id:
        return format_html(
            '{}<span class="t2">solo este período</span>', regla.periodo.nombre,
        )
    return format_html(
        'General<span class="t2">para los períodos sin regla propia</span>'
    )


class ReglasLista(ListaMantenedor):
    model = ReglaCalculo
    permiso = P.CONFIGURAR_PERIODO
    menu = "reglas"
    titulo = "Reglas de cálculo"
    bajada = (
        "Los parámetros con que el sistema calcula: hasta cuánto cuenta un "
        "ítem, desde qué porcentaje se considera realizado, cuándo el "
        "semáforo deja de ser ámbar y cómo se cuentan los días."
    )
    singular = "regla"
    plural = "reglas"
    genero = "la"
    placeholder = "Nombre, período u observación"
    rotulo_nuevo = "Nueva regla"
    busca = ["nombre", "periodo__nombre", "observacion", "aprobada_por"]
    orden_inicial = "nombre"

    url_lista = "gestion:reglas"
    url_nueva = "gestion:regla_nueva"
    url_editar = "gestion:regla_editar"
    url_detalle = "gestion:regla_detalle"
    url_estado = "gestion:regla_estado"

    filtros = [
        Filtro("aprobada", "Situación",
               [("si", "Aprobadas"), ("no", "Propuestas")],
               consulta=lambda v: Q(aprobada=(v == "si")),
               vacio="Todas"),
        filtro_estado(femenino=True),
    ]

    columnas = [
        Columna(
            "nombre", "Regla", orden="nombre", clase="w",
            celda=lambda o: enlace_nombre(
                o, "gestion:regla_detalle",
                extra=format_html('<span class="t2">{}</span>', o.resumen()),
            ),
        ),
        Columna("alcance", "Alcance", orden="periodo__inicio", celda=_celda_alcance,
                valor=lambda o: o.periodo.nombre if o.periodo_id else "General"),
        Columna("tope", "Tope", alineado="r", orden="tope_aporte",
                valor=lambda o: f"{o.tope_aporte} %"),
        Columna("realizado", "Ítem realizado", alineado="r",
                orden="umbral_realizado",
                valor=lambda o: f"desde {o.umbral_realizado} %"),
        Columna("situacion", "Situación", orden="aprobada", celda=_chip_aprobada,
                valor=lambda o: "Aprobada" if o.aprobada else "Propuesta"),
        Columna("estado", "Estado", orden="activo",
                celda=lambda o: chip_estado(o, femenino=True),
                valor=lambda o: "Activa" if o.activo else "Inactiva"),
    ]

    nota = (
        "<b>Mientras una regla no esté aprobada, el sistema calcula igual y "
        "lo dice.</b> Todo resultado obtenido con una regla en estado de "
        "propuesta aparece rotulado como tal. Es lo que permite mostrar "
        "números sin afirmar que son los definitivos."
    )

    def base_queryset(self):
        return ReglaCalculo.objects.select_related("periodo")


SECCIONES_REGLA = [
    ("Identificación", "A qué se aplica esta regla.", ["nombre", "periodo"]),
    ("Cómo se cuenta el cumplimiento",
     "El tope decide si hacer más de la meta se reconoce o no.",
     ["tope_aporte", "umbral_realizado"]),
    ("Semáforo y días",
     "El ámbar se mide como porcentaje de lo esperado a la fecha.",
     ["umbral_ambar", "convencion_dias"]),
    ("Cuándo avisa el sistema",
     "Los umbrales de las alertas. El del avance bajo no está aquí porque es "
     "el mismo del semáforo: con dos valores distintos, el tablero y la "
     "alerta podrían contradecirse sobre la misma persona.",
     ["dias_aviso_vencimiento", "dias_sin_registrar", "dias_evidencia_espera"]),
    ("Respaldo",
     "Una regla aprobada tiene que decir quién la aprobó.",
     ["aprobada", "aprobada_por", "observacion"]),
]


class ReglaNueva(CrearMantenedor):
    model = ReglaCalculo
    form_class = ReglaCalculoForm
    permiso = P.CONFIGURAR_PERIODO
    menu = "reglas"
    singular = "regla"
    plural = "reglas"
    genero = "la"
    url_lista = "gestion:reglas"
    url_detalle = "gestion:regla_detalle"
    secciones = SECCIONES_REGLA


class ReglaEditar(EditarMantenedor):
    model = ReglaCalculo
    form_class = ReglaCalculoForm
    permiso = P.CONFIGURAR_PERIODO
    menu = "reglas"
    singular = "regla"
    plural = "reglas"
    genero = "la"
    url_lista = "gestion:reglas"
    url_detalle = "gestion:regla_detalle"
    secciones = SECCIONES_REGLA


class ReglaDetalle(DetalleMantenedor):
    model = ReglaCalculo
    permiso = P.CONFIGURAR_PERIODO
    menu = "reglas"
    singular = "regla"
    plural = "reglas"
    genero = "la"
    url_lista = "gestion:reglas"
    url_editar = "gestion:regla_editar"
    url_estado = "gestion:regla_estado"
    campos = [
        ("Nombre", "nombre"),
        ("Alcance",
         lambda o: (f"Solo «{o.periodo.nombre}»" if o.periodo_id
                    else "General, para los períodos sin regla propia")),
        ("Tope del cumplimiento", lambda o: f"{o.tope_aporte} %"),
        ("Ítem realizado", lambda o: f"desde el {o.umbral_realizado} %"),
        ("Ámbar", lambda o: f"hasta el {o.umbral_ambar} % de lo esperado"),
        ("Convención de días", lambda o: o.get_convencion_dias_display()),
        ("Avisa de un vencimiento",
         lambda o: f"{o.dias_aviso_vencimiento} días antes"),
        ("Avisa por falta de registros",
         lambda o: f"a los {o.dias_sin_registrar} días sin registrar"),
        ("Avisa por evidencia en espera",
         lambda o: f"a los {o.dias_evidencia_espera} días esperando decisión"),
        ("Situación", lambda o: "Aprobada" if o.aprobada else
         "Propuesta, pendiente de aprobación formal"),
        ("Aprobada por", lambda o: o.aprobada_por or "Todavía nadie"),
        ("De dónde salen los valores",
         lambda o: o.observacion or "Sin observación", {"ancho": True}),
    ]
    pie = (
        "Cambiar un umbral aquí cambia el resultado que muestran las "
        "pantallas, sin tocar código y sin volver a desplegar."
    )

    def get_queryset(self):
        return ReglaCalculo.objects.select_related("periodo")


class ReglaEstado(CambiarEstado):
    model = ReglaCalculo
    permiso = P.CONFIGURAR_PERIODO
    url_lista = "gestion:reglas"
    singular = "regla"
    genero = "la"

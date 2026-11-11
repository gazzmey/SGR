"""
Regalos para niños: campañas, inscripciones y entrega (hoja REGALOS NIÑOS).

· Las **campañas** son del municipio entero y las configura quien configura
  los períodos (coordinador y administrador en los roles de ejemplo).
· **Inscribe y entrega** quien registra atención ciudadana, en su delegación.
· **Consulta** también quien ve el tablero, para saber cuántos regalos hay
  que preparar.

El aviso de duplicado cruza delegaciones a propósito —es la regla de la
matriz: «RUT ya ingresado por delegación XX»—, pero cada delegación solo ve
y modifica sus propias inscripciones.
"""

from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html, format_html_join
from django.views import View

from atencion.forms_regalos import CampanaForm, InscripcionForm
from atencion.modelos_regalos import CampanaRegalos, InscripcionRegalo
from atencion.models import limpiar_rut, rut_valido
from comun import permisos as P
from comun.contexto import delegacion_activa
from comun.mantenedor import (
    CambiarEstado,
    Columna,
    CrearMantenedor,
    DetalleMantenedor,
    EditarMantenedor,
    Filtro,
    ListaMantenedor,
    auditar,
    chip_estado,
    enlace_nombre,
    filtro_estado,
)
from comun.permisos import redirect_al_login, tiene_permiso
from comun.resultado import anunciar


def puede_ver(usuario):
    return tiene_permiso(usuario, P.REGISTRAR_ATENCION) or tiene_permiso(usuario, P.VER_TABLERO)


class _Ver:
    """Entra quien atiende público o quien ve el tablero."""

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_al_login(request)
        if not puede_ver(request.user):
            raise PermissionDenied(
                "Los regalos los llevan quienes atienden público y quienes conducen la delegación.")
        return super().dispatch(request, *args, **kwargs)


def _quien(usuario):
    return (usuario.get_full_name() or usuario.get_username()) if usuario else "—"


# =========================================================================
# Campañas
# =========================================================================


class CampanasLista(ListaMantenedor):
    model = CampanaRegalos
    permiso = P.CONFIGURAR_PERIODO
    menu = "campanas"
    titulo = "Campañas de regalos"
    bajada = (
        "Navidad, Día del Niño y Aniversario. Cada campaña vale para todas las "
        "delegaciones: un niño se inscribe una sola vez, en cualquiera de ellas."
    )
    singular = "campaña"
    plural = "campañas"
    genero = "la"
    placeholder = "Código, año u observación"
    rotulo_nuevo = "Nueva campaña"
    busca = ["codigo", "observacion"]
    orden_inicial = "-anio"
    url_lista = "atencion:campanas"
    url_nueva = "atencion:campana_nueva"
    url_editar = "atencion:campana_editar"
    url_detalle = "atencion:campana_detalle"
    url_estado = "atencion:campana_estado"
    filtros = [
        Filtro("evento", "Evento", CampanaRegalos.Evento.choices, vacio="Todos"),
        filtro_estado(femenino=True),
    ]
    columnas = [
        Columna("codigo", "Código", clase="mono"),
        Columna("anio", "Campaña", orden="anio", clase="w",
                celda=lambda o: enlace_nombre(
                    o, "atencion:campana_detalle", femenino=True,
                    extra=format_html('<span class="t2">Hasta los {} años</span>', o.edad_maxima)),
                valor=lambda o: o.nombre),
        Columna("inscripcion_hasta", "Inscripciones",
                valor=lambda o: (f"hasta el {o.inscripcion_hasta:%d-%m-%Y}"
                                 if o.inscripcion_hasta else "abiertas")),
        Columna("inscritos", "Inscritos", orden="", alineado="r",
                valor=lambda o: o.inscripciones.filter(activo=True).count()),
        Columna("estado", "Estado", orden="activo",
                celda=lambda o: chip_estado(o, femenino=True),
                valor=lambda o: "Activa" if o.activo else "Inactiva"),
    ]
    nota = (
        "<b>Una campaña desactivada cierra las inscripciones</b>, pero sus "
        "inscripciones y entregas se conservan."
    )


SECCIONES_CAMPANA = [
    ("Qué campaña", "El evento y el año. No puede haber dos del mismo evento en un año.",
     ["evento", "anio", "edad_maxima"]),
    ("Fechas", "Hasta cuándo se inscribe y cuándo se entrega.",
     ["inscripcion_hasta", "fecha_entrega", "observacion"]),
]


class CampanaNueva(CrearMantenedor):
    model = CampanaRegalos
    form_class = CampanaForm
    permiso = P.CONFIGURAR_PERIODO
    menu = "campanas"
    singular = "campaña"
    plural = "campañas"
    genero = "la"
    url_lista = "atencion:campanas"
    url_detalle = "atencion:campana_detalle"
    secciones = SECCIONES_CAMPANA


class CampanaEditar(EditarMantenedor):
    model = CampanaRegalos
    form_class = CampanaForm
    permiso = P.CONFIGURAR_PERIODO
    menu = "campanas"
    singular = "campaña"
    plural = "campañas"
    genero = "la"
    url_lista = "atencion:campanas"
    url_detalle = "atencion:campana_detalle"
    secciones = SECCIONES_CAMPANA


def _por_tramo(consulta):
    """Inscritos y entregados por tramo, en el orden de los tramos."""
    filas = {
        f["tramo_edad"]: f for f in
        consulta.values("tramo_edad").annotate(
            inscritos=Count("pk"), entregados=Count("pk", filter=Q(entregado_el__isnull=False)))
    }
    salida = []
    for valor, texto in InscripcionRegalo.Tramo.choices:
        if valor not in filas:
            continue
        inscritos, entregados = filas[valor]["inscritos"], filas[valor]["entregados"]
        salida.append({"tramo": texto, "inscritos": inscritos, "entregados": entregados,
                       "pendientes": inscritos - entregados})
    return salida


def _por_delegacion_html(campana):
    filas = (
        campana.inscripciones.filter(activo=True)
        .values("delegacion__nombre")
        .annotate(n=Count("pk"), e=Count("pk", filter=Q(entregado_el__isnull=False)))
        .order_by("delegacion__nombre")
    )
    if not filas:
        return "Todavía no hay inscritos."
    return format_html_join(
        "", "<div>{}: <b>{}</b> inscritos · {} entregados</div>",
        ((f["delegacion__nombre"], f["n"], f["e"]) for f in filas),
    )


class CampanaDetalle(DetalleMantenedor):
    model = CampanaRegalos
    permiso = P.CONFIGURAR_PERIODO
    menu = "campanas"
    singular = "campaña"
    plural = "campañas"
    genero = "la"
    url_lista = "atencion:campanas"
    url_editar = "atencion:campana_editar"
    url_estado = "atencion:campana_estado"
    campos = [
        ("Código", "codigo", {"mono": True}),
        ("Campaña", lambda o: o.nombre),
        ("Edad máxima", lambda o: f"{o.edad_maxima} años"),
        ("Inscripciones", lambda o: (f"hasta el {o.inscripcion_hasta:%d-%m-%Y}"
                                     if o.inscripcion_hasta else "abiertas mientras esté activa")),
        ("Entrega", lambda o: o.fecha_entrega.strftime("%d-%m-%Y") if o.fecha_entrega else "Por definir"),
        ("Por delegación", _por_delegacion_html, {"ancho": True, "html": True}),
        ("Observación", lambda o: o.observacion or "—", {"ancho": True}),
    ]
    kpis = [
        ("Inscritos", lambda o: o.inscripciones.filter(activo=True).count(),
         "En todas las delegaciones"),
        ("Entregados", lambda o: o.inscripciones.filter(activo=True, entregado_el__isnull=False).count(),
         "Regalos ya retirados"),
    ]
    pie = "Las inscripciones se hacen desde Comunidad → Regalos para niños."


class CampanaEstado(CambiarEstado):
    model = CampanaRegalos
    permiso = P.CONFIGURAR_PERIODO
    url_lista = "atencion:campanas"
    singular = "campaña"
    genero = "la"


# =========================================================================
# Inscripciones
# =========================================================================


def _campanas():
    return [(c.pk, c.nombre) for c in CampanaRegalos.objects.order_by("-anio", "evento")]


def _chip_entrega(o):
    if o.entregado:
        return format_html('<span class="chip ok">Entregado</span><span class="t2">{}</span>',
                           o.entregado_el.strftime("%d-%m-%Y"))
    if not o.activo:
        return format_html('<span class="chip off"><span class="t">Anulada</span></span>')
    return format_html('<span class="chip warn">Por entregar</span>')


class RegalosLista(_Ver, ListaMantenedor):
    model = InscripcionRegalo
    campo_delegacion = "delegacion_id"
    menu = "regalos"
    titulo = "Regalos para niños"
    bajada = (
        "Los niños inscritos en cada campaña. Un RUT se inscribe una sola vez "
        "por campaña, en cualquier delegación."
    )
    singular = "inscripción"
    plural = "inscripciones"
    genero = "la"
    placeholder = "RUT completo del niño o del adulto, o código"
    rotulo_nuevo = "Inscribir"
    busca = ["codigo"]
    orden_inicial = "-registrada"
    url_lista = "atencion:regalos"
    url_nueva = "atencion:regalo_nuevo"
    url_editar = "atencion:regalo_editar"
    url_detalle = "atencion:regalo"
    url_estado = "atencion:regalo_estado"

    filtros = [
        Filtro("campana", "Campaña", _campanas, vacio="Todas"),
        Filtro("entrega", "Entrega",
               [("pendientes", "Por entregar"), ("entregados", "Entregados")],
               consulta=lambda v: Q(entregado_el__isnull=(v == "pendientes")),
               vacio="Todas"),
        Filtro("tramo", "Tramo", InscripcionRegalo.Tramo.choices, campo="tramo_edad",
               vacio="Todos"),
        filtro_estado(femenino=True),
    ]

    columnas = [
        Columna("codigo", "Código", clase="mono"),
        Columna("rut_menor", "Niño o niña", orden="", clase="w",
                celda=lambda o: enlace_nombre(
                    o, "atencion:regalo", femenino=True,
                    extra=format_html('<span class="t2">{}</span>', o.get_tramo_edad_display())),
                valor=lambda o: o.rut_enmascarado),
        Columna("campana", "Campaña", orden="campana__anio", valor=lambda o: o.campana.nombre),
        Columna("apoderado", "Lo inscribió", orden="apoderado__nombre",
                celda=lambda o: format_html('{}<span class="t2">{}</span>', o.apoderado.nombre,
                                            timezone.localtime(o.registrada).strftime("%d-%m-%Y")),
                valor=lambda o: o.apoderado.nombre),
        Columna("entregado_el", "Entrega", celda=_chip_entrega,
                valor=lambda o: (o.entregado_el.strftime("%d-%m-%Y") if o.entregado
                                 else ("Anulada" if not o.activo else "Por entregar"))),
    ]

    excel_columnas = [
        Columna("codigo", "Código"),
        Columna("rut", "RUT del niño (enmascarado)", valor=lambda o: o.rut_enmascarado),
        Columna("tramo", "Tramo de edad", valor=lambda o: o.get_tramo_edad_display()),
        Columna("campana", "Campaña", valor=lambda o: o.campana.nombre),
        Columna("delegacion", "Delegación", valor=lambda o: o.delegacion.nombre),
        Columna("apoderado", "Adulto que lo inscribió", valor=lambda o: o.apoderado.nombre),
        Columna("telefono", "Teléfono del adulto", valor=lambda o: o.apoderado.telefono),
        Columna("registrada", "Inscrito el",
                valor=lambda o: timezone.localtime(o.registrada).strftime("%d-%m-%Y")),
        Columna("entregado", "Entregado el",
                valor=lambda o: o.entregado_el.strftime("%d-%m-%Y") if o.entregado else ""),
        Columna("estado", "Estado", valor=lambda o: "Vigente" if o.activo else "Anulada"),
    ]

    nota = (
        "<b>Del niño solo se guarda el RUT y el tramo de edad.</b> El RUT "
        "sirve para que no reciba dos regalos y aparece completo solo en su "
        "ficha, donde se verifica al entregar. Anular una inscripción libera "
        "el RUT para que otra delegación lo inscriba."
    )

    def base_queryset(self):
        return InscripcionRegalo.objects.select_related("campana", "apoderado", "delegacion")

    def _buscar(self, consulta):
        termino = (self.request.GET.get("q") or "").strip()
        if not termino:
            return consulta
        # El RUT se busca completo y exacto, sin puntos: buscar por pedazos
        # permitiría ir adivinando RUT de niños de a un dígito.
        rut = limpiar_rut(termino)
        if rut_valido(rut):
            return consulta.filter(Q(rut_menor=rut) | Q(apoderado__rut=rut))
        return consulta.filter(codigo__icontains=termino)

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        campana = None
        pedida = self.request.GET.get("campana")
        if pedida:
            campana = CampanaRegalos.objects.filter(pk=pedida).first()
        if campana is None:
            campana = CampanaRegalos.objects.filter(activo=True).order_by("-anio").first()
        if campana is not None:
            consulta = self.limitar(campana.inscripciones.filter(activo=True))
            contexto.update({
                "antes_del_listado": "atencion/_resumen_regalos.html",
                "campana": campana,
                "por_tramo": _por_tramo(consulta),
                "total_inscritos": consulta.count(),
                "total_entregados": consulta.filter(entregado_el__isnull=False).count(),
                "abierta": campana.abierta(timezone.localdate()),
            })
        if not tiene_permiso(self.request.user, P.REGISTRAR_ATENCION):
            contexto["url_nueva"] = ""
            contexto["url_editar"] = ""
            contexto["url_estado"] = ""
        return contexto


class _Inscribe:
    """Inscribir, corregir, entregar y anular: quien registra atención."""

    permiso = P.REGISTRAR_ATENCION
    campo_delegacion = "delegacion_id"

    def get_form_kwargs(self):
        datos = super().get_form_kwargs()
        perfil = P.perfil_de(self.request.user)
        datos["delegacion"] = delegacion_activa(self.request) or getattr(perfil, "delegacion", None)
        datos["usuario"] = self.request.user
        return datos


SECCIONES_INSCRIPCION = [
    ("El niño o niña", "Solo el RUT y el tramo de edad: no se guarda su nombre.",
     ["campana", "rut_menor", "tramo_edad"]),
    ("Quién lo inscribe", "El adulto al que se llama para retirar el regalo.",
     ["rut_apoderado", "nombre_apoderado", "telefono_apoderado"]),
]


class RegaloNuevo(_Inscribe, CrearMantenedor):
    model = InscripcionRegalo
    form_class = InscripcionForm
    menu = "regalos"
    singular = "inscripción"
    plural = "inscripciones"
    genero = "la"
    url_lista = "atencion:regalos"
    url_detalle = "atencion:regalo"
    lateral = "atencion/_lateral_regalo.html"
    secciones = SECCIONES_INSCRIPCION


class RegaloEditar(_Inscribe, EditarMantenedor):
    model = InscripcionRegalo
    form_class = InscripcionForm
    menu = "regalos"
    singular = "inscripción"
    plural = "inscripciones"
    genero = "la"
    url_lista = "atencion:regalos"
    url_detalle = "atencion:regalo"
    lateral = "atencion/_lateral_regalo.html"
    secciones = SECCIONES_INSCRIPCION

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            obj = InscripcionRegalo.objects.filter(pk=kwargs.get("pk")).first()
            if obj is not None and obj.entregado:
                anunciar(request, "Ya se entregó",
                         "Una inscripción con el regalo entregado no se corrige: es el "
                         "registro de lo que se entregó.", icono="warning")
                return redirect("atencion:regalo", pk=obj.pk)
        return super().dispatch(request, *args, **kwargs)


class RegaloDetalle(_Ver, DetalleMantenedor):
    model = InscripcionRegalo
    campo_delegacion = "delegacion_id"
    template_name = "atencion/regalo_detalle.html"
    menu = "regalos"
    singular = "inscripción"
    plural = "inscripciones"
    genero = "la"
    url_lista = "atencion:regalos"
    url_editar = "atencion:regalo_editar"
    url_estado = "atencion:regalo_estado"
    campos = [
        ("Código", "codigo", {"mono": True}),
        ("Campaña", lambda o: o.campana.nombre),
        ("RUT del niño o niña", "rut_menor", {"mono": True}),
        ("Tramo de edad", "tramo_edad"),
        ("Adulto que lo inscribió", lambda o: f"{o.apoderado.nombre} · {o.apoderado.rut}"),
        ("Teléfono del adulto", lambda o: o.apoderado.telefono or "—"),
        ("Delegación", lambda o: o.delegacion.nombre),
        ("Inscrito", lambda o: "%s, por %s" % (
            timezone.localtime(o.registrada).strftime("%d-%m-%Y %H:%M"), _quien(o.registrado_por))),
        ("Entrega", lambda o: ("%s, por %s" % (o.entregado_el.strftime("%d-%m-%Y"),
                                               _quien(o.entregado_por))
                               if o.entregado else "Por entregar")),
    ]
    pie = (
        "El RUT completo se muestra solo aquí, para verificarlo al entregar. "
        "En los listados y en la exportación va enmascarado."
    )

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        puede = tiene_permiso(self.request.user, P.REGISTRAR_ATENCION)
        contexto["puede_entregar"] = puede
        if not puede:
            contexto["url_editar"] = ""
        return contexto


class RegaloEntregar(View):
    """Marca el regalo como entregado. Solo POST, y una sola vez."""

    def post(self, request, pk):
        if not request.user.is_authenticated:
            return redirect_al_login(request)
        if not tiene_permiso(request.user, P.REGISTRAR_ATENCION):
            raise PermissionDenied("No tienes permiso para entregar regalos.")
        consulta = InscripcionRegalo.objects.all()
        perfil = P.perfil_de(request.user)
        if perfil is not None:
            consulta = consulta.filter(delegacion__in=perfil.delegaciones_visibles())
        inscripcion = get_object_or_404(consulta, pk=pk)
        if not inscripcion.activo:
            anunciar(request, "Inscripción anulada",
                     "Una inscripción anulada no se entrega.", icono="error")
        elif inscripcion.entregado:
            anunciar(request, "Ya estaba entregado",
                     f"Se entregó el {inscripcion.entregado_el:%d-%m-%Y}.", icono="warning")
        else:
            inscripcion.entregado_el = timezone.localdate()
            inscripcion.entregado_por = request.user
            inscripcion.save(update_fields=["entregado_el", "entregado_por"])
            auditar(request, "estado", inscripcion, entidad="Inscripción de regalo",
                    antes="por entregar", despues="entregado")
            anunciar(request, "Regalo entregado",
                     f"{inscripcion.codigo} queda entregado hoy, a nombre de "
                     f"{inscripcion.apoderado.nombre}.")
        return redirect("atencion:regalo", pk=inscripcion.pk)


class RegaloEstado(CambiarEstado):
    model = InscripcionRegalo
    permiso = P.REGISTRAR_ATENCION
    campo_delegacion = "delegacion_id"
    url_lista = "atencion:regalos"
    singular = "inscripción"
    genero = "la"

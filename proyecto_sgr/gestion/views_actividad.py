"""
Mis actividades, su registro, y la cola de validación del verificador.

La cadena que implementan estas vistas es la del sistema completo: registrar
→ adjuntar → validar → sumar. Cada paso tiene su propia comprobación de
permiso y su propio efecto sobre el estado de la actividad, y el estado es
lo único que decide si la actividad puntúa.
"""

from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html
from django.views import View

from comun import permisos as P
from comun.auditoria import registrar
from comun.contexto import delegacion_activa
from comun.mantenedor import Columna, Filtro, ListaMantenedor
from comun.models import EventoAuditoria
from comun.permisos import redirect_al_login, tiene_permiso
from comun.resultado import anunciar
from gestion.forms_actividad import ActividadForm, EvidenciaForm, RechazoForm
from gestion.modelos_actividad import Actividad, Evidencia
from gestion.models import Periodo


# =========================================================================
# Apoyo
# =========================================================================


CHIP_ACTIVIDAD = {
    Actividad.Estado.BORRADOR: ("line", "Sin evidencia"),
    Actividad.Estado.PENDIENTE: ("warn", "Pendiente"),
    Actividad.Estado.APROBADA: ("ok", "Aprobada"),
    Actividad.Estado.RECHAZADA: ("bad", "Rechazada"),
    Actividad.Estado.ANULADA: ("off", "Anulada"),
}


def _chip_actividad(actividad):
    clase, texto = CHIP_ACTIVIDAD[actividad.estado]
    if clase == "off":
        return format_html('<span class="chip off"><span class="t">{}</span></span>', texto)
    return format_html('<span class="chip {}">{}</span>', clase, texto)


def periodo_abierto():
    """El período en curso, o None si no hay ninguno abierto."""
    return Periodo.objects.filter(
        activo=True, estado=Periodo.Estado.ABIERTO,
    ).order_by("-inicio").first()


def _exigir(request, permiso, queja):
    if not request.user.is_authenticated:
        return redirect_al_login(request)
    if not tiene_permiso(request.user, permiso):
        raise PermissionDenied(queja)
    return None


# =========================================================================
# Mis actividades
# =========================================================================


class MisActividades(ListaMantenedor):
    """
    Lo que registró quien está mirando.

    No es «todas las actividades»: cada persona ve las suyas. Quien supervisa
    tiene el tablero y la cola de validación, que son otra cosa.
    """

    model = Actividad
    permiso = P.REGISTRAR_ACTIVIDAD
    menu = "actividades"
    titulo = "Mis actividades"
    bajada = (
        "Lo que registraste en el período. Una actividad suma a tu meta "
        "cuando un verificador aprueba su evidencia."
    )
    singular = "actividad"
    plural = "actividades"
    genero = "la"
    placeholder = "Código, acción, detalle o contacto"
    rotulo_nuevo = "Registrar actividad"
    busca = ["codigo", "accion", "detalle", "contacto"]
    orden_inicial = "-fecha"

    url_lista = "gestion:actividades"
    url_nueva = "gestion:actividad_nueva"
    url_editar = "gestion:actividad_detalle"
    url_detalle = "gestion:actividad_detalle"
    url_estado = ""

    filtros = [
        Filtro("situacion", "Situación", Actividad.Estado.choices,
               campo="estado", vacio="Todas"),
        Filtro("periodo", "Período",
               lambda: [(p.pk, p.nombre) for p in Periodo.objects.filter(activo=True)],
               campo="periodo_id", vacio="Todos"),
    ]

    columnas = [
        Columna("codigo", "Código", clase="mono"),
        Columna("fecha", "Fecha", valor=lambda o: f"{o.fecha:%d-%m-%Y}"),
        Columna("accion", "Acción", orden="accion", clase="w",
                celda=lambda o: format_html(
                    '<a class="link" href="{}">{}</a><span class="t2">{}</span>',
                    reverse("gestion:actividad_detalle", args=[o.pk]),
                    o.accion, o.item.nombre,
                ),
                valor=lambda o: o.accion),
        Columna("item", "Suma a", orden="item__nombre", valor=lambda o: o.item.nombre),
        Columna("cantidad", "Acredita", alineado="r", orden="cantidad",
                valor=lambda o: f"{o.cantidad} {o.item.get_unidad_display().lower()}"),
        Columna("situacion", "Situación", orden="estado", celda=_chip_actividad,
                valor=lambda o: o.get_estado_display()),
    ]

    nota = (
        "<b>Registrar no es puntuar.</b> Una actividad empieza sin evidencia; "
        "cuando le adjuntas una queda pendiente, y solo suma a tu meta cuando "
        "el verificador la aprueba. Si te la rechazan, corriges y vuelves a "
        "enviarla."
    )

    def base_queryset(self):
        return (
            Actividad.objects
            .filter(funcionario=self.request.user)
            .select_related("item", "periodo", "delegacion")
        )


def actividad_nueva(request):
    """Registra una actividad en el período abierto."""
    desvio = _exigir(request, P.REGISTRAR_ACTIVIDAD,
                     "No tienes permiso para registrar actividades.")
    if desvio:
        return desvio

    perfil = P.perfil_de(request.user)
    periodo = periodo_abierto()

    if perfil is None or periodo is None or perfil.cargo_asignado is None:
        return render(request, "gestion/actividad_imposible.html", {
            "menu": "actividades",
            "perfil": perfil,
            "periodo": periodo,
        })

    formulario = ActividadForm(request.POST or None, perfil=perfil, periodo=periodo)

    if request.method == "POST" and formulario.is_valid():
        actividad = formulario.save()
        anunciar(
            request,
            "Actividad registrada",
            "Quedó con el código %s. Todavía no suma a tu meta: adjúntale una "
            "evidencia y espera la validación." % actividad.codigo,
            acciones=[
                ("Adjuntar la evidencia",
                 reverse("gestion:evidencia_nueva", args=[actividad.pk])),
                ("Ver mis actividades", reverse("gestion:actividades")),
            ],
        )
        return redirect("gestion:actividad_detalle", pk=actividad.pk)

    return render(request, "gestion/actividad_form.html", {
        "menu": "actividades",
        "form": formulario,
        "periodo": periodo,
        "perfil": perfil,
    })


def actividad_detalle(request, pk):
    """Ficha de la actividad con sus evidencias."""
    desvio = _exigir(request, P.REGISTRAR_ACTIVIDAD, "No tienes permiso para verla.")
    if desvio:
        return desvio

    actividad = get_object_or_404(
        Actividad.objects.select_related("item", "periodo", "delegacion", "funcionario"),
        pk=pk,
    )
    # Cada quien ve lo suyo; quien valida llega por la cola de validación.
    if actividad.funcionario_id != request.user.id and not tiene_permiso(
            request.user, P.VALIDAR_EVIDENCIA):
        raise PermissionDenied("Esa actividad no es tuya.")

    return render(request, "gestion/actividad_detalle.html", {
        "menu": "actividades",
        "obj": actividad,
        "evidencias": actividad.evidencias.select_related("autor", "verificador"),
        "puede_adjuntar": (
            actividad.funcionario_id == request.user.id
            and actividad.estado in {Actividad.Estado.BORRADOR, Actividad.Estado.RECHAZADA}
            and tiene_permiso(request.user, P.ADJUNTAR_EVIDENCIA)
        ),
    })


def evidencia_nueva(request, pk):
    """Adjunta la evidencia de una actividad propia."""
    desvio = _exigir(request, P.ADJUNTAR_EVIDENCIA,
                     "No tienes permiso para adjuntar evidencias.")
    if desvio:
        return desvio

    actividad = get_object_or_404(Actividad, pk=pk)
    if actividad.funcionario_id != request.user.id:
        raise PermissionDenied("Esa actividad no es tuya.")
    if actividad.estado not in {Actividad.Estado.BORRADOR, Actividad.Estado.RECHAZADA}:
        anunciar(request, "No corresponde adjuntar ahora",
                 "La actividad está %s." % actividad.get_estado_display().lower(),
                 icono="warning")
        return redirect("gestion:actividad_detalle", pk=pk)

    formulario = EvidenciaForm(request.POST or None,
                               actividad=actividad, autor=request.user)

    if request.method == "POST" and formulario.is_valid():
        evidencia = formulario.save()
        actividad.estado = Actividad.Estado.PENDIENTE
        actividad.save(update_fields=["estado"])
        anunciar(
            request,
            "Evidencia adjuntada",
            "Quedó con el código %s y la actividad pasó a pendiente de "
            "validación." % evidencia.codigo,
        )
        return redirect("gestion:actividad_detalle", pk=pk)

    return render(request, "gestion/evidencia_form.html", {
        "menu": "actividades",
        "form": formulario,
        "actividad": actividad,
    })


# =========================================================================
# Validar evidencias
# =========================================================================


class ColaValidacion(ListaMantenedor):
    """
    Lo que el verificador tiene por revisar.

    Se limita a su delegación activa: un verificador valida lo de su
    delegación, no lo de todas. Quien tenga alcance «todas» las ve todas,
    porque su rol se lo autoriza.
    """

    model = Evidencia
    permiso = P.VALIDAR_EVIDENCIA
    menu = "validar"
    titulo = "Validar evidencias"
    bajada = (
        "Las evidencias que esperan decisión. Aprobar hace que su actividad "
        "sume a la meta; rechazar la devuelve con un motivo."
    )
    singular = "evidencia"
    plural = "evidencias"
    genero = "la"
    placeholder = "Código, descripción o referencia"
    rotulo_nuevo = ""
    busca = ["codigo", "descripcion", "referencia", "actividad__accion"]
    orden_inicial = "creada"

    url_lista = "gestion:validar"
    url_nueva = ""
    url_editar = "gestion:evidencia_detalle"
    url_detalle = "gestion:evidencia_detalle"
    url_estado = ""

    # Por omisión, solo lo que falta decidir. Las ya decididas se consultan
    # eligiéndolas en el filtro: la pantalla es una cola de trabajo, y una
    # cola que muestra lo ya hecho deja de servir para trabajar.
    filtros = [
        Filtro("decision", "Decisión",
               [("aprobada", "Aprobadas"), ("rechazada", "Rechazadas"),
                ("todas", "Todas")],
               consulta=lambda v: Q() if v == "todas" else Q(decision=v),
               vacio="Solo pendientes"),
    ]

    columnas = [
        Columna("codigo", "Código", clase="mono"),
        Columna("actividad", "Actividad", orden="actividad__accion", clase="w",
                celda=lambda o: format_html(
                    '<a class="link" href="{}">{}</a><span class="t2">{} · {}</span>',
                    reverse("gestion:evidencia_detalle", args=[o.pk]),
                    o.actividad.accion, o.descripcion,
                    o.actividad.item.nombre,
                ),
                valor=lambda o: o.actividad.accion),
        Columna("quien", "Quién la cargó", orden="autor__first_name",
                valor=lambda o: o.autor.get_full_name() or o.autor.get_username()),
        Columna("creada", "Cargada", valor=lambda o: f"{o.creada:%d-%m-%Y %H:%M}"),
        Columna("decision", "Decisión", orden="decision",
                celda=lambda o: _chip_decision(o),
                valor=lambda o: o.get_decision_display()),
    ]

    nota = (
        "<b>Una decisión por evidencia.</b> Si dos verificadores abren la "
        "misma a la vez, el segundo encuentra que ya está decidida y el "
        "sistema no la cuenta dos veces."
    )

    def base_queryset(self):
        consulta = (
            Evidencia.objects
            .select_related("actividad", "actividad__item", "autor", "verificador")
            .filter(anulada=False)
        )

        # Sin filtro elegido, la cola trae solo lo pendiente. Se mira el
        # parámetro de la dirección y no el objeto filtro, para que la regla
        # sea la misma venga la petición de la pantalla o escrita a mano.
        if not self.request.GET.get("decision"):
            consulta = consulta.filter(decision=Evidencia.Decision.PENDIENTE)

        perfil = P.perfil_de(self.request.user)
        if perfil is not None:
            visibles = perfil.delegaciones_visibles().values_list("pk", flat=True)
            consulta = consulta.filter(actividad__delegacion_id__in=list(visibles))
        return consulta


def _chip_decision(evidencia):
    if evidencia.anulada:
        return format_html('<span class="chip off"><span class="t">Anulada</span></span>')
    mapa = {
        Evidencia.Decision.PENDIENTE: ("warn", "Pendiente"),
        Evidencia.Decision.APROBADA: ("ok", "Aprobada"),
        Evidencia.Decision.RECHAZADA: ("bad", "Rechazada"),
    }
    clase, texto = mapa[evidencia.decision]
    return format_html('<span class="chip {}">{}</span>', clase, texto)


def evidencia_detalle(request, pk):
    """Ficha de la evidencia, desde donde se aprueba o se rechaza."""
    desvio = _exigir(request, P.VALIDAR_EVIDENCIA, "No tienes permiso para validar.")
    if desvio:
        return desvio

    evidencia = get_object_or_404(
        Evidencia.objects.select_related(
            "actividad", "actividad__item", "actividad__funcionario",
            "actividad__delegacion", "autor", "verificador"),
        pk=pk,
    )
    return render(request, "gestion/evidencia_detalle.html", {
        "menu": "validar",
        "obj": evidencia,
        "form_rechazo": RechazoForm(),
    })


class DecidirEvidencia(View):
    """
    Aprueba, rechaza o anula una evidencia.

    Es el punto donde una actividad empieza —o deja— de sumar, así que cada
    paso comprueba el estado actual antes de actuar: si otra persona ya
    decidió, se avisa en vez de pisar la decisión. Eso es lo que impide la
    doble puntuación del caso EVI-06.
    """

    def post(self, request, pk, paso):
        desvio = _exigir(request, P.VALIDAR_EVIDENCIA,
                         "No tienes permiso para validar evidencias.")
        if desvio:
            return desvio

        evidencia = get_object_or_404(Evidencia, pk=pk)
        actividad = evidencia.actividad

        if paso in {"aprobar", "rechazar"} and not evidencia.pendiente:
            anunciar(
                request, "Esta evidencia ya estaba decidida",
                "Quedó como «%s». No se cuenta dos veces." % (
                    "anulada" if evidencia.anulada else evidencia.get_decision_display().lower()),
                icono="warning",
            )
            return redirect("gestion:evidencia_detalle", pk=pk)

        if paso == "aprobar":
            evidencia.decision = Evidencia.Decision.APROBADA
            evidencia.verificador = request.user
            evidencia.decidida = timezone.now()
            evidencia.motivo = ""
            evidencia.save(update_fields=["decision", "verificador", "decidida", "motivo"])
            actividad.estado = Actividad.Estado.APROBADA
            actividad.save(update_fields=["estado"])
            registrar(request, EventoAuditoria.Accion.VALIDAR,
                      entidad="Evidencia", objeto=evidencia,
                      antes="pendiente", despues="aprobada",
                      detalle="Actividad %s de %s." % (
                          actividad.codigo,
                          actividad.funcionario.get_full_name()
                          or actividad.funcionario.get_username()),
                      delegacion=actividad.delegacion)
            anunciar(request, "Evidencia aprobada",
                     "«%s» ya suma a la meta de %s." % (
                         actividad.accion,
                         actividad.funcionario.get_full_name() or actividad.funcionario.get_username()))

        elif paso == "rechazar":
            formulario = RechazoForm(request.POST)
            if not formulario.is_valid():
                anunciar(request, "Falta el motivo",
                         formulario.errors["motivo"][0], icono="error")
                return redirect("gestion:evidencia_detalle", pk=pk)
            evidencia.decision = Evidencia.Decision.RECHAZADA
            evidencia.verificador = request.user
            evidencia.decidida = timezone.now()
            evidencia.motivo = formulario.cleaned_data["motivo"]
            evidencia.save(update_fields=["decision", "verificador", "decidida", "motivo"])
            actividad.estado = Actividad.Estado.RECHAZADA
            actividad.save(update_fields=["estado"])
            registrar(request, EventoAuditoria.Accion.RECHAZAR,
                      entidad="Evidencia", objeto=evidencia,
                      antes="pendiente", despues="rechazada",
                      detalle=evidencia.motivo,
                      delegacion=actividad.delegacion)
            anunciar(request, "Evidencia rechazada",
                     "Se devolvió con el motivo. La actividad no suma.",
                     icono="warning")

        elif paso == "anular":
            if evidencia.decision != Evidencia.Decision.APROBADA:
                anunciar(request, "Solo se anula lo aprobado",
                         "Anular revierte una aprobación; esta no lo está.",
                         icono="error")
                return redirect("gestion:evidencia_detalle", pk=pk)
            motivo = (request.POST.get("motivo") or "").strip()
            if len(motivo) < 15:
                anunciar(request, "Falta el motivo de la anulación",
                         "Anular quita puntaje ya otorgado: tiene que quedar "
                         "escrito por qué.", icono="error")
                return redirect("gestion:evidencia_detalle", pk=pk)
            evidencia.anulada = True
            evidencia.motivo_anulacion = motivo
            evidencia.save(update_fields=["anulada", "motivo_anulacion"])
            actividad.estado = Actividad.Estado.ANULADA
            actividad.motivo_anulacion = motivo
            actividad.save(update_fields=["estado", "motivo_anulacion"])
            registrar(request, EventoAuditoria.Accion.ANULAR,
                      entidad="Evidencia", objeto=evidencia,
                      antes="aprobada", despues="anulada", detalle=motivo,
                      delegacion=actividad.delegacion)
            anunciar(request, "Evidencia anulada",
                     "La actividad deja de sumar y queda el motivo en su historial.",
                     icono="warning")
        else:
            raise PermissionDenied("Ese paso no existe.")

        return redirect("gestion:evidencia_detalle", pk=pk)

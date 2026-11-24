"""
La agenda colectiva: consultar, ingresar, avanzar, reasignar y validar.

Quién puede qué, y por qué
--------------------------
**Consultar** no pide permiso especial, solo haber entrado: la agenda es
colectiva, y el sentido de que lo sea es que cualquiera de la delegación pueda
ver qué hay comprometido y con qué plazo. Lo que sí se limita es *qué* se ve:
los compromisos de las delegaciones que el perfil tenga autorizadas.

**Ingresar** y **avanzar** piden el permiso de registrar actividades, que es
el que tiene quien trabaja en terreno.

**Reasignar** pide su propio permiso, ``reasignar_compromiso``. Cambiar de
responsable no es parte del trabajo diario: es una decisión de quien
supervisa, y por eso está separada.

**Avisar que no se llega a la fecha** pide lo mismo que avanzar: lo hace
quien trabaja el compromiso. El aviso le llega al delegado y al responsable
en su *Mi panel*, y solo ellos pueden marcarlo como visto.

**Validar** pide el permiso de validar evidencias. Es el mismo acto —alguien
distinto de quien ejecuta confirma que se cumplió— y tenerlo separado del de
avanzar es lo que impide que una persona cierre y valide su propio
compromiso.
"""

from datetime import date, timedelta

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
from comun.models import EventoAuditoria
from comun.mantenedor import Columna, Filtro, ListaMantenedor
from comun.navegacion import a_donde_volver, con_vuelta, consulta_de_vuelta
from comun.permisos import redirect_al_login, tiene_permiso
from comun.resultado import anunciar
from gestion.forms_agenda import AvisoForm, CompromisoForm, ReasignarForm, TransicionForm
from gestion.modelos_agenda import (
    AvisoCompromiso, CambioCompromiso, Compromiso, DestinatarioAviso,
    destinatarios_del_aviso,
)
from gestion.views_actividad import periodo_abierto


# =========================================================================
# Apoyo
# =========================================================================


CHIP_COMPROMISO = {
    Compromiso.Estado.INGRESADO: ("line", "Ingresado"),
    Compromiso.Estado.PENDIENTE: ("warn", "Pendiente"),
    Compromiso.Estado.EN_PROCESO: ("warn", "En proceso"),
    Compromiso.Estado.REALIZADO: ("ok", "Realizado"),
    Compromiso.Estado.ANULADO: ("off", "Anulado"),
}

#: El paso de la dirección y el estado al que lleva. Están separados del
#: modelo porque son vocabulario de la pantalla: la matriz de transiciones
#: permitidas vive en ``Compromiso.TRANSICIONES`` y es la que manda.
PASOS = {
    "pendiente": Compromiso.Estado.PENDIENTE,
    "proceso": Compromiso.Estado.EN_PROCESO,
    "realizado": Compromiso.Estado.REALIZADO,
    "anulado": Compromiso.Estado.ANULADO,
}

ROTULOS_PASO = {
    "pendiente": "Pasar a pendiente",
    "proceso": "Tomar y poner en proceso",
    "realizado": "Marcar realizado",
    "anulado": "Anular",
}


def _chip_compromiso(compromiso):
    clase, texto = CHIP_COMPROMISO[compromiso.estado]
    if clase == "off":
        return format_html('<span class="chip off"><span class="t">{}</span></span>', texto)
    return format_html('<span class="chip {}">{}</span>', clase, texto)


def _celda_plazo(compromiso):
    """El vencimiento, y cuántos días lleva de atraso si los lleva."""
    fecha = f"{compromiso.vencimiento:%d-%m-%Y}"
    atraso = compromiso.atraso_al_dia()
    if compromiso.cerrado:
        if compromiso.cerrado_con_atraso:
            return format_html(
                '{}<span class="t2">Cerrado con {} {} de atraso</span>',
                fecha, compromiso.dias_de_atraso,
                "día" if compromiso.dias_de_atraso == 1 else "días",
            )
        return format_html('{}<span class="t2">Cerrado a tiempo</span>', fecha)
    if atraso:
        return format_html(
            '{}<span class="t2 bad">Vencido hace {} {}</span>',
            fecha, atraso, "día" if atraso == 1 else "días",
        )
    faltan = compromiso.dias_para_vencer()
    if faltan is not None and faltan <= 3:
        return format_html(
            '{}<span class="t2 warn">{}</span>', fecha,
            "Vence hoy" if faltan == 0 else
            ("Vence mañana" if faltan == 1 else f"Vence en {faltan} días"),
        )
    return fecha


def _exigir(request, permiso, queja):
    if not request.user.is_authenticated:
        return redirect_al_login(request)
    if permiso and not tiene_permiso(request.user, permiso):
        raise PermissionDenied(queja)
    return None


def _visibles_para(usuario):
    """Las delegaciones cuyos compromisos puede ver esa persona."""
    perfil = P.perfil_de(usuario)
    if perfil is None:
        return None          # superusuario: todas
    return list(perfil.delegaciones_visibles().values_list("pk", flat=True))


# =========================================================================
# La agenda
# =========================================================================


def _gente_para_filtro():
    """
    Las personas que tienen compromisos, para el filtro por funcionario.

    Las opciones se arman sin la persona que mira; el listado igual se
    limita después a las delegaciones que cada uno puede ver.
    """
    from django.contrib.auth import get_user_model

    gente = (get_user_model().objects
             .filter(compromisos__isnull=False)
             .distinct().order_by("first_name", "last_name"))
    return [(str(u.pk), u.get_full_name() or u.get_username()) for u in gente]


class Agenda(ListaMantenedor):
    """
    Los compromisos de la delegación, con su plazo y su estado.

    Por omisión muestra los abiertos, porque una agenda sirve para saber qué
    falta. Los cerrados se consultan eligiéndolos en el filtro.
    """

    model = Compromiso
    permiso = None           # consultar la agenda solo pide haber entrado
    menu = "agenda"
    titulo = "Agenda de compromisos"
    bajada = (
        "Lo que la delegación se comprometió a hacer, con su responsable y su "
        "plazo. Un compromiso realizado y validado alimenta la meta de su ítem."
    )
    singular = "compromiso"
    plural = "compromisos"
    genero = "el"
    placeholder = "Código, RUT o nombre del solicitante, territorio o descripción"
    rotulo_nuevo = "Ingresar compromiso"
    busca = ["codigo", "solicitante", "territorio", "descripcion", "apoyo",
             "vecino__rut", "vecino__nombres", "vecino__apellidos"]
    rango_fechas = ("creado__date", "Ingresado")
    orden_inicial = "vencimiento"

    url_lista = "gestion:agenda"
    url_nueva = "gestion:compromiso_nuevo"
    url_editar = "gestion:compromiso_detalle"
    url_detalle = "gestion:compromiso_detalle"
    url_estado = ""

    filtros = [
        Filtro("situacion", "Situación",
               Compromiso.Estado.choices + [("todos", "Todos")],
               consulta=lambda v: (
                   Q() if v == "todos" else Q(estado=v)
               ),
               vacio="Solo abiertos"),
        Filtro("quien", "Responsable",
               lambda: [("mios", "Los míos")] + _gente_para_filtro(),
               consulta=lambda v: Q(responsable_id=v) if v.isdigit() else Q(),
               vacio="De toda la delegación"),
        Filtro("plazo", "Plazo",
               [("vencidos", "Vencidos"), ("semana", "Vencen en 7 días")],
               consulta=lambda v: Q(),      # idem: depende de la fecha de hoy
               vacio="Cualquier plazo"),
        Filtro("origen", "Origen",
               [("interno", "Internos"), ("externo", "Externos")],
               vacio="Internos y externos"),
    ]

    columnas = [
        Columna("codigo", "Código", clase="mono"),
        Columna("solicitante", "Compromiso", orden="solicitante", clase="w",
                celda=lambda o: format_html(
                    '<a class="link" href="{}">{}</a><span class="t2">{}{}{}</span>',
                    reverse("gestion:compromiso_detalle", args=[o.pk]),
                    o.solicitante,
                    f"RUT {o.vecino.rut} · " if o.vecino_id else "",
                    o.territorio,
                    {"interno": " · interno", "externo": " · externo"}.get(o.origen, ""),
                ),
                valor=lambda o: o.solicitante),
        Columna("responsable", "Responsable", orden="responsable__first_name",
                valor=lambda o: o.responsable.get_full_name() or o.responsable.get_username()),
        Columna("vencimiento", "Vence", orden="vencimiento",
                celda=_celda_plazo,
                valor=lambda o: f"{o.vencimiento:%d-%m-%Y}"),
        Columna("situacion", "Situación", orden="estado", celda=_chip_compromiso,
                valor=lambda o: o.get_estado_display()),
    ]

    nota = (
        "<b>Realizado no es lo mismo que puntuado.</b> Un compromiso que exige "
        "validación queda realizado al cerrarlo, pero no alimenta la meta de su "
        "ítem hasta que alguien distinto lo valida."
    )

    def _buscar(self, consulta):
        """
        La búsqueda de siempre, más el RUT escrito con puntos: «12.345.678-5»
        encuentra al vecino guardado como 12345678-5.
        """
        import re

        resultado = super()._buscar(consulta)
        termino = (self.request.GET.get("q") or "").strip()
        sin_puntos = termino.replace(".", "").replace(" ", "").upper()
        if termino and sin_puntos != termino.upper() and re.fullmatch(r"\d{1,8}-?[\dK]?", sin_puntos):
            resultado = resultado | consulta.filter(vecino__rut__icontains=sin_puntos)
        return resultado

    def base_queryset(self):
        consulta = (
            Compromiso.objects
            .select_related("responsable", "item", "delegacion", "periodo",
                            "responsable_original", "vecino")
        )

        visibles = _visibles_para(self.request.user)
        if visibles is not None:
            consulta = consulta.filter(delegacion_id__in=visibles)

        # Sin filtro de situación elegido, solo los abiertos: es lo que hace
        # que la pantalla sirva para trabajar. Se lee el parámetro de la
        # dirección y no el filtro, para que la regla valga igual si alguien
        # escribe la dirección a mano.
        if not self.request.GET.get("situacion"):
            consulta = consulta.filter(estado__in=Compromiso.ABIERTOS)

        if self.request.GET.get("quien") == "mios":
            consulta = consulta.filter(responsable=self.request.user)

        hoy = date.today()
        plazo = self.request.GET.get("plazo")
        if plazo == "vencidos":
            consulta = consulta.filter(
                vencimiento__lt=hoy, estado__in=Compromiso.ABIERTOS)
        elif plazo == "semana":
            consulta = consulta.filter(
                vencimiento__gte=hoy,
                vencimiento__lte=hoy + timedelta(days=7),
                estado__in=Compromiso.ABIERTOS,
            )
        return consulta

    def get_context_data(self, **kwargs):
        from gestion import calculo as C
        from gestion import reglas as R

        contexto = super().get_context_data(**kwargs)
        # El filtro por funcionario ofrece solo a la gente que esta persona
        # puede ver: las de sus delegaciones.
        from django.contrib.auth import get_user_model

        visibles = _visibles_para(self.request.user)
        gente = get_user_model().objects.filter(is_active=True, perfil__activo=True)
        if visibles is not None:
            gente = gente.filter(perfil__delegacion_id__in=visibles)
        for filtro in contexto.get("filtros", []):
            if filtro["clave"] == "quien":
                filtro["opciones"] = [("mios", "Los míos")] + [
                    (str(u.pk), u.get_full_name() or u.get_username())
                    for u in gente.order_by("first_name", "last_name").distinct()]
        contexto["puede_ingresar"] = tiene_permiso(
            self.request.user, P.REGISTRAR_ACTIVIDAD)
        if not contexto["puede_ingresar"]:
            contexto["url_nueva"] = ""

        # El resumen por colaborador (HU-14, hoja TUBO de la matriz): del
        # período abierto y de la delegación activa, que es la que la
        # persona está mirando. La delegación activa ya está comprobada
        # contra las que su perfil autoriza.
        periodo = periodo_abierto()
        delegacion = delegacion_activa(self.request)
        if periodo is not None and delegacion is not None:
            regla = R.vigente(periodo)
            contexto.update({
                "antes_del_listado": "gestion/_resumen_tubo.html",
                "tubo": C.resumen_por_responsable(periodo, [delegacion.pk]),
                "tubo_periodo": periodo,
                "tubo_delegacion": delegacion,
                "tubo_umbral": regla.umbral_realizado,
            })
        return contexto


def compromiso_nuevo(request):
    """Ingresa un compromiso en el período abierto."""
    desvio = _exigir(request, P.REGISTRAR_ACTIVIDAD,
                     "No tienes permiso para ingresar compromisos.")
    if desvio:
        return desvio

    perfil = P.perfil_de(request.user)
    periodo = periodo_abierto()
    delegacion = delegacion_activa(request) or getattr(perfil, "delegacion", None)

    # Desde el mapa de presencia llegan el territorio y su delegación. La
    # delegación se acepta solo si está entre las que el perfil autoriza:
    # si no, se queda la activa, igual que siempre.
    pedida = (request.GET.get("delegacion") or "").strip()
    if perfil is not None and pedida.isdigit():
        delegacion = perfil.delegaciones_visibles().filter(pk=pedida).first() or delegacion
    inicial = {}
    if request.GET.get("territorio"):
        inicial["territorio"] = request.GET["territorio"].strip()[:120]

    if perfil is None or periodo is None or delegacion is None:
        return render(request, "gestion/compromiso_imposible.html", {
            "menu": "agenda",
            "perfil": perfil,
            "periodo": periodo,
            "delegacion": delegacion,
        })

    formulario = CompromisoForm(
        request.POST or None, perfil=perfil, periodo=periodo,
        delegacion=delegacion, initial=inicial,
    )

    if request.method == "POST" and formulario.is_valid():
        compromiso = formulario.save()
        CambioCompromiso.objects.create(
            compromiso=compromiso,
            tipo=CambioCompromiso.Tipo.CREACION,
            estado_nuevo=compromiso.estado,
            responsable_nuevo=compromiso.responsable,
            quien=request.user,
            observacion="Ingresado con vencimiento al %s."
                        % compromiso.vencimiento.strftime("%d-%m-%Y"),
        )
        anunciar(
            request, "Compromiso ingresado",
            "Quedó con el código %s, a nombre de %s y con plazo al %s." % (
                compromiso.codigo,
                compromiso.responsable.get_full_name() or compromiso.responsable.get_username(),
                compromiso.vencimiento.strftime("%d-%m-%Y"),
            ),
            acciones=[("Ver la agenda", reverse("gestion:agenda"))],
        )
        return redirect("gestion:compromiso_detalle", pk=compromiso.pk)

    return render(request, "gestion/compromiso_form.html", {
        "menu": "agenda",
        "form": formulario,
        "periodo": periodo,
        "delegacion": delegacion,
    })


def compromiso_detalle(request, pk):
    """Ficha del compromiso: su estado, su plazo y su historial completo."""
    if not request.user.is_authenticated:
        return redirect_al_login(request)

    compromiso = get_object_or_404(
        Compromiso.objects.select_related(
            "responsable", "responsable_original", "item", "delegacion",
            "periodo", "actividad", "validado_por"),
        pk=pk,
    )

    visibles = _visibles_para(request.user)
    if visibles is not None and compromiso.delegacion_id not in visibles:
        raise PermissionDenied(
            "Ese compromiso es de una delegación que no tienes autorizada."
        )

    puede_avanzar = (tiene_permiso(request.user, P.REGISTRAR_ACTIVIDAD)
                     and compromiso.puede_modificar(request.user))
    pasos = []
    if puede_avanzar:
        for clave, estado in PASOS.items():
            if compromiso.puede_pasar_a(estado):
                pasos.append({
                    "clave": clave,
                    "rotulo": ROTULOS_PASO[clave],
                    "url": reverse("gestion:compromiso_paso", args=[pk, clave]),
                    "peligroso": clave == "anulado",
                })

    from comun.observaciones import hilo

    avisos = list(
        compromiso.avisos.select_related("autor")
        .prefetch_related("destinatarios__usuario")
    )
    for aviso in avisos:
        aviso.mio_sin_ver = next(
            (d for d in aviso.destinatarios.all()
             if d.usuario_id == request.user.pk and d.visto_el is None), None)

    puede_avisar = puede_avanzar and compromiso.abierto
    return render(request, "gestion/compromiso_detalle.html", {
        "menu": "agenda",
        "obj": compromiso,
        "avisos": avisos,
        "form_aviso": AvisoForm() if puede_avisar else None,
        "a_quien_avisa": (
            destinatarios_del_aviso(compromiso, request.user) if puede_avisar else []
        ),
        "hilo": hilo(request, "compromiso", compromiso),
        "cambios": compromiso.cambios.select_related(
            "quien", "responsable_anterior", "responsable_nuevo"),
        "pasos": pasos,
        "solo_consulta": (tiene_permiso(request.user, P.REGISTRAR_ACTIVIDAD)
                          and compromiso.abierto and not puede_avanzar),
        "form_paso": TransicionForm(),
        "form_reasignar": (
            ReasignarForm(compromiso=compromiso)
            if tiene_permiso(request.user, P.REASIGNAR_COMPROMISO)
               and compromiso.abierto
            else None
        ),
        "puede_validar": (
            tiene_permiso(request.user, P.VALIDAR_EVIDENCIA)
            and compromiso.responsable_id != request.user.pk
            and compromiso.estado == Compromiso.Estado.REALIZADO
            and compromiso.requiere_validacion
            and not compromiso.validado
        ),
        "atraso_hoy": compromiso.atraso_al_dia(),

        # A dónde manda «Volver». Por omisión a la agenda, que es donde viven
        # los compromisos; pero si se llegó desde las alertas con ``?volver=``,
        # vuelve a las alertas. Quien está recorriendo una lista de pendientes
        # quiere seguir con el siguiente, no aparecer en otra pantalla.
        "url_volver": a_donde_volver(request, "gestion:agenda"),

        # Lo mismo, en forma de consulta, para que los formularios de la ficha
        # lo arrastren: sin esto el origen se perdería al cerrar o reasignar.
        "vuelta_qs": consulta_de_vuelta(request),
    })


class CompromisoTransicion(View):
    """
    Cambia el estado de un compromiso, si la transición está permitida.

    La comprobación la hace el modelo, con ``impedimento()``, y esta vista
    solo la consulta y traduce el motivo a pantalla. Así la regla es la misma
    venga el cambio de un botón, de una dirección escrita a mano o de la
    consola de administración.
    """

    def post(self, request, pk, paso):
        desvio = _exigir(request, P.REGISTRAR_ACTIVIDAD,
                         "No tienes permiso para mover compromisos.")
        if desvio:
            return desvio

        compromiso = get_object_or_404(Compromiso, pk=pk)
        visibles = _visibles_para(request.user)
        if visibles is not None and compromiso.delegacion_id not in visibles:
            raise PermissionDenied("Ese compromiso no es de tu delegación.")
        if compromiso.abierto and not compromiso.puede_modificar(request.user):
            raise PermissionDenied(
                "Solo el responsable mueve este compromiso. Si no puede "
                "seguir, la delegada lo reasigna.")

        if paso not in PASOS:
            raise PermissionDenied("Ese paso no existe.")
        destino = PASOS[paso]

        impedimento = compromiso.impedimento(destino)
        if impedimento:
            anunciar(request, "No se puede hacer ese cambio", impedimento,
                     icono="error")
            return redirect(con_vuelta(request, "gestion:compromiso_detalle", pk))

        formulario = TransicionForm(
            request.POST, exige_observacion=(destino == Compromiso.Estado.ANULADO),
        )
        if not formulario.is_valid():
            anunciar(request, "Falta la observación",
                     formulario.errors["observacion"][0], icono="error")
            return redirect(con_vuelta(request, "gestion:compromiso_detalle", pk))

        anterior = compromiso.estado
        observacion = formulario.cleaned_data["observacion"]
        campos = ["estado", "observacion"]
        compromiso.estado = destino
        compromiso.observacion = observacion

        # Al cerrar se calcula el atraso una sola vez y se guarda. Después se
        # consulta ese número, no se recalcula: es lo que pide AGE-04 con
        # «cierre conserva atraso».
        if destino in (Compromiso.Estado.REALIZADO, Compromiso.Estado.ANULADO):
            hoy = date.today()
            compromiso.cerrado_el = hoy
            compromiso.dias_de_atraso = max(0, (hoy - compromiso.vencimiento).days)
            compromiso.cerrado_con_atraso = compromiso.dias_de_atraso > 0
            campos += ["cerrado_el", "dias_de_atraso", "cerrado_con_atraso"]

        compromiso.save(update_fields=campos)

        CambioCompromiso.objects.create(
            compromiso=compromiso,
            tipo=CambioCompromiso.Tipo.ESTADO,
            estado_anterior=anterior,
            estado_nuevo=destino,
            quien=request.user,
            observacion=observacion,
        )
        registrar(request, EventoAuditoria.Accion.ESTADO,
                  entidad="Compromiso", objeto=compromiso,
                  antes=dict(Compromiso.Estado.choices)[anterior],
                  despues=dict(Compromiso.Estado.choices)[destino],
                  detalle=observacion)

        if destino == Compromiso.Estado.REALIZADO:
            if compromiso.aporta:
                detalle = "Ya alimenta la meta de «%s»." % compromiso.item
            else:
                detalle = compromiso.motivo_sin_puntaje
            if compromiso.cerrado_con_atraso:
                detalle += " Se cerró con %d %s de atraso, y eso queda en su " \
                           "historial." % (
                               compromiso.dias_de_atraso,
                               "día" if compromiso.dias_de_atraso == 1 else "días")
            anunciar(request, "Compromiso realizado", detalle)
        elif destino == Compromiso.Estado.ANULADO:
            anunciar(request, "Compromiso anulado",
                     "Sale del denominador de la agenda y queda el motivo "
                     "escrito en su historial.", icono="warning")
        else:
            anunciar(request, "Compromiso actualizado",
                     "Pasó a «%s»." % compromiso.get_estado_display().lower())

        return redirect(con_vuelta(request, "gestion:compromiso_detalle", pk))


class CompromisoReasignar(View):
    """Cambia el responsable, conservando el original y el motivo (AGE-06)."""

    def post(self, request, pk):
        desvio = _exigir(request, P.REASIGNAR_COMPROMISO,
                         "No tienes permiso para reasignar compromisos.")
        if desvio:
            return desvio

        compromiso = get_object_or_404(Compromiso, pk=pk)
        visibles = _visibles_para(request.user)
        if visibles is not None and compromiso.delegacion_id not in visibles:
            raise PermissionDenied("Ese compromiso no es de tu delegación.")

        if not compromiso.abierto:
            anunciar(request, "Ya está cerrado",
                     "Un compromiso %s no se reasigna: su historial quedó "
                     "cerrado." % compromiso.get_estado_display().lower(),
                     icono="error")
            return redirect(con_vuelta(request, "gestion:compromiso_detalle", pk))

        formulario = ReasignarForm(request.POST, compromiso=compromiso)
        if not formulario.is_valid():
            primer_error = next(iter(formulario.errors.values()))[0]
            anunciar(request, "No se pudo reasignar", primer_error, icono="error")
            return redirect(con_vuelta(request, "gestion:compromiso_detalle", pk))

        anterior = compromiso.responsable
        nuevo = formulario.cleaned_data["responsable"]
        compromiso.responsable = nuevo
        compromiso.save(update_fields=["responsable"])

        CambioCompromiso.objects.create(
            compromiso=compromiso,
            tipo=CambioCompromiso.Tipo.RESPONSABLE,
            responsable_anterior=anterior,
            responsable_nuevo=nuevo,
            quien=request.user,
            observacion=formulario.cleaned_data["motivo"],
        )

        registrar(request, EventoAuditoria.Accion.REASIGNAR,
                  entidad="Compromiso", objeto=compromiso,
                  antes=anterior.get_full_name() or anterior.get_username(),
                  despues=nuevo.get_full_name() or nuevo.get_username(),
                  detalle=formulario.cleaned_data["motivo"])

        anunciar(
            request, "Compromiso reasignado",
            "Ahora responde %s. Queda registrado que venía de %s, con el "
            "motivo." % (
                nuevo.get_full_name() or nuevo.get_username(),
                anterior.get_full_name() or anterior.get_username(),
            ),
        )
        return redirect(con_vuelta(request, "gestion:compromiso_detalle", pk))


class CompromisoAvisar(View):
    """
    Avisa que el compromiso no se va a cumplir en la fecha (guía 4.2, punto 4).

    Deja el motivo en el historial y le manda el aviso al delegado y al
    responsable, que lo ven en su *Mi panel* hasta marcarlo como visto. No
    cambia el vencimiento ni el atraso: eso queda para otra versión.
    """

    def post(self, request, pk):
        desvio = _exigir(request, P.REGISTRAR_ACTIVIDAD,
                         "No tienes permiso para avisar sobre compromisos.")
        if desvio:
            return desvio

        compromiso = get_object_or_404(
            Compromiso.objects.select_related("delegacion__delegado", "responsable"),
            pk=pk,
        )
        visibles = _visibles_para(request.user)
        if visibles is not None and compromiso.delegacion_id not in visibles:
            raise PermissionDenied("Ese compromiso no es de tu delegación.")
        if compromiso.abierto and compromiso.responsable_id != request.user.pk:
            raise PermissionDenied(
                "Solo el responsable avisa que su compromiso no llega a la fecha.")

        if not compromiso.abierto:
            anunciar(request, "Ya está cerrado",
                     "El compromiso está %s: ya no hay fecha que cumplir."
                     % compromiso.get_estado_display().lower(), icono="error")
            return redirect(con_vuelta(request, "gestion:compromiso_detalle", pk))

        formulario = AvisoForm(request.POST)
        if not formulario.is_valid():
            anunciar(request, "Falta el motivo",
                     formulario.errors["motivo"][0], icono="error")
            return redirect(con_vuelta(request, "gestion:compromiso_detalle", pk))

        motivo = formulario.cleaned_data["motivo"]
        aviso = AvisoCompromiso.objects.create(
            compromiso=compromiso, motivo=motivo, autor=request.user,
            vencimiento=compromiso.vencimiento,
        )
        destinatarios = destinatarios_del_aviso(compromiso, request.user)
        for usuario, por_que in destinatarios:
            DestinatarioAviso.objects.create(aviso=aviso, usuario=usuario, por_que=por_que)

        compromiso.observacion = motivo
        compromiso.save(update_fields=["observacion"])
        CambioCompromiso.objects.create(
            compromiso=compromiso,
            tipo=CambioCompromiso.Tipo.AVISO,
            quien=request.user,
            observacion=motivo,
        )

        nombres = [u.get_full_name() or u.get_username() for u, _ in destinatarios]
        registrar(request, EventoAuditoria.Accion.AVISAR,
                  entidad="Compromiso", objeto=compromiso,
                  despues=", ".join(nombres) or "nadie",
                  detalle=motivo)

        if nombres:
            anunciar(
                request, "Aviso enviado",
                "Le llegó a %s en su Mi panel. La fecha comprometida sigue "
                "siendo el %s." % (
                    " y ".join(nombres) if len(nombres) <= 2
                    else ", ".join(nombres[:-1]) + " y " + nombres[-1],
                    compromiso.vencimiento.strftime("%d-%m-%Y")),
            )
        else:
            anunciar(
                request, "El aviso quedó en la ficha, pero no le llegó a nadie",
                "La delegación %s no tiene delegado asignado y el responsable "
                "eres tú. Pídele al administrador que asigne el delegado en "
                "Administración, Delegaciones." % compromiso.delegacion.nombre,
                icono="warning",
            )
        return redirect(con_vuelta(request, "gestion:compromiso_detalle", pk) + "#avisos")


class AvisoVisto(View):
    """Marca un aviso como visto. Solo puede hacerlo a quien le llegó."""

    def post(self, request, pk, aviso):
        if not request.user.is_authenticated:
            return redirect_al_login(request)

        destinatario = (
            DestinatarioAviso.objects
            .select_related("aviso__compromiso")
            .filter(aviso_id=aviso, aviso__compromiso_id=pk, usuario=request.user)
            .first()
        )
        if destinatario is None:
            raise PermissionDenied("Ese aviso no te llegó a ti.")

        if destinatario.visto_el is None:
            destinatario.visto_el = timezone.now()
            destinatario.save(update_fields=["visto_el"])
            anunciar(request, "Aviso visto",
                     "Ya no aparece en tu Mi panel. Quien avisó ve que lo viste.")
        return redirect(con_vuelta(request, "gestion:compromiso_detalle", pk) + "#avisos")


class CompromisoValidar(View):
    """
    Valida un compromiso realizado, que es lo que lo hace puntuar.

    Tiene su propia comprobación de permiso y su propio paso porque cerrar y
    validar son actos distintos: el caso AGE-05 pide que «cierre sin
    validación requerida no otorga puntaje», y si fueran el mismo paso la
    distinción no existiría.
    """

    def post(self, request, pk):
        desvio = _exigir(request, P.VALIDAR_EVIDENCIA,
                         "No tienes permiso para validar compromisos.")
        if desvio:
            return desvio

        compromiso = get_object_or_404(Compromiso, pk=pk)
        visibles = _visibles_para(request.user)
        if visibles is not None and compromiso.delegacion_id not in visibles:
            raise PermissionDenied("Ese compromiso no es de tu delegación.")
        if compromiso.responsable_id == request.user.pk:
            raise PermissionDenied(
                "Eres el responsable de este compromiso: lo valida otra "
                "persona. Nadie valida su propio trabajo."
            )

        if compromiso.estado != Compromiso.Estado.REALIZADO:
            anunciar(request, "Todavía no corresponde validar",
                     "El compromiso está «%s». Se valida una vez realizado."
                     % compromiso.get_estado_display().lower(), icono="error")
            return redirect(con_vuelta(request, "gestion:compromiso_detalle", pk))

        if compromiso.validado:
            anunciar(request, "Ya estaba validado",
                     "Lo validó %s. No se cuenta dos veces." % (
                         compromiso.validado_por.get_full_name()
                         if compromiso.validado_por else "otra persona"),
                     icono="warning")
            return redirect(con_vuelta(request, "gestion:compromiso_detalle", pk))

        compromiso.validado = True
        compromiso.validado_por = request.user
        compromiso.validado_el = timezone.now()
        compromiso.save(update_fields=["validado", "validado_por", "validado_el"])

        CambioCompromiso.objects.create(
            compromiso=compromiso,
            tipo=CambioCompromiso.Tipo.VALIDACION,
            quien=request.user,
            observacion="Se confirmó el cumplimiento.",
        )

        registrar(request, EventoAuditoria.Accion.VALIDAR,
                  entidad="Compromiso", objeto=compromiso,
                  antes="realizado sin validar", despues="validado",
                  detalle="Alimenta «%s»." % compromiso.item
                          if compromiso.item_id else "Sin ítem asignado.")

        if compromiso.item_id:
            detalle = "Ya alimenta la meta de «%s»." % compromiso.item
        else:
            detalle = ("Queda validado. No alimenta ninguna meta porque no "
                       "tiene ítem asignado.")
        anunciar(request, "Compromiso validado", detalle)
        return redirect(con_vuelta(request, "gestion:compromiso_detalle", pk))

"""
Las dos pantallas de supervisión que faltaban: alertas y auditoría.

Van juntas porque son las dos caras de lo mismo. La auditoría dice qué pasó
y no se puede tocar; las alertas dicen qué está pasando ahora y requiere
atención. Marcar una alerta como revisada es, a su vez, un evento que la
auditoría registra.
"""

from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.html import format_html
from django.views import View

from comun import permisos as P
from comun.auditoria import registrar
from comun.contexto import delegacion_activa
from comun.mantenedor import Columna, Filtro, ListaMantenedor
from comun.models import AlertaRevisada, EventoAuditoria
from comun.navegacion import desde_formulario
from comun.permisos import redirect_al_login, tiene_permiso
from comun.resultado import anunciar
from gestion import alertas as A
from gestion import tablero as T
from organizacion.models import Delegacion


def _exigir(request, permiso, queja):
    if not request.user.is_authenticated:
        return redirect_al_login(request)
    if permiso and not tiene_permiso(request.user, permiso):
        raise PermissionDenied(queja)
    return None


# =========================================================================
# Alertas
# =========================================================================


def alertas(request):
    """
    Lo que requiere atención en la delegación, calculado al abrir la página.

    Pide el permiso de ver el tablero: quien supervisa el avance es quien
    tiene que ver los avisos. La delegación es la activa de la sesión y se
    puede cambiar con ``?delegacion=``, valor que se vuelve a comprobar
    contra las que el perfil autoriza.
    """
    desvio = _exigir(request, P.VER_TABLERO,
                     "No tienes permiso para ver las alertas de la delegación.")
    if desvio:
        return desvio

    periodo = T.periodo_elegido(request)
    perfil = P.perfil_de(request.user)
    permitidas = (perfil.delegaciones_visibles() if perfil is not None
                  else Delegacion.objects.filter(activo=True))

    pedida = request.GET.get("delegacion")
    delegacion = None
    if pedida:
        delegacion = permitidas.filter(pk=pedida).first()
        if delegacion is None:
            raise PermissionDenied(
                "Esa delegación no está entre las que tu perfil autoriza."
            )
    if delegacion is None:
        delegacion = delegacion_activa(request) or permitidas.first()

    datos = A.de_delegacion(delegacion, periodo)
    return render(request, "gestion/alertas.html", {
        "menu": "alertas",
        "periodo": periodo,
        "periodos": list(T.periodos_visibles()),
        "delegacion": delegacion,
        "delegaciones": list(permitidas),
        **datos,
        "sin_datos": ("Todavía no hay un período configurado."
                      if periodo is None else
                      "Tu perfil no tiene delegaciones autorizadas."
                      if delegacion is None else ""),
    })


class RevisarAlerta(View):
    """
    Marca una alerta como revisada.

    No borra ni cambia el compromiso, la evidencia ni el avance que la
    originaron: escribe una fila aparte. Es lo que pide el caso TAB-06 con
    «la revisión no elimina el evento original». Si la condición sigue
    dándose, la alerta sigue existiendo; solo deja de aparecer entre las
    pendientes.
    """

    def post(self, request):
        desvio = _exigir(request, P.VER_TABLERO,
                         "No tienes permiso para revisar alertas.")
        if desvio:
            return desvio

        clave = (request.POST.get("clave") or "").strip()
        titulo = (request.POST.get("titulo") or "").strip()
        detalle = (request.POST.get("detalle") or "").strip()
        tipo = (request.POST.get("tipo") or "").strip()
        # No se usa ``request.POST.get("volver")`` directo: iría a parar a un
        # ``redirect()``, y un valor de formulario que llega sin validar a un
        # ``redirect()`` es una redirección abierta. Ver ``comun.navegacion``.
        volver = desde_formulario(request, "gestion:alertas")

        if not clave or not titulo:
            anunciar(request, "No se pudo marcar",
                     "Faltó identificar la alerta.", icono="error")
            return redirect(volver)

        perfil = P.perfil_de(request.user)
        delegacion = delegacion_activa(request) or getattr(perfil, "delegacion", None)

        marca, nueva = AlertaRevisada.objects.get_or_create(
            clave=clave,
            defaults={
                "tipo": tipo, "titulo": titulo, "detalle": detalle,
                "delegacion": delegacion, "quien": request.user,
            },
        )
        if nueva:
            registrar(
                request, EventoAuditoria.Accion.REVISAR,
                entidad="Alerta", objeto=marca, objeto_texto=titulo,
                despues="revisada", detalle=detalle, delegacion=delegacion,
            )
            anunciar(request, "Alerta revisada",
                     "Sale de las pendientes. Lo que la originó no cambió: si "
                     "la condición sigue dándose, la alerta sigue ahí.")
        else:
            anunciar(request, "Ya estaba revisada",
                     "La revisó %s." % marca.usuario_visible, icono="warning")
        return redirect(volver)


# =========================================================================
# Auditoría
# =========================================================================


ACCION_CHIP = {
    EventoAuditoria.Accion.CREAR: "ok",
    EventoAuditoria.Accion.EDITAR: "line",
    EventoAuditoria.Accion.ESTADO: "warn",
    EventoAuditoria.Accion.VALIDAR: "ok",
    EventoAuditoria.Accion.RECHAZAR: "bad",
    EventoAuditoria.Accion.ANULAR: "bad",
    EventoAuditoria.Accion.PERIODO: "warn",
    EventoAuditoria.Accion.PARAMETRO: "warn",
    EventoAuditoria.Accion.AJUSTE: "warn",
    EventoAuditoria.Accion.REASIGNAR: "line",
    EventoAuditoria.Accion.REVISAR: "line",
}


def _chip_accion(evento):
    return format_html(
        '<span class="chip {}">{}</span>',
        ACCION_CHIP.get(evento.accion, "line"), evento.get_accion_display(),
    )


def _celda_cambio(evento):
    if evento.antes and evento.despues:
        return format_html(
            '<span class="t2">{}</span>{}', evento.antes, evento.despues)
    return evento.cambio


class Auditoria(ListaMantenedor):
    """
    El historial de operaciones críticas, de solo lectura.

    No tiene formulario de creación, ni de edición, ni botón de estado: no es
    un mantenedor, es un registro. El caso INT-03 pide que un perfil
    operativo no pueda alterarla, y la forma de garantizarlo no es esconder
    los botones sino que las rutas no existan.
    """

    model = EventoAuditoria
    permiso = P.VER_AUDITORIA
    menu = "auditoria"
    titulo = "Auditoría"
    bajada = (
        "Historial de operaciones críticas: quién cambió qué dato y cuándo. "
        "Es de solo lectura; ningún usuario puede modificar ni borrar eventos."
    )
    singular = "evento"
    plural = "eventos"
    genero = "el"
    placeholder = "Usuario, registro, acción o detalle"
    rotulo_nuevo = ""
    busca = ["quien_texto", "entidad", "objeto_texto", "detalle",
             "antes", "despues"]
    orden_inicial = "-cuando"

    url_lista = "gestion:auditoria"
    url_nueva = ""
    url_editar = ""
    url_detalle = ""
    url_estado = ""

    filtros = [
        Filtro("accion", "Acción", EventoAuditoria.Accion.choices,
               campo="accion", vacio="Todas"),
        Filtro("entidad", "Entidad",
               lambda: [(e, e) for e in EventoAuditoria.objects
                        .order_by("entidad").values_list("entidad", flat=True)
                        .distinct()],
               campo="entidad", vacio="Todas"),
    ]

    columnas = [
        Columna("cuando", "Fecha y hora", orden="cuando",
                valor=lambda o: f"{o.cuando:%d-%m-%Y %H:%M}"),
        Columna("usuario", "Usuario", orden="quien_texto",
                valor=lambda o: o.usuario_visible),
        Columna("accion", "Acción", orden="accion", celda=_chip_accion,
                valor=lambda o: o.get_accion_display()),
        Columna("registro", "Registro", orden="entidad", clase="w",
                celda=lambda o: format_html(
                    '{}<span class="t2">{}</span>',
                    o.registro_visible, o.entidad),
                valor=lambda o: o.registro_visible),
        Columna("cambio", "Cambio", clase="w", celda=_celda_cambio,
                valor=lambda o: o.cambio),
        Columna("origen", "Origen", valor=lambda o: o.origen or "—"),
    ]

    nota = (
        "<b>Solo se agregan filas.</b> La auditoría no tiene formulario de "
        "edición ni de borrado, y sus rutas no existen: no es que los botones "
        "estén escondidos, es que la operación no está construida."
    )

    def base_queryset(self):
        consulta = EventoAuditoria.objects.select_related("quien", "delegacion")

        # Quien tiene alcance acotado ve los eventos de sus delegaciones y los
        # que no pertenecen a ninguna —un cambio de parámetro del cálculo, por
        # ejemplo, que afecta a todas.
        perfil = P.perfil_de(self.request.user)
        if perfil is not None:
            from organizacion.models import Rol

            if perfil.rol.alcance != Rol.Alcance.TODAS:
                visibles = list(
                    perfil.delegaciones_visibles().values_list("pk", flat=True))
                consulta = consulta.filter(
                    Q(delegacion_id__in=visibles) | Q(delegacion__isnull=True))
        return consulta

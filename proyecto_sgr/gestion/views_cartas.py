"""
El tubo de cartas de oficina de partes (hoja TUBO CARTAS de la matriz).

Lo ve y lo lleva quien atiende público —el Apoyo Administrativo, que en el
descriptor de cargos es quien retroalimenta al delegado con las solicitudes
por carta— y quien conduce la delegación. Por eso pide uno de dos permisos:
registrar atención ciudadana o ver el tablero.
"""

from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.urls import reverse
from django.utils.html import format_html

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
    filtro_estado,
)
from comun.permisos import redirect_al_login, tiene_permiso
from gestion.forms_cartas import CartaForm
from gestion.modelos_cartas import Carta

PERMISOS = (P.REGISTRAR_ATENCION, P.VER_TABLERO)


def puede_ver_cartas(usuario):
    return any(tiene_permiso(usuario, clave) for clave in PERMISOS)


class _PermisoCartas:
    """Exige uno de los dos permisos antes de entrar a la vista."""

    campo_delegacion = "delegacion_id"

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_al_login(request)
        if not puede_ver_cartas(request.user):
            raise PermissionDenied(
                "El tubo de cartas lo llevan quienes atienden público y quienes "
                "conducen la delegación."
            )
        return super().dispatch(request, *args, **kwargs)


CHIP_CARTA = {
    Carta.Estado.EN_PROCESO: "warn",
    Carta.Estado.APROBADA: "ok",
    Carta.Estado.FINALIZADA: "ok",
    Carta.Estado.NO_APLICA: "line",
}


def _chip(carta):
    return format_html('<span class="chip {}">{}</span>',
                       CHIP_CARTA.get(carta.estado, "line"), carta.get_estado_display())


def _quien(usuario):
    return usuario.get_full_name() or usuario.get_username()


class CartasLista(_PermisoCartas, ListaMantenedor):
    model = Carta
    menu = "cartas"
    titulo = "Tubo de cartas"
    bajada = (
        "Las cartas que llegan por oficina de partes, con quién las sigue y en "
        "qué quedaron. Lo que la delegación tenga que hacer va además a la agenda."
    )
    singular = "carta"
    plural = "cartas"
    genero = "la"
    placeholder = "Código, N°, remitente, tema o unidad"
    rotulo_nuevo = "Ingresar carta"
    busca = ["codigo", "numero", "remitente", "dirigida_a", "tema", "derivada_a"]
    orden_inicial = "-fecha"

    url_lista = "gestion:cartas"
    url_nueva = "gestion:carta_nueva"
    url_editar = "gestion:carta_editar"
    url_detalle = "gestion:carta_detalle"
    url_estado = "gestion:carta_estado"

    filtros = [
        Filtro("situacion", "Estado de la carta", Carta.Estado.choices,
               campo="estado", vacio="Todos"),
        Filtro("quien", "Encargado", [("mias", "Las mías")],
               consulta=lambda v: Q(), vacio="Toda la delegación"),
        filtro_estado(femenino=True),
    ]

    columnas = [
        Columna("codigo", "Código", clase="mono"),
        Columna("remitente", "Carta", orden="remitente", clase="w",
                celda=lambda o: format_html(
                    '<a class="link" href="{}">{}</a><span class="t2">Para {} · {}</span>',
                    reverse("gestion:carta_detalle", args=[o.pk]),
                    o.remitente, o.dirigida_a,
                    o.tema if len(o.tema) <= 70 else o.tema[:69] + "…",
                ),
                valor=lambda o: o.remitente),
        Columna("fecha", "Recibida",
                celda=lambda o: format_html(
                    '{}<span class="t2">{}</span>', o.fecha.strftime("%d-%m-%Y"),
                    f"N° {o.numero}" if o.numero else "sin N°"),
                valor=lambda o: o.fecha.strftime("%d-%m-%Y")),
        Columna("responsable", "Seguimiento", orden="responsable__first_name",
                celda=lambda o: format_html(
                    '{}<span class="t2">{}</span>', _quien(o.responsable),
                    f"Derivada a {o.derivada_a}" if o.derivada_a else "En la delegación"),
                valor=lambda o: _quien(o.responsable)),
        Columna("estado", "Estado", orden="estado", celda=_chip,
                valor=lambda o: o.get_estado_display()),
    ]

    excel_columnas = [
        Columna("codigo", "Código"),
        Columna("delegacion", "Delegación", valor=lambda o: o.delegacion.nombre),
        Columna("fecha", "Fecha de recepción", valor=lambda o: o.fecha.strftime("%d-%m-%Y")),
        Columna("numero", "N° oficina de partes"),
        Columna("dirigida_a", "Dirigida a"),
        Columna("remitente", "Remite"),
        Columna("tema", "Actividad o tema"),
        Columna("fecha_actividad", "Fecha de la actividad",
                valor=lambda o: o.fecha_actividad.strftime("%d-%m-%Y") if o.fecha_actividad else ""),
        Columna("responsable", "Encargado de seguimiento", valor=lambda o: _quien(o.responsable)),
        Columna("estado", "Estado", valor=lambda o: o.get_estado_display()),
        Columna("pronunciamiento", "Pronunciamiento"),
        Columna("derivada_a", "Derivada a"),
        Columna("observacion", "Observación"),
    ]

    nota = (
        "<b>Una carta no es un compromiso.</b> Muchas llegan solo para "
        "conocimiento —esas quedan en «No aplica»— y otras las decide otra "
        "unidad. Si de una carta nace algo que la delegación tiene que hacer, "
        "ingrésalo también en la agenda: ahí tiene plazo y cuenta para el tubo."
    )

    def base_queryset(self):
        consulta = Carta.objects.select_related("responsable", "delegacion")
        if self.request.GET.get("quien") == "mias":
            consulta = consulta.filter(responsable=self.request.user)
        return consulta

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        vigentes = self.limitar(Carta.objects.filter(activo=True))
        cuentas = dict(vigentes.values_list("estado").annotate(n=Count("pk")))
        contexto.update({
            "antes_del_listado": "gestion/_resumen_cartas.html",
            "cartas_por_estado": [
                (valor, texto, CHIP_CARTA[valor], cuentas.get(valor, 0))
                for valor, texto in Carta.Estado.choices
            ],
            "cartas_total": sum(cuentas.values()),
        })
        return contexto


SECCIONES_CARTA = [
    ("La carta", "Lo que dice el papel que llegó por oficina de partes.",
     ["fecha", "numero", "dirigida_a", "remitente", "tema", "fecha_actividad"]),
    ("El seguimiento", "Quién la sigue, en qué quedó y qué se respondió.",
     ["responsable", "estado", "derivada_a", "pronunciamiento", "observacion"]),
]


class _ConDelegacion:
    def get_form_kwargs(self):
        datos = super().get_form_kwargs()
        perfil = P.perfil_de(self.request.user)
        datos["delegacion"] = (delegacion_activa(self.request)
                               or getattr(perfil, "delegacion", None))
        datos["usuario"] = self.request.user
        return datos


class CartaNueva(_PermisoCartas, _ConDelegacion, CrearMantenedor):
    model = Carta
    form_class = CartaForm
    menu = "cartas"
    singular = "carta"
    plural = "cartas"
    genero = "la"
    url_lista = "gestion:cartas"
    url_detalle = "gestion:carta_detalle"
    lateral = "gestion/_lateral_carta.html"
    secciones = SECCIONES_CARTA


class CartaEditar(_PermisoCartas, _ConDelegacion, EditarMantenedor):
    model = Carta
    form_class = CartaForm
    menu = "cartas"
    singular = "carta"
    plural = "cartas"
    genero = "la"
    url_lista = "gestion:cartas"
    url_detalle = "gestion:carta_detalle"
    lateral = "gestion/_lateral_carta.html"
    secciones = SECCIONES_CARTA


class CartaDetalle(_PermisoCartas, DetalleMantenedor):
    model = Carta
    template_name = "gestion/carta_detalle.html"
    menu = "cartas"
    singular = "carta"
    plural = "cartas"
    genero = "la"
    url_lista = "gestion:cartas"
    url_editar = "gestion:carta_editar"
    url_estado = "gestion:carta_estado"
    campos = [
        ("Código", "codigo", {"mono": True}),
        ("Estado", "estado"),
        ("Recibida", lambda o: o.fecha.strftime("%d-%m-%Y")),
        ("N° de oficina de partes", lambda o: o.numero or "—"),
        ("Dirigida a", "dirigida_a"),
        ("Remite", "remitente"),
        ("Actividad o tema", "tema", {"ancho": True}),
        ("Fecha de la actividad",
         lambda o: o.fecha_actividad.strftime("%d-%m-%Y") if o.fecha_actividad else "—"),
        ("Encargado de seguimiento", lambda o: _quien(o.responsable)),
        ("Derivada a", lambda o: o.derivada_a or "—"),
        ("Pronunciamiento", lambda o: o.pronunciamiento or "Todavía sin respuesta",
         {"ancho": True}),
        ("Observación", lambda o: o.observacion or "—", {"ancho": True}),
        ("Delegación", lambda o: o.delegacion.nombre),
    ]
    kpis = [
        ("Días desde que llegó", lambda o: o.dias_desde_recepcion,
         "Desde la fecha de recepción"),
        ("Situación", lambda o: "Cerrada" if o.cerrada else "Esperando respuesta",
         "Aprobada, finalizada o no aplica la cierran"),
    ]
    pie = (
        "El original queda en oficina de partes. Aquí se registra lo necesario "
        "para encontrarlo y saber en qué quedó."
    )

    def get_context_data(self, **kwargs):
        from comun.observaciones import hilo

        contexto = super().get_context_data(**kwargs)
        contexto["hilo"] = hilo(self.request, "carta", contexto["obj"])
        return contexto


class CartaEstado(CambiarEstado):
    model = Carta
    campo_delegacion = "delegacion_id"
    url_lista = "gestion:cartas"
    singular = "carta"
    genero = "la"

    def post(self, request, pk):
        if request.user.is_authenticated and not puede_ver_cartas(request.user):
            raise PermissionDenied("No puedes cambiar el estado de las cartas.")
        return super().post(request, pk)

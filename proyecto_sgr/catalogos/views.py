"""
Mantenedores de ítems, tipos de atención y subatenciones.

Mismo patrón que los de organización: la clase declara columnas y filtros, y
el comportamiento está en ``comun/mantenedor.py``. Las tres pantallas exigen
el permiso «Gestionar catálogos».
"""

from django.db.models import Count, Q
from django.urls import reverse
from django.utils.html import format_html

from catalogos.forms import ItemForm, SubAtencionForm, TipoAtencionForm
from catalogos.models import Area, Item, SubAtencion, TipoAtencion
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
from comun.utilidades import suma_ponderadores

PERMISO = P.GESTIONAR_CATALOGO


def filtro_area():
    """El filtro por área, que comparten ítems y tipos de atención."""
    return Filtro("area", "Área", Area.choices, vacio="Todas")


# =========================================================================
# Ítems
# =========================================================================


class ItemsLista(ListaMantenedor):
    model = Item
    permiso = PERMISO
    menu = "items"
    titulo = "Ítems y metas"
    bajada = (
        "Lo que se mide en el período, con su meta y el peso que tiene en el "
        "resultado de la delegación."
    )
    singular = "ítem"
    plural = "ítems"
    genero = "el"
    placeholder = "Nombre, código o descripción"
    rotulo_nuevo = "Nuevo ítem"
    busca = ["codigo", "nombre", "descripcion"]
    orden_inicial = "codigo"

    url_lista = "catalogos:items"
    url_nueva = "catalogos:item_nuevo"
    url_editar = "catalogos:item_editar"
    url_detalle = "catalogos:item_detalle"
    url_estado = "catalogos:item_estado"

    filtros = [
        filtro_area(),
        Filtro("unidad", "Unidad", Item.Unidad.choices, vacio="Todas"),
        filtro_estado(),
    ]

    columnas = [
        Columna("codigo", "Código", clase="mono"),
        Columna(
            "nombre", "Ítem", orden="nombre", clase="w",
            celda=lambda o: enlace_nombre(
                o, "catalogos:item_detalle",
                extra=format_html('<span class="t2">{}</span>', o.get_area_display()),
            ),
        ),
        Columna("unidad", "Unidad", valor=lambda o: o.get_unidad_display()),
        Columna("meta", "Meta", alineado="r"),
        Columna(
            "ponderador", "Ponderador", alineado="r",
            celda=lambda o: format_html("{} %", o.ponderador),
            valor=lambda o: o.ponderador,
        ),
        Columna(
            "estado", "Estado", orden="activo",
            celda=chip_estado,
            valor=lambda o: "Activo" if o.activo else "Inactivo",
        ),
    ]

    @property
    def nota(self):
        """
        Cuánto suman los ponderadores activos ahora mismo.

        Se calcula al pintar y no se guarda en ninguna parte: un total
        almacenado se desactualizaría en cuanto alguien desactive un ítem.
        """
        total = suma_ponderadores(Item)
        if total == 100:
            return (
                "<b>Los ponderadores suman 100 %.</b> La configuración del "
                "período está completa: el resultado de cada delegación se "
                "calcula sobre esta base."
            )
        if total < 100:
            return (
                "<b>Los ponderadores activos suman %d %%.</b> Faltan %d %% "
                "para completar el 100 %%. Mientras no se cierre, el "
                "resultado del período se calcula sobre lo que haya."
                % (total, 100 - total)
            )
        return (
            "<b>Los ponderadores activos suman %d %%</b>, más de 100 %%. "
            "Revisa los pesos: el resultado quedaría calculado sobre una "
            "base distinta de 100." % total
        )


class _ConPonderador:
    """
    Le pasa al panel lateral cuánto ponderador queda libre.

    Lo comparten crear y editar; la diferencia es que al editar hay que
    descontar el ítem que se está modificando, para que su propio valor no
    aparezca como ya ocupado.
    """

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        otros = suma_ponderadores(Item, excluir_pk=getattr(self.object, "pk", None))
        ctx["suma_otros"] = otros
        ctx["ponderador_libre"] = max(0, 100 - otros)
        return ctx


class ItemNuevo(_ConPonderador, CrearMantenedor):
    model = Item
    form_class = ItemForm
    permiso = PERMISO
    menu = "items"
    singular = "ítem"
    plural = "ítems"
    genero = "el"
    url_lista = "catalogos:items"
    url_detalle = "catalogos:item_detalle"
    lateral = "catalogos/_lateral_item.html"
    secciones = [
        ("Identificación", "Cómo se llama el ítem y en qué área se informa.",
         ["codigo", "nombre", "area"]),
        ("Qué se considera", "El criterio que se aplica al revisar los registros.",
         ["descripcion"]),
        ("Medición", "En qué unidad se mide, cuál es la meta y cuánto pesa en el resultado.",
         ["unidad", "meta", "ponderador"]),
    ]


class ItemEditar(_ConPonderador, EditarMantenedor):
    model = Item
    form_class = ItemForm
    permiso = PERMISO
    menu = "items"
    singular = "ítem"
    plural = "ítems"
    genero = "el"
    url_lista = "catalogos:items"
    url_detalle = "catalogos:item_detalle"
    lateral = "catalogos/_lateral_item.html"
    secciones = ItemNuevo.secciones


class ItemDetalle(DetalleMantenedor):
    model = Item
    permiso = PERMISO
    menu = "items"
    singular = "ítem"
    plural = "ítems"
    genero = "el"
    url_lista = "catalogos:items"
    url_editar = "catalogos:item_editar"
    url_estado = "catalogos:item_estado"
    campos = [
        ("Código", "codigo", {"mono": True}),
        ("Nombre", "nombre"),
        ("Área", "area"),
        ("Unidad de medida", "unidad"),
        ("Meta del período", lambda o: f"{o.meta} {o.get_unidad_display().lower()}"),
        ("Ponderador", lambda o: f"{o.ponderador} %"),
        ("Qué se considera", "descripcion", {"ancho": True}),
    ]
    kpis = [
        ("Peso en el resultado", lambda o: f"{o.ponderador} %",
         "Del 100 % de la evaluación"),
        ("Suman los activos", lambda o: f"{suma_ponderadores(Item)} %",
         "Incluido este ítem si está activo"),
    ]
    pie = "Cambiar el ponderador recalcula el resultado del período en curso."


class ItemEstado(CambiarEstado):
    model = Item
    permiso = PERMISO
    url_lista = "catalogos:items"
    singular = "ítem"
    genero = "el"


# =========================================================================
# Tipos de atención
# =========================================================================


class TiposLista(ListaMantenedor):
    model = TipoAtencion
    permiso = PERMISO
    menu = "tipos"
    titulo = "Tipos de atención"
    bajada = (
        "La clasificación general de lo que se resuelve en el mesón. Cada "
        "tipo se abre en subatenciones."
    )
    singular = "tipo de atención"
    plural = "tipos de atención"
    genero = "el"
    placeholder = "Nombre, código o descripción"
    rotulo_nuevo = "Nuevo tipo"
    busca = ["codigo", "nombre", "descripcion"]
    orden_inicial = "codigo"

    url_lista = "catalogos:tipos"
    url_nueva = "catalogos:tipo_nuevo"
    url_editar = "catalogos:tipo_editar"
    url_detalle = "catalogos:tipo_detalle"
    url_estado = "catalogos:tipo_estado"

    filtros = [filtro_area(), filtro_estado()]

    columnas = [
        Columna("codigo", "Código", clase="mono"),
        Columna(
            "nombre", "Tipo de atención", orden="nombre", clase="w",
            celda=lambda o: enlace_nombre(
                o, "catalogos:tipo_detalle",
                extra=format_html('<span class="t2">{}</span>', o.descripcion),
            ),
        ),
        Columna("area", "Área", valor=lambda o: o.get_area_display()),
        Columna(
            "subatenciones", "Subatenciones", orden="n_activas", alineado="r",
            celda=lambda o: _celda_subatenciones(o),
            valor=lambda o: o.n_activas,
        ),
        Columna(
            "estado", "Estado", orden="activo",
            celda=chip_estado,
            valor=lambda o: "Activo" if o.activo else "Inactivo",
        ),
    ]

    nota = (
        "<b>Un tipo con subatenciones activas no se puede desactivar.</b> "
        "Quedarían disponibles para registrar sin su tipo. Primero se "
        "desactivan ellas; el sistema lo comprueba al intentarlo."
    )

    def base_queryset(self):
        return TipoAtencion.objects.annotate(
            n_activas=Count("subatenciones", filter=Q(subatenciones__activo=True)),
        )


def _celda_subatenciones(tipo):
    """El número de subatenciones activas, enlazado al listado ya filtrado."""
    if not tipo.n_activas:
        return format_html('<span class="soft">—</span>')
    destino = "%s?tipo=%s" % (reverse("catalogos:subatenciones"), tipo.pk)
    return format_html('<a class="link" href="{}">{}</a>', destino, tipo.n_activas)


class TipoNuevo(CrearMantenedor):
    model = TipoAtencion
    form_class = TipoAtencionForm
    permiso = PERMISO
    menu = "tipos"
    singular = "tipo de atención"
    plural = "tipos de atención"
    genero = "el"
    url_lista = "catalogos:tipos"
    url_detalle = "catalogos:tipo_detalle"
    lateral = "catalogos/_lateral_tipo.html"
    secciones = [
        ("Identificación", "Cómo se llama y en qué área se informa.",
         ["codigo", "nombre", "area"]),
        ("Qué entra aquí", "El texto que orienta a quien registra una atención.",
         ["descripcion"]),
    ]


class TipoEditar(EditarMantenedor):
    model = TipoAtencion
    form_class = TipoAtencionForm
    permiso = PERMISO
    menu = "tipos"
    singular = "tipo de atención"
    plural = "tipos de atención"
    genero = "el"
    url_lista = "catalogos:tipos"
    url_detalle = "catalogos:tipo_detalle"
    lateral = "catalogos/_lateral_tipo.html"
    secciones = TipoNuevo.secciones


class TipoDetalle(DetalleMantenedor):
    model = TipoAtencion
    permiso = PERMISO
    menu = "tipos"
    singular = "tipo de atención"
    plural = "tipos de atención"
    genero = "el"
    url_lista = "catalogos:tipos"
    url_editar = "catalogos:tipo_editar"
    url_estado = "catalogos:tipo_estado"
    campos = [
        ("Código", "codigo", {"mono": True}),
        ("Nombre", "nombre"),
        ("Área", "area"),
        ("Qué entra aquí", "descripcion", {"ancho": True}),
        ("Subatenciones",
         lambda o: ", ".join(s.nombre for s in o.subatenciones.filter(activo=True))
                   or "Todavía ninguna activa",
         {"ancho": True}),
    ]
    kpis = [
        ("Subatenciones activas", lambda o: o.subatenciones.filter(activo=True).count(),
         "Disponibles para registrar"),
        ("En total", lambda o: o.subatenciones.count(),
         "Incluyendo las desactivadas"),
    ]
    pie = "Las subatenciones se administran en su propio mantenedor."


class TipoEstado(CambiarEstado):
    model = TipoAtencion
    permiso = PERMISO
    url_lista = "catalogos:tipos"
    singular = "tipo de atención"
    genero = "el"


# =========================================================================
# Subatenciones
# =========================================================================


class SubatencionesLista(ListaMantenedor):
    model = SubAtencion
    permiso = PERMISO
    menu = "subatenciones"
    titulo = "Subatenciones"
    bajada = (
        "El detalle de cada tipo. Es lo que se elige al registrar una "
        "atención, y lo que define si hace falta documento de respaldo."
    )
    singular = "subatención"
    plural = "subatenciones"
    genero = "la"
    placeholder = "Nombre, código o descripción"
    rotulo_nuevo = "Nueva subatención"
    busca = ["codigo", "nombre", "descripcion", "tipo_atencion__nombre"]
    orden_inicial = "codigo"

    url_lista = "catalogos:subatenciones"
    url_nueva = "catalogos:subatencion_nueva"
    url_editar = "catalogos:subatencion_editar"
    url_detalle = "catalogos:subatencion_detalle"
    url_estado = "catalogos:subatencion_estado"

    filtros = [
        Filtro(
            "tipo", "Tipo de atención",
            lambda: [(t.pk, t.nombre) for t in TipoAtencion.objects.filter(activo=True)],
            campo="tipo_atencion_id", vacio="Todos",
        ),
        Filtro(
            "respaldo", "Respaldo",
            [("si", "Exige documento"), ("no", "No exige")],
            consulta=lambda v: Q(documento=(v == "si")),
            vacio="Todas",
        ),
        filtro_estado(femenino=True),
    ]

    columnas = [
        Columna("codigo", "Código", clase="mono"),
        Columna(
            "nombre", "Subatención", orden="nombre", clase="w",
            celda=lambda o: enlace_nombre(
                o, "catalogos:subatencion_detalle", femenino=True,
                extra=format_html('<span class="t2">{}</span>', o.descripcion),
            ),
        ),
        Columna(
            "tipo", "Tipo", orden="tipo_atencion__nombre",
            valor=lambda o: o.tipo_atencion.nombre,
        ),
        Columna(
            "documento", "Respaldo", orden="documento",
            celda=lambda o: _chip_respaldo(o),
            valor=lambda o: "Exige documento" if o.documento else "No exige",
        ),
        Columna(
            "estado", "Estado", orden="activo",
            celda=lambda o: chip_estado(o, femenino=True),
            valor=lambda o: "Activa" if o.activo else "Inactiva",
        ),
    ]

    nota = (
        "<b>«Exige documento» no es un recordatorio.</b> Si está marcado, el "
        "ingreso de atención ciudadana no deja guardar sin indicar el "
        "respaldo: lo comprueba el método <code>clean()</code> del modelo, "
        "así que vale también desde el administrador."
    )

    def base_queryset(self):
        return SubAtencion.objects.select_related("tipo_atencion")


def _chip_respaldo(sub):
    if sub.documento:
        return format_html('<span class="chip warn"><span class="t">Exige documento</span></span>')
    return format_html('<span class="soft">No exige</span>')


class SubatencionNueva(CrearMantenedor):
    model = SubAtencion
    form_class = SubAtencionForm
    permiso = PERMISO
    menu = "subatenciones"
    singular = "subatención"
    plural = "subatenciones"
    genero = "la"
    url_lista = "catalogos:subatenciones"
    url_detalle = "catalogos:subatencion_detalle"
    lateral = "catalogos/_lateral_subatencion.html"
    secciones = [
        ("A qué tipo pertenece", "Una subatención siempre cuelga de un tipo activo.",
         ["codigo", "tipo_atencion", "nombre"]),
        ("Detalle", "Lo que ve quien registra la atención en el mesón.",
         ["descripcion", "documento"]),
    ]


class SubatencionEditar(EditarMantenedor):
    model = SubAtencion
    form_class = SubAtencionForm
    permiso = PERMISO
    menu = "subatenciones"
    singular = "subatención"
    plural = "subatenciones"
    genero = "la"
    url_lista = "catalogos:subatenciones"
    url_detalle = "catalogos:subatencion_detalle"
    lateral = "catalogos/_lateral_subatencion.html"
    secciones = SubatencionNueva.secciones


class SubatencionDetalle(DetalleMantenedor):
    model = SubAtencion
    permiso = PERMISO
    menu = "subatenciones"
    singular = "subatención"
    plural = "subatenciones"
    genero = "la"
    url_lista = "catalogos:subatenciones"
    url_editar = "catalogos:subatencion_editar"
    url_estado = "catalogos:subatencion_estado"
    campos = [
        ("Código", "codigo", {"mono": True}),
        ("Nombre", "nombre"),
        ("Tipo de atención", lambda o: o.tipo_atencion.nombre),
        ("Área", lambda o: o.tipo_atencion.get_area_display()),
        ("Documento de respaldo",
         lambda o: "Obligatorio: no se puede guardar la atención sin indicarlo"
                   if o.documento else "No se exige"),
        ("Detalle", "descripcion", {"ancho": True}),
    ]
    kpis = [
        ("Atenciones registradas", lambda o: o.atenciones.count(),
         "Con esta subatención"),
    ]
    pie = "Mientras tenga atenciones registradas no se puede desactivar."

    def get_queryset(self):
        # Las subatenciones son del municipio entero, no de una delegación,
        # así que aquí limitar() no filtra nada. Se encauza igual para que el
        # patrón sea el mismo en los seis mantenedores: si alguna vez un
        # catálogo pasa a ser por delegación, basta declarar el campo.
        return self.limitar(SubAtencion.objects.select_related("tipo_atencion"))


class SubatencionEstado(CambiarEstado):
    model = SubAtencion
    permiso = PERMISO
    url_lista = "catalogos:subatenciones"
    singular = "subatención"
    genero = "la"

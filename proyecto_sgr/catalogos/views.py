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
PERMISO = P.GESTIONAR_CATALOGO


def filtro_area():
    """El filtro por área, que comparten ítems y tipos de atención."""
    return Filtro("area", "Área", Area.choices, vacio="Todas")


# =========================================================================
# Ítems
# =========================================================================


def _enlace_historial(obj):
    from gestion.views_versiones import enlace_historial

    return enlace_historial(obj)


class ItemsLista(ListaMantenedor):
    model = Item
    permiso = PERMISO
    menu = "items"
    titulo = "Ítems y metas"
    bajada = (
        "Lo que se puede medir, con la meta y el peso que se proponen al "
        "asignarlo a un cargo."
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
        Filtro("medicion", "Cómo se mide", Item.Medicion.choices, vacio="Todas"),
        filtro_estado(),
    ]

    columnas = [
        Columna("codigo", "Código", clase="mono"),
        Columna(
            "nombre", "Ítem", orden="nombre", clase="w",
            celda=lambda o: enlace_nombre(
                o, "catalogos:item_detalle",
                extra=format_html(
                    '<span class="t2">{}{}</span>', o.get_area_display(),
                    "" if o.medicion == Item.Medicion.ACTIVIDADES
                    else " · " + o.get_medicion_display().lower(),
                ),
            ),
        ),
        Columna("unidad", "Unidad", valor=lambda o: o.get_unidad_display()),
        Columna("meta", "Meta sugerida", alineado="r"),
        Columna(
            "ponderador", "Ponderador sugerido", alineado="r",
            celda=lambda o: format_html("{} %", o.ponderador),
            valor=lambda o: o.ponderador,
        ),
        Columna(
            "estado", "Estado", orden="activo",
            celda=chip_estado,
            valor=lambda o: "Activo" if o.activo else "Inactivo",
        ),
    ]

    nota = (
        "<b>La meta y el ponderador de esta lista son sugeridos.</b> Se "
        "proponen al asignar el ítem a un cargo. El peso que usa el cálculo "
        "se define por período y cargo en Metas y ponderadores, donde los "
        "ítems de cada cargo suman 100 %."
    )


class ItemNuevo(CrearMantenedor):
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
        ("Medición", "Cómo se mide, en qué unidad, y qué meta y peso se proponen al asignarlo a un cargo.",
         ["medicion", "unidad", "meta", "ponderador"]),
    ]


class ItemEditar(EditarMantenedor):
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
        ("Cómo se mide", "medicion"),
        ("Historial", lambda o: _enlace_historial(o), {"html": True}),
        ("Unidad de medida", "unidad"),
        ("Meta sugerida", lambda o: f"{o.meta} {o.get_unidad_display().lower()}"),
        ("Ponderador sugerido", lambda o: f"{o.ponderador} %"),
        ("Qué se considera", "descripcion", {"ancho": True}),
    ]
    kpis = [
        ("En metas vigentes",
         lambda o: o.metas.filter(activo=True).exclude(periodo__estado="cerrado").count(),
         "De períodos abiertos o en preparación"),
        ("Ponderador sugerido", lambda o: f"{o.ponderador} %",
         "Se propone al crear una meta con este ítem"),
    ]
    pie = (
        "La meta y el ponderador que usa el cálculo se definen por período y "
        "cargo, en Metas y ponderadores. Cambiar los sugeridos no altera "
        "ninguna meta ya creada."
    )


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

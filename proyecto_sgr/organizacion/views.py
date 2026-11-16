"""
Mantenedores de delegaciones, roles y usuarios.

Cada clase declara qué tiene que mostrar; el comportamiento —buscar,
filtrar, ordenar, paginar, exportar, activar y desactivar— está una sola vez
en ``comun/mantenedor.py``. Por eso estos archivos son cortos: si hubiera
que cambiar cómo funciona el paginador, se cambia en un lugar y los seis
mantenedores cambian con él.

Las pantallas se abren con la acción «Gestionar usuarios y roles» o con el
permiso de Django de cada operación (ver ``comun/entidades.py``). La
comprobación la hace el mixin antes de entrar a la vista, así que no depende
de que el menú haya escondido el enlace.

Nadie se asigna privilegios a sí mismo: en la propia ficha el rol queda
bloqueado, nadie se desactiva ni desactiva su propio rol, y los privilegios
de un rol se configuran en una pantalla aparte que pide la acción de
administrar el acceso.
"""

from django.core.exceptions import PermissionDenied
from django.db.models import Count
from django.urls import reverse
from django.utils.html import format_html

from comun import permisos as P
from comun.formularios import nombre_de_usuario
from comun.mantenedor import (
    Desde,
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
from organizacion.forms import (
    DelegacionForm, RolForm, RolPrivilegiosForm, TerritorioForm, UsuarioForm,
    roles_asignables,
)
from organizacion.models import Delegacion, PerfilUsuario, Rol, Territorio

PERMISO = P.GESTIONAR_USUARIO


def _ficha(obj, nombre_de_ruta):
    """La dirección de la ficha de un registro."""
    return reverse(nombre_de_ruta, args=[obj.pk])


# =========================================================================
# Delegaciones
# =========================================================================


class DelegacionesLista(ListaMantenedor):
    model = Delegacion
    permiso = PERMISO
    # Se llega a la delegación por su propia clave: quien no tiene alcance
    # «todas» ve únicamente las que su perfil autoriza.
    campo_delegacion = "pk"
    menu = "delegaciones"
    titulo = "Delegaciones municipales"
    bajada = (
        "Las unidades territoriales donde se presta atención. Cada registro "
        "del sistema queda asociado a una de ellas."
    )
    singular = "delegación"
    plural = "delegaciones"
    genero = "la"
    placeholder = "Nombre, código, comuna o dirección"
    rotulo_nuevo = "Nueva delegación"
    busca = ["codigo", "nombre", "comuna", "direccion"]
    orden_inicial = "codigo"

    url_lista = "organizacion:delegaciones"
    url_nueva = "organizacion:delegacion_nueva"
    url_editar = "organizacion:delegacion_editar"
    url_detalle = "organizacion:delegacion_detalle"
    url_estado = "organizacion:delegacion_estado"

    filtros = [
        Filtro("zona", "Zona", Delegacion.Zona.choices, vacio="Todas"),
        filtro_estado(femenino=True),
    ]

    columnas = [
        Columna("codigo", "Código", clase="mono"),
        Columna(
            "nombre", "Delegación", orden="nombre",
            celda=lambda o: enlace_nombre(
                o, "organizacion:delegacion_detalle", femenino=True,
                extra=format_html('<span class="t2">{}</span>', o.direccion or o.comuna),
            ),
        ),
        Columna("zona", "Zona", valor=lambda o: o.get_zona_display()),
        Columna("delegado", "Delegado", orden="delegado__first_name",
                valor=lambda o: nombre_de_usuario(o.delegado) if o.delegado_id else "—"),
        Columna("horario", "Horario", clase="w"),
        Columna(
            "usuarios", "Usuarios", orden="n_perfiles", alineado="r",
            valor=lambda o: o.n_perfiles,
        ),
        Columna(
            "estado", "Estado", orden="activo",
            celda=lambda o: chip_estado(o, femenino=True),
            valor=lambda o: "Activa" if o.activo else "Inactiva",
        ),
    ]

    nota = (
        "<b>Por qué no hay botón de eliminar.</b> Los perfiles de usuario "
        "apuntan a su delegación con <code>on_delete=PROTECT</code>: borrarla "
        "dejaría registros huérfanos. Desactivarla la retira de los "
        "formularios y conserva el historial."
    )

    def base_queryset(self):
        # Se cuenta en la consulta y no en la plantilla: contar en la
        # plantilla daría una consulta por fila.
        return Delegacion.objects.annotate(n_perfiles=Count("perfiles", distinct=True))


class DelegacionNueva(CrearMantenedor):
    model = Delegacion
    campo_delegacion = "pk"
    form_class = DelegacionForm
    permiso = PERMISO
    menu = "delegaciones"
    singular = "delegación"
    plural = "delegaciones"
    genero = "la"
    url_lista = "organizacion:delegaciones"
    url_detalle = "organizacion:delegacion_detalle"
    lateral = "organizacion/_lateral_delegacion.html"
    secciones = [
        ("Identificación", "El código se asigna solo y no vuelve a cambiar.",
         ["codigo", "nombre", "zona", "comuna"]),
        ("Ubicación y atención", "Lo que se publica para que la comunidad sepa dónde ir.",
         ["direccion", "telefono", "horario"]),
        ("Delegado", "Quien encabeza la delegación. Puede quedar vacío mientras se nombra.",
         ["delegado"]),
    ]


class DelegacionEditar(EditarMantenedor):
    model = Delegacion
    campo_delegacion = "pk"
    form_class = DelegacionForm
    permiso = PERMISO
    menu = "delegaciones"
    singular = "delegación"
    plural = "delegaciones"
    genero = "la"
    url_lista = "organizacion:delegaciones"
    url_detalle = "organizacion:delegacion_detalle"
    lateral = "organizacion/_lateral_delegacion.html"
    secciones = DelegacionNueva.secciones


class DelegacionDetalle(DetalleMantenedor):
    desde_aqui = [
        Desde("Nuevo territorio", "organizacion:territorio_nuevo", "territorio",
              lambda o: {"delegacion": o.pk}, cuando=lambda o: o.activo),
    ]
    model = Delegacion
    campo_delegacion = "pk"
    permiso = PERMISO
    menu = "delegaciones"
    singular = "delegación"
    plural = "delegaciones"
    genero = "la"
    url_lista = "organizacion:delegaciones"
    url_editar = "organizacion:delegacion_editar"
    url_estado = "organizacion:delegacion_estado"
    campos = [
        ("Código", "codigo", {"mono": True}),
        ("Nombre", "nombre"),
        ("Zona", "zona"),
        ("Comuna", "comuna"),
        ("Dirección", "direccion", {"ancho": True}),
        ("Teléfono", "telefono"),
        ("Horario de atención", "horario"),
        ("Delegado", lambda o: nombre_de_usuario(o.delegado) if o.delegado_id else "Sin asignar"),
        ("Territorios",
         lambda o: ", ".join(t.nombre for t in o.territorios.filter(activo=True)) or "Ninguno todavía",
         {"ancho": True}),
        ("Creada el", lambda o: o.creada.strftime("%d-%m-%Y") if o.creada else ""),
    ]
    kpis = [
        ("Territorios activos", lambda o: o.territorios.filter(activo=True).count(),
         "Sectores que atiende"),
        ("Usuarios asignados", lambda o: o.perfiles.count(),
         "Tienen esta delegación como base"),
        ("Usuarios autorizados", lambda o: o.perfiles_autorizados.count(),
         "Pueden cambiarse a ella desde la cabecera"),
    ]
    pie = "Los cambios quedan registrados con la fecha y el usuario que los hizo."


class DelegacionEstado(CambiarEstado):
    model = Delegacion
    campo_delegacion = "pk"
    permiso = PERMISO
    url_lista = "organizacion:delegaciones"
    singular = "delegación"
    genero = "la"


# =========================================================================
# Territorios
# =========================================================================


class _Territorio:
    model = Territorio
    campo_delegacion = "delegacion_id"
    permiso = PERMISO
    menu = "territorios"
    singular = "territorio"
    plural = "territorios"
    genero = "el"
    url_lista = "organizacion:territorios"
    url_detalle = "organizacion:territorio_detalle"


class TerritoriosLista(_Territorio, ListaMantenedor):
    titulo = "Territorios"
    bajada = (
        "Los sectores o unidades vecinales que atiende cada delegación. Los "
        "usan los vecinos, las juntas, los hitos y las actividades."
    )
    placeholder = "Nombre, código o delegación"
    rotulo_nuevo = "Nuevo territorio"
    busca = ["codigo", "nombre", "descripcion", "delegacion__nombre"]
    url_nueva = "organizacion:territorio_nuevo"
    url_editar = "organizacion:territorio_editar"
    url_estado = "organizacion:territorio_estado"
    filtros = [
        Filtro("delegacion", "Delegación",
               lambda: [(d.pk, d.nombre) for d in Delegacion.objects.filter(activo=True)],
               campo="delegacion_id", vacio="Todas"),
        filtro_estado(),
    ]
    columnas = [
        Columna("codigo", "Código", clase="mono"),
        Columna("nombre", "Territorio", orden="nombre", clase="w",
                celda=lambda o: enlace_nombre(
                    o, "organizacion:territorio_detalle",
                    extra=format_html('<span class="t2">{}</span>', o.descripcion[:90]))),
        Columna("delegacion", "Delegación", orden="delegacion__nombre",
                valor=lambda o: o.delegacion.nombre),
        Columna("vecinos", "Vecinos", orden="n_vecinos", alineado="r",
                valor=lambda o: o.n_vecinos),
        Columna("juntas", "Juntas", orden="n_juntas", alineado="r",
                valor=lambda o: o.n_juntas),
        Columna("estado", "Estado", orden="activo", celda=chip_estado,
                valor=lambda o: "Activo" if o.activo else "Inactivo"),
    ]
    nota = (
        "<b>El territorio pertenece a una delegación.</b> Una junta, un hito "
        "o una actividad solo pueden usar territorios de su misma delegación, "
        "y un territorio con vecinos, juntas o hitos activos no se desactiva."
    )

    def base_queryset(self):
        return (Territorio.objects.select_related("delegacion")
                .annotate(n_vecinos=Count("vecinos", distinct=True),
                          n_juntas=Count("juntas", distinct=True)))


class TerritorioNuevo(_Territorio, CrearMantenedor):
    prellenables = ["delegacion"]
    form_class = TerritorioForm
    pasa_usuario = True
    secciones = [
        ("Identificación", "El código se asigna solo. El nombre no se repite dentro de la delegación.",
         ["codigo", "nombre", "delegacion"]),
        ("Qué comprende", "Para reconocerlo sin abrir un mapa.", ["descripcion"]),
    ]


class TerritorioEditar(_Territorio, EditarMantenedor):
    form_class = TerritorioForm
    pasa_usuario = True
    secciones = TerritorioNuevo.secciones


class TerritorioDetalle(_Territorio, DetalleMantenedor):
    desde_aqui = [
        Desde("Nuevo vecino del territorio", "atencion:vecino_nuevo", "vecino",
              lambda o: {"territorio": o.pk}, cuando=lambda o: o.activo),
        Desde("Nueva junta de vecinos", "atencion:junta_nueva", "junta",
              lambda o: {"territorio": o.pk, "delegacion": o.delegacion_id}, cuando=lambda o: o.activo),
    ]
    url_editar = "organizacion:territorio_editar"
    url_estado = "organizacion:territorio_estado"
    campos = [
        ("Código", "codigo", {"mono": True}),
        ("Nombre", "nombre"),
        ("Delegación", lambda o: o.delegacion.nombre),
        ("Qué comprende", "descripcion", {"ancho": True}),
        ("Juntas de vecinos",
         lambda o: ", ".join(j.nombre for j in o.juntas.all()) or "Ninguna", {"ancho": True}),
        ("Creado el", lambda o: o.creada.strftime("%d-%m-%Y") if o.creada else ""),
    ]
    kpis = [
        ("Vecinos", lambda o: o.vecinos.filter(activo=True).count(), "Activos que viven aquí"),
        ("Hitos", lambda o: o.hitos.filter(activo=True).count(), "Activos en este territorio"),
    ]
    pie = "Un territorio con vecinos, juntas o hitos activos no se desactiva."


class TerritorioEstado(CambiarEstado):
    model = Territorio
    campo_delegacion = "delegacion_id"
    permiso = PERMISO
    url_lista = "organizacion:territorios"
    singular = "territorio"
    genero = "el"


# =========================================================================
# Roles
# =========================================================================


class RolesLista(ListaMantenedor):
    model = Rol
    permiso = PERMISO
    menu = "roles"
    titulo = "Roles y permisos"
    bajada = (
        "Un rol agrupa las acciones que habilita. Es lo que decide qué ve y "
        "qué puede hacer cada persona."
    )
    singular = "rol"
    plural = "roles"
    genero = "el"
    placeholder = "Nombre, código o descripción"
    rotulo_nuevo = "Nuevo rol"
    busca = ["codigo", "nombre", "descripcion"]
    orden_inicial = "codigo"

    url_lista = "organizacion:roles"
    url_nueva = "organizacion:rol_nuevo"
    url_editar = "organizacion:rol_editar"
    url_detalle = "organizacion:rol_detalle"
    url_estado = "organizacion:rol_estado"

    filtros = [
        Filtro("alcance", "Alcance", Rol.Alcance.choices, vacio="Todos"),
        filtro_estado(),
    ]

    columnas = [
        Columna("codigo", "Código", clase="mono"),
        Columna(
            "nombre", "Rol", orden="nombre", clase="w",
            celda=lambda o: enlace_nombre(
                o, "organizacion:rol_detalle",
                extra=format_html('<span class="t2">{}</span>', o.descripcion),
            ),
        ),
        Columna("alcance", "Alcance", valor=lambda o: o.get_alcance_display()),
        # orden="" deja la columna sin enlace de ordenamiento: son datos de
        # un JSONField y ordenar por su contenido no significaría nada.
        Columna(
            "permisos", "Acciones", orden="", alineado="r",
            valor=lambda o: len(o.permisos or []),
        ),
        Columna(
            "usuarios", "Usuarios", orden="n_perfiles", alineado="r",
            valor=lambda o: o.n_perfiles,
        ),
        Columna(
            "estado", "Estado", orden="activo",
            celda=chip_estado,
            valor=lambda o: "Activo" if o.activo else "Inactivo",
        ),
    ]

    nota = (
        "<b>El alcance no es lo mismo que el permiso.</b> El permiso dice "
        "<i>qué</i> puede hacer; el alcance, <i>sobre qué delegaciones</i>. "
        "Un rol puede validar evidencias solo en su delegación o en todas, "
        "con el mismo permiso marcado."
    )

    def base_queryset(self):
        return Rol.objects.annotate(n_perfiles=Count("perfiles", distinct=True))


class RolNuevo(CrearMantenedor):
    model = Rol
    form_class = RolForm
    permiso = PERMISO
    menu = "roles"
    singular = "rol"
    plural = "roles"
    genero = "el"
    url_lista = "organizacion:roles"
    url_detalle = "organizacion:rol_detalle"
    lateral = "organizacion/_lateral_rol.html"
    secciones = [
        ("Identificación del rol", "Cómo se llama. El código se asigna solo.",
         ["codigo", "nombre"]),
        ("Qué hace", "Una frase que permita reconocerlo sin abrir los permisos.",
         ["descripcion"]),
    ]


class RolEditar(EditarMantenedor):
    model = Rol
    form_class = RolForm
    permiso = PERMISO
    menu = "roles"
    singular = "rol"
    plural = "roles"
    genero = "el"
    url_lista = "organizacion:roles"
    url_detalle = "organizacion:rol_detalle"
    lateral = "organizacion/_lateral_rol.html"
    secciones = RolNuevo.secciones


class RolDetalle(DetalleMantenedor):
    model = Rol
    permiso = PERMISO
    menu = "roles"
    singular = "rol"
    plural = "roles"
    genero = "el"
    url_lista = "organizacion:roles"
    url_editar = "organizacion:rol_editar"
    url_estado = "organizacion:rol_estado"
    campos = [
        ("Código", "codigo", {"mono": True}),
        ("Nombre", "nombre"),
        ("Alcance", "alcance"),
        ("Descripción", "descripcion", {"ancho": True}),
        ("Grupo de Django", lambda o: o.grupo.name if o.grupo_id else "Ninguno"),
        ("Permisos de Django del grupo",
         lambda o: _lista_django(o), {"ancho": True, "html": True}),
        ("Acciones habilitadas",
         lambda o: _lista_permisos(o), {"ancho": True, "html": True}),
    ]
    template_name = "organizacion/rol_detalle.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["puede_privilegios"] = (
            P.tiene_permiso(self.request.user, P.GESTIONAR_USUARIO)
            and not _es_su_rol(self.request.user, self.object)
        )
        return ctx
    kpis = [
        ("Usuarios con este rol", lambda o: o.perfiles.count(),
         "Perfiles que lo tienen asignado"),
        ("Acciones habilitadas", lambda o: len(o.permisos or []),
         "De %d disponibles" % len(P.CLAVES)),
    ]
    pie = "Quitar una acción de un rol afecta de inmediato a todos sus usuarios."


def _lista_django(rol):
    """Los permisos de Django del grupo del rol, agrupados por operación."""
    from comun.entidades import ACCIONES, POR_MODELO

    if not rol.grupo_id:
        return "<span class='soft'>Sin grupo de Django.</span>"
    por_accion = {}
    for permiso in rol.grupo.permissions.select_related("content_type"):
        accion, _, modelo = permiso.codename.partition("_")
        entidad = POR_MODELO.get((permiso.content_type.app_label, modelo))
        if entidad:
            por_accion.setdefault(accion, []).append(entidad.nombre)
    if not por_accion:
        return "<span class='soft'>El grupo no tiene permisos.</span>"
    trozos = []
    for accion, texto in ACCIONES.items():
        if accion in por_accion:
            nombres = sorted(por_accion[accion])
            cuantas = "las 17 entidades" if len(nombres) == 17 else ", ".join(nombres).lower()
            trozos.append("<b>%s:</b> %s" % (texto.capitalize(), cuantas))
    return "<br>".join(trozos)


def _es_su_rol(usuario, rol):
    perfil = P.perfil_de(usuario)
    return bool(perfil and perfil.rol_id == rol.pk)


def _lista_permisos(rol):
    """Los permisos del rol como lista legible, agrupados igual que el formulario."""
    marcados = set(rol.permisos or [])
    if not marcados:
        return "<span class='soft'>Ninguna acción habilitada.</span>"
    trozos = []
    for grupo, acciones in P.agrupados():
        textos = [texto for clave, texto in acciones if clave in marcados]
        if textos:
            trozos.append(
                "<b>%s:</b> %s" % (grupo, ", ".join(textos).lower())
            )
    return "<br>".join(trozos)


class RolEstado(CambiarEstado):
    model = Rol
    permiso = PERMISO
    url_lista = "organizacion:roles"
    singular = "rol"
    genero = "el"

    def motivo_propio(self, request, obj):
        if _es_su_rol(request.user, obj):
            return "Es tu propio rol: lo activa o desactiva otra persona."
        return ""


class RolPrivilegios(EditarMantenedor):
    """
    Acciones, alcance y grupo de Django de un rol.

    Es el «medio protegido» de la Evaluación 3: pide la acción «Gestionar
    usuarios y roles» y nada más —el permiso de Django para editar roles no
    alcanza—, y nadie configura los privilegios del rol que él mismo tiene:
    eso lo hace otra persona o el superusuario desde Django Admin.
    """

    model = Rol
    form_class = RolPrivilegiosForm
    permiso = PERMISO
    accion_django = None
    menu = "roles"
    singular = "rol"
    plural = "roles"
    genero = "el"
    url_lista = "organizacion:roles"
    url_detalle = "organizacion:rol_detalle"
    lateral = "organizacion/_lateral_rol.html"
    secciones = [
        ("Alcance", "Sobre qué delegaciones actúa quien tiene el rol.", ["alcance"]),
        ("Grupo de Django",
         "Los permisos de Django sobre las 17 entidades: Consulta solo mira; "
         "Gestión crea, edita, desactiva y anula.", ["grupo"]),
        ("Acciones habilitadas", "Las acciones de negocio del SGR. Marca solo lo que el rol necesita.",
         ["permisos"]),
    ]

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            rol = Rol.objects.filter(pk=kwargs.get("pk")).first()
            if rol is not None and _es_su_rol(request.user, rol):
                raise PermissionDenied(
                    "Es tu propio rol: sus privilegios los configura otra persona.")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(
            titulo_form="Privilegios del rol",
            bajada_form=format_html(
                "Qué puede hacer <b>{}</b>. Nadie configura su propio rol.", self.object.nombre),
            sin_aviso_bloqueo=True,
        )
        return ctx

    def get_success_url(self):
        return reverse("organizacion:rol_detalle", args=[self.object.pk])


# =========================================================================
# Usuarios
# =========================================================================


class UsuariosLista(ListaMantenedor):
    model = PerfilUsuario
    campo_delegacion = "delegacion_id"
    permiso = PERMISO
    menu = "usuarios"
    titulo = "Usuarios del sistema"
    bajada = (
        "Quién tiene acceso, con qué rol y en qué delegación. El correo es "
        "el usuario de acceso."
    )
    singular = "usuario"
    plural = "usuarios"
    genero = "el"
    placeholder = "Nombre, correo, código o cargo"
    rotulo_nuevo = "Nuevo usuario"
    busca = [
        "codigo", "cargo", "rut",
        "usuario__first_name", "usuario__last_name", "usuario__email",
    ]
    orden_inicial = "codigo"

    url_lista = "organizacion:usuarios"
    url_nueva = "organizacion:usuario_nuevo"
    url_editar = "organizacion:usuario_editar"
    url_detalle = "organizacion:usuario_detalle"
    url_estado = "organizacion:usuario_estado"

    filtros = [
        Filtro(
            "rol", "Rol",
            lambda: [(r.pk, r.nombre) for r in Rol.objects.filter(activo=True)],
            campo="rol_id", vacio="Todos",
        ),
        Filtro(
            "delegacion", "Delegación",
            lambda: [(d.pk, d.nombre) for d in Delegacion.objects.filter(activo=True)],
            campo="delegacion_id", vacio="Todas",
        ),
        filtro_estado(),
    ]

    columnas = [
        Columna("codigo", "Código", clase="mono"),
        Columna(
            "nombre", "Usuario", orden="usuario__first_name",
            celda=lambda o: _celda_usuario(o),
            valor=lambda o: f"{o.nombre} <{o.correo}>",
        ),
        Columna("rut", "RUT", clase="mono", valor=lambda o: o.rut or "—"),
        Columna("rol", "Rol", orden="rol__nombre", valor=lambda o: o.rol.nombre),
        Columna(
            "delegacion", "Delegación", orden="delegacion__nombre",
            celda=lambda o: _celda_delegacion(o),
            valor=lambda o: o.delegacion.nombre,
        ),
        Columna(
            "estado", "Estado", orden="activo",
            celda=chip_estado,
            valor=lambda o: "Activo" if o.activo else "Inactivo",
        ),
    ]

    nota = (
        "<b>Las contraseñas no se escriben aquí.</b> Una cuenta nueva nace sin "
        "contraseña utilizable y la persona crea la suya con el enlace de "
        "«¿Olvidaste tu contraseña?». Así nadie, ni el administrador, llega a "
        "conocerla: en la base solo queda el hash que genera Django."
    )

    def base_queryset(self):
        return (
            PerfilUsuario.objects
            .select_related("usuario", "rol", "delegacion")
            .annotate(n_autorizadas=Count("delegaciones_autorizadas", distinct=True))
        )


def _celda_usuario(perfil):
    """El nombre enlazado a la ficha y, debajo, el correo de acceso."""
    return format_html(
        '<a class="link" href="{}">{}</a><span class="t2">{}</span>',
        _ficha(perfil, "organizacion:usuario_detalle"),
        perfil.nombre,
        perfil.correo,
    )


def _celda_delegacion(perfil):
    """
    La delegación base y, si tiene más autorizadas, cuántas.

    ``n_autorizadas`` es el tamaño de la lista de delegaciones autorizadas y
    viene anotado en la consulta: contar aquí haría una consulta por fila.
    """
    marcadas = perfil.n_autorizadas
    if not marcadas:
        return format_html("{}", perfil.delegacion.nombre)
    return format_html(
        '{}<span class="t2">{} autorizada{} en su lista</span>',
        perfil.delegacion.nombre, marcadas, "" if marcadas == 1 else "s",
    )


class _ConEditor:
    """El formulario de usuario sabe quién edita, para no dejarlo darse privilegios."""

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["editor"] = self.request.user
        return kwargs


class UsuarioNuevo(_ConEditor, CrearMantenedor):
    model = PerfilUsuario
    campo_delegacion = "delegacion_id"
    form_class = UsuarioForm
    permiso = PERMISO
    menu = "usuarios"
    singular = "usuario"
    plural = "usuarios"
    genero = "el"
    url_lista = "organizacion:usuarios"
    url_detalle = "organizacion:usuario_detalle"
    lateral = "organizacion/_lateral_usuario.html"
    secciones = [
        ("Datos de la persona", "El correo institucional es además su usuario de acceso.",
         ["codigo", "rut", "nombres", "apellidos", "correo", "cargo"]),
        ("Rol y alcance",
         "El rol decide qué puede hacer. Las delegaciones autorizadas solo "
         "tienen efecto si el alcance del rol es «varias delegaciones».",
         ["rol", "delegacion", "delegaciones_autorizadas"]),
        # El cargo con metas va en su propia sección, y no junto al cargo de
        # texto, porque son cosas distintas que se parecen demasiado de
        # nombre: el de arriba se muestra, este se calcula. Ponerlos uno al
        # lado del otro invitaba a llenar el equivocado.
        ("Cómo se le mide",
         "El cargo con metas decide con qué ítems se evalúa a esta persona. "
         "Sin él, el sistema no tiene metas contra las que medirla y su "
         "resultado queda indefinido, que no es lo mismo que cero.",
         ["cargo_asignado"]),
    ]


class UsuarioEditar(_ConEditor, EditarMantenedor):
    model = PerfilUsuario
    campo_delegacion = "delegacion_id"
    form_class = UsuarioForm
    permiso = PERMISO
    menu = "usuarios"
    singular = "usuario"
    plural = "usuarios"
    genero = "el"
    url_lista = "organizacion:usuarios"
    url_detalle = "organizacion:usuario_detalle"
    lateral = "organizacion/_lateral_usuario.html"
    secciones = UsuarioNuevo.secciones

    def get_queryset(self):
        # Se encauza por limitar(): un get_queryset propio que no lo haga
        # dejaría abierto justamente el camino que se quería cerrar.
        return self.limitar(
            PerfilUsuario.objects.select_related("usuario", "rol", "delegacion",
                                                 "cargo_asignado")
        )

    def get_object(self, queryset=None):
        perfil = super().get_object(queryset)
        _exigir_rol_alcanzable(self.request.user, perfil)
        return perfil


class UsuarioDetalle(DetalleMantenedor):
    desde_aqui = [
        Desde("Asignarle una meta", "gestion:meta_nueva", "asignacion",
              lambda o: {"funcionario": o.usuario_id},
              cuando=lambda o: o.activo and o.cargo_asignado_id, detalle="Una asignación personal"),
        Desde("Registrar actividad a su nombre", "gestion:registro_actividad_nueva", "actividad",
              lambda o: {"funcionario": o.usuario_id, "delegacion": o.delegacion_id},
              cuando=lambda o: o.activo),
    ]
    model = PerfilUsuario
    campo_delegacion = "delegacion_id"
    permiso = PERMISO
    menu = "usuarios"
    singular = "usuario"
    plural = "usuarios"
    genero = "el"
    url_lista = "organizacion:usuarios"
    url_editar = "organizacion:usuario_editar"
    url_estado = "organizacion:usuario_estado"
    campos = [
        ("Código", "codigo", {"mono": True}),
        ("RUT", lambda o: o.rut or "Sin registrar", {"mono": True}),
        ("Nombres", lambda o: o.usuario.first_name),
        ("Apellidos", lambda o: o.usuario.last_name),
        ("Correo de acceso", lambda o: o.correo, {"ancho": True}),
        ("Cargo", "cargo"),
        ("Cargo con metas",
         lambda o: (o.cargo_asignado.nombre if o.cargo_asignado_id else
                    "Sin asignar — no se le puede medir")),
        ("Rol", lambda o: o.rol.nombre),
        ("Alcance del rol", lambda o: o.rol.get_alcance_display()),
        ("Delegación base", lambda o: o.delegacion.nombre),
        ("Delegaciones a las que accede",
         lambda o: ", ".join(d.nombre for d in o.delegaciones_visibles()),
         {"ancho": True}),
        ("Puede iniciar sesión",
         lambda o: "Sí" if o.usuario.has_usable_password() else
                   "Todavía no: debe crear su contraseña con el enlace de recuperación"),
        ("Último acceso",
         lambda o: (o.usuario.last_login.astimezone().strftime("%d-%m-%Y %H:%M")
                    if o.usuario.last_login else "Nunca ha iniciado sesión")),
    ]
    kpis = [
        ("Acciones habilitadas", lambda o: len(o.rol.permisos or []),
         "Las que le da su rol"),
    ]
    pie = "El perfil se desactiva; la cuenta de Django se conserva para el historial."

    def get_queryset(self):
        # Se encauza por limitar(): un get_queryset propio que no lo haga
        # dejaría abierto justamente el camino que se quería cerrar.
        return self.limitar(
            PerfilUsuario.objects.select_related("usuario", "rol", "delegacion",
                                                 "cargo_asignado")
        )


class UsuarioEstado(CambiarEstado):
    model = PerfilUsuario
    campo_delegacion = "delegacion_id"
    permiso = PERMISO
    url_lista = "organizacion:usuarios"
    singular = "usuario"
    genero = "el"

    def motivo_propio(self, request, obj):
        if obj.usuario_id == request.user.pk:
            return "Es tu propia cuenta: la activa o desactiva otra persona."
        if obj.rol not in roles_asignables(request.user) and not P.tiene_permiso(
                request.user, P.GESTIONAR_USUARIO):
            return ("Esa cuenta tiene un rol con más permisos que los tuyos: la "
                    "administra quien gestiona el acceso.")
        return ""


def _exigir_rol_alcanzable(editor, perfil):
    """
    Quien no administra el acceso no edita cuentas con más poder que la suya.

    Si pudiera, le bastaría cambiarle el correo a la cuenta del administrador
    y recuperar su contraseña.
    """
    if perfil.usuario_id == editor.pk or P.tiene_permiso(editor, P.GESTIONAR_USUARIO):
        return
    if perfil.rol not in roles_asignables(editor):
        raise PermissionDenied(
            "Esa cuenta tiene un rol con más permisos que los tuyos: la "
            "administra quien gestiona el acceso.")

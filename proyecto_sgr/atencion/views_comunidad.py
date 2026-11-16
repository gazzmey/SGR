"""
Mantenedores de la comunidad: vecinos, juntas de vecinos, participaciones
en juntas y gestiones sociales (Evaluación 3).

Siguen el patrón de ``comun/mantenedor.py``: cada clase declara qué
muestra, y el motor resuelve listado, búsqueda, filtros, orden, paginador,
exportación, permisos, alcance por delegación y auditoría.

Cómo se elimina
---------------
* Vecinos, juntas y participaciones **se desactivan** (POST con
  confirmación). No se desactiva lo que otros registros activos todavía
  usan: el modelo lo dice en ``motivo_bloqueo()``.
* Las gestiones sociales **se anulan** con un motivo: son atenciones que
  ocurrieron y no pueden desaparecer del historial.
"""

from django.db.models import Count, Q
from django.urls import reverse
from django.utils.html import format_html

from atencion.forms_comunidad import (
    GestionSocialForm, JuntaForm, ParticipacionForm, VecinoForm,
)
from atencion.models import CasoSocial, JuntaVecinos, ParticipacionJunta, Solicitante
from comun import permisos as P
from comun.formularios import nombre_de_usuario
from comun.mantenedor import (
    AnularMantenedor, CambiarEstado, Columna, CrearMantenedor, DetalleMantenedor,
    EditarMantenedor, Filtro, ListaMantenedor, chip_estado, enlace_nombre, filtro_estado,
)
from organizacion.models import Delegacion

PERMISO = P.REGISTRAR_ATENCION


def _territorios():
    from organizacion.models import Territorio

    return [(t.pk, f"{t.nombre} · {t.delegacion.nombre}")
            for t in Territorio.objects.filter(activo=True).select_related("delegacion")]


def _delegaciones():
    return [(d.pk, d.nombre) for d in Delegacion.objects.filter(activo=True)]


# =========================================================================
# Vecinos
# =========================================================================


class _Vecino:
    model = Solicitante
    campo_delegacion = "territorio__delegacion_id"
    permiso = PERMISO
    menu = "vecinos"
    singular = "vecino"
    plural = "vecinos"
    genero = "el"
    url_lista = "atencion:vecinos"
    url_detalle = "atencion:vecino_detalle"


class VecinosLista(_Vecino, ListaMantenedor):
    titulo = "Vecinos"
    bajada = (
        "Las personas que acuden a las delegaciones: su RUT, cómo "
        "contactarlas y en qué territorio viven."
    )
    placeholder = "RUT, nombre, correo o dirección"
    rotulo_nuevo = "Nuevo vecino"
    busca = ["rut", "nombres", "apellidos", "correo", "direccion", "territorio__nombre"]
    orden_inicial = "apellidos"
    url_nueva = "atencion:vecino_nuevo"
    url_editar = "atencion:vecino_editar"
    url_estado = "atencion:vecino_estado"
    filtros = [
        Filtro("territorio", "Territorio", _territorios, campo="territorio_id", vacio="Todos"),
        filtro_estado(),
    ]
    columnas = [
        Columna("rut", "RUT", clase="mono"),
        Columna("apellidos", "Vecino", orden="apellidos", clase="w",
                celda=lambda o: enlace_nombre(
                    o, "atencion:vecino_detalle",
                    extra=format_html('<span class="t2">{}</span>', o.correo or o.telefono or "Sin contacto")),
                valor=lambda o: o.nombre),
        Columna("territorio", "Territorio", orden="territorio__nombre",
                valor=lambda o: o.territorio.nombre if o.territorio_id else (o.sector or "—")),
        Columna("participaciones", "Juntas", orden="n_juntas", alineado="r",
                valor=lambda o: o.n_juntas),
        Columna("estado", "Estado", orden="activo", celda=chip_estado,
                valor=lambda o: "Activo" if o.activo else "Inactivo"),
    ]
    nota = (
        "<b>Datos ficticios.</b> Los RUT del sistema son números con dígito "
        "verificador válido que no corresponden a nadie. Un vecino que "
        "integra una junta no se desactiva sin terminar antes esa participación."
    )

    def base_queryset(self):
        return (Solicitante.objects.select_related("territorio")
                .annotate(n_juntas=Count("participaciones", filter=Q(participaciones__activo=True))))


class VecinoNuevo(_Vecino, CrearMantenedor):
    form_class = VecinoForm
    pasa_usuario = True
    secciones = [
        ("Identificación", "El RUT no se repite entre vecinos.", ["rut", "nombres", "apellidos"]),
        ("Contacto", "Para avisarle cuando su requerimiento se resuelva.",
         ["telefono", "correo", "direccion"]),
        ("Territorio", "Dónde vive. Decide a qué junta de vecinos puede integrarse.", ["territorio"]),
    ]


class VecinoEditar(_Vecino, EditarMantenedor):
    form_class = VecinoForm
    pasa_usuario = True
    secciones = VecinoNuevo.secciones


class VecinoDetalle(_Vecino, DetalleMantenedor):
    url_editar = "atencion:vecino_editar"
    url_estado = "atencion:vecino_estado"
    campos = [
        ("RUT", "rut", {"mono": True}),
        ("Nombres", "nombres"),
        ("Apellidos", "apellidos"),
        ("Teléfono", "telefono"),
        ("Correo", "correo"),
        ("Dirección", "direccion", {"ancho": True}),
        ("Territorio", lambda o: (f"{o.territorio.nombre} · {o.territorio.delegacion.nombre}"
                                  if o.territorio_id else "Sin territorio")),
        ("Sector registrado antes", lambda o: o.sector or "—"),
        ("Juntas en que participa",
         lambda o: ", ".join(f"{p.junta.nombre} ({p.get_cargo_display().lower()})"
                             for p in o.participaciones.filter(activo=True).select_related("junta"))
         or "Ninguna", {"ancho": True}),
        ("Registrado el", lambda o: o.creada.strftime("%d-%m-%Y") if o.creada else ""),
    ]
    kpis = [
        ("Atenciones", lambda o: o.atenciones.count(), "En todas las delegaciones"),
        ("Gestiones sociales", lambda o: CasoSocial.objects.filter(atencion__solicitante=o).count(),
         "Casos abiertos a su nombre"),
    ]
    pie = "Un vecino no se borra: se desactiva y conserva sus atenciones."


class VecinoEstado(CambiarEstado):
    model = Solicitante
    campo_delegacion = "territorio__delegacion_id"
    permiso = PERMISO
    url_lista = "atencion:vecinos"
    singular = "vecino"
    genero = "el"


# =========================================================================
# Juntas de vecinos
# =========================================================================


class _Junta:
    model = JuntaVecinos
    campo_delegacion = "delegacion_id"
    permiso = PERMISO
    menu = "juntas"
    singular = "junta de vecinos"
    plural = "juntas de vecinos"
    genero = "la"
    url_lista = "atencion:juntas"
    url_detalle = "atencion:junta_detalle"


class JuntasLista(_Junta, ListaMantenedor):
    titulo = "Juntas de vecinos"
    bajada = "Las organizaciones comunitarias de cada territorio, con su directiva y sus socios."
    placeholder = "Nombre, código o dirección"
    rotulo_nuevo = "Nueva junta"
    busca = ["codigo", "nombre", "direccion", "territorio__nombre"]
    url_nueva = "atencion:junta_nueva"
    url_editar = "atencion:junta_editar"
    url_estado = "atencion:junta_estado"
    filtros = [
        Filtro("delegacion", "Delegación", _delegaciones, campo="delegacion_id", vacio="Todas"),
        filtro_estado(femenino=True),
    ]
    columnas = [
        Columna("codigo", "Código", clase="mono"),
        Columna("nombre", "Junta", orden="nombre", clase="w",
                celda=lambda o: enlace_nombre(
                    o, "atencion:junta_detalle", femenino=True,
                    extra=format_html('<span class="t2">{}</span>', o.direccion))),
        Columna("territorio", "Territorio", orden="territorio__nombre",
                valor=lambda o: o.territorio.nombre),
        Columna("delegacion", "Delegación", orden="delegacion__nombre",
                valor=lambda o: o.delegacion.nombre),
        Columna("constitucion", "Constituida", orden="fecha_constitucion",
                valor=lambda o: o.fecha_constitucion.strftime("%d-%m-%Y")),
        Columna("socios", "Participantes", orden="n_socios", alineado="r",
                valor=lambda o: o.n_socios),
        Columna("estado", "Estado", orden="activo",
                celda=lambda o: chip_estado(o, femenino=True),
                valor=lambda o: "Activa" if o.activo else "Inactiva"),
    ]
    nota = (
        "<b>La junta es de un territorio de su delegación.</b> Solo pueden "
        "integrarla vecinos que viven en ese territorio, y una junta con "
        "participantes vigentes no se desactiva."
    )

    def base_queryset(self):
        return (JuntaVecinos.objects.select_related("territorio", "delegacion")
                .annotate(n_socios=Count("participaciones", filter=Q(participaciones__activo=True))))


class JuntaNueva(_Junta, CrearMantenedor):
    form_class = JuntaForm
    pasa_usuario = True
    secciones = [
        ("Identificación", "El código se asigna solo.", ["codigo", "nombre", "fecha_constitucion"]),
        ("Ubicación", "El territorio tiene que ser de la delegación elegida.",
         ["delegacion", "territorio", "direccion"]),
    ]


class JuntaEditar(_Junta, EditarMantenedor):
    form_class = JuntaForm
    pasa_usuario = True
    secciones = JuntaNueva.secciones


class JuntaDetalle(_Junta, DetalleMantenedor):
    url_editar = "atencion:junta_editar"
    url_estado = "atencion:junta_estado"
    campos = [
        ("Código", "codigo", {"mono": True}),
        ("Nombre", "nombre"),
        ("Delegación", lambda o: o.delegacion.nombre),
        ("Territorio", lambda o: o.territorio.nombre),
        ("Dirección", "direccion", {"ancho": True}),
        ("Fecha de constitución", lambda o: o.fecha_constitucion.strftime("%d-%m-%Y")),
        ("Directiva vigente",
         lambda o: ", ".join(f"{p.get_cargo_display()}: {p.vecino.nombre}"
                             for p in o.participaciones.filter(activo=True, dirigente=True)
                             .select_related("vecino")) or "Sin directiva registrada",
         {"ancho": True}),
    ]
    kpis = [
        ("Participantes vigentes", lambda o: o.participaciones.filter(activo=True).count(),
         "Socios y dirigentes"),
        ("Dirigentes", lambda o: o.participaciones.filter(activo=True, dirigente=True).count(),
         "Integran la directiva"),
    ]
    pie = "Una junta con participantes vigentes no se desactiva."


class JuntaEstado(CambiarEstado):
    model = JuntaVecinos
    campo_delegacion = "delegacion_id"
    permiso = PERMISO
    url_lista = "atencion:juntas"
    singular = "junta de vecinos"
    genero = "la"


# =========================================================================
# Participaciones en juntas
# =========================================================================


class _Participacion:
    model = ParticipacionJunta
    campo_delegacion = "junta__delegacion_id"
    permiso = PERMISO
    menu = "participaciones"
    singular = "participación"
    plural = "participaciones"
    genero = "la"
    url_lista = "atencion:participaciones"
    url_detalle = "atencion:participacion_detalle"


def _celda_participacion(o):
    return format_html(
        '<a class="link" href="{}">{}</a><span class="t2">{}</span>',
        reverse("atencion:participacion_detalle", args=[o.pk]), o.vecino.nombre, o.vecino.rut)


class ParticipacionesLista(_Participacion, ListaMantenedor):
    titulo = "Participaciones en juntas"
    bajada = "Quién integra cada junta de vecinos, desde cuándo y con qué cargo."
    placeholder = "Vecino, RUT o junta"
    rotulo_nuevo = "Nueva participación"
    busca = ["codigo", "vecino__nombres", "vecino__apellidos", "vecino__rut", "junta__nombre"]
    orden_inicial = "junta__nombre"
    url_nueva = "atencion:participacion_nueva"
    url_editar = "atencion:participacion_editar"
    url_estado = "atencion:participacion_estado"
    filtros = [
        Filtro("junta", "Junta",
               lambda: [(j.pk, j.nombre) for j in JuntaVecinos.objects.filter(activo=True)],
               campo="junta_id", vacio="Todas"),
        Filtro("dirigente", "Condición", [("si", "Dirigentes"), ("no", "Socios")],
               consulta=lambda v: Q(dirigente=(v == "si")), vacio="Todas"),
        Filtro("estado", "Vigencia", [("activos", "Vigentes"), ("inactivos", "Terminadas")],
               consulta=lambda v: Q(activo=(v == "activos")), vacio="Todas"),
    ]
    columnas = [
        Columna("codigo", "Código", clase="mono"),
        Columna("vecino", "Vecino", orden="vecino__apellidos", clase="w",
                celda=_celda_participacion, valor=lambda o: o.vecino.nombre),
        Columna("junta", "Junta", orden="junta__nombre", valor=lambda o: o.junta.nombre),
        Columna("cargo", "Cargo", orden="cargo", valor=lambda o: o.get_cargo_display()),
        Columna("desde", "Desde", orden="fecha_incorporacion",
                valor=lambda o: o.fecha_incorporacion.strftime("%d-%m-%Y")),
        Columna("estado", "Vigencia", orden="activo",
                celda=lambda o: format_html('<span class="chip ok">Vigente</span>') if o.activo
                else format_html('<span class="chip off"><span class="t">Terminada</span></span>'),
                valor=lambda o: "Vigente" if o.activo else "Terminada"),
    ]
    nota = (
        "<b>La membresía es un registro, no un texto.</b> Terminar una "
        "participación la deja en el historial; si la persona vuelve, se "
        "registra una nueva con su fecha."
    )

    def base_queryset(self):
        return ParticipacionJunta.objects.select_related("vecino", "junta")


class ParticipacionNueva(_Participacion, CrearMantenedor):
    form_class = ParticipacionForm
    pasa_usuario = True
    secciones = [
        ("Quién y dónde", "El vecino tiene que vivir en el territorio de la junta.",
         ["codigo", "vecino", "junta"]),
        ("Condición", "Un dirigente ocupa un cargo de la directiva; cada cargo, una persona a la vez.",
         ["dirigente", "cargo", "fecha_incorporacion"]),
    ]


class ParticipacionEditar(_Participacion, EditarMantenedor):
    form_class = ParticipacionForm
    pasa_usuario = True
    secciones = ParticipacionNueva.secciones


class ParticipacionDetalle(_Participacion, DetalleMantenedor):
    url_editar = "atencion:participacion_editar"
    url_estado = "atencion:participacion_estado"
    campos = [
        ("Código", "codigo", {"mono": True}),
        ("Vecino", lambda o: f"{o.vecino.nombre} · {o.vecino.rut}"),
        ("Junta", lambda o: o.junta.nombre),
        ("Territorio", lambda o: o.junta.territorio.nombre),
        ("Es dirigente", lambda o: "Sí" if o.dirigente else "No"),
        ("Cargo", "cargo"),
        ("Fecha de incorporación", lambda o: o.fecha_incorporacion.strftime("%d-%m-%Y")),
        ("Terminada el", lambda o: o.desactivada.strftime("%d-%m-%Y") if o.desactivada else "—"),
    ]
    pie = "Terminar una participación la conserva en el historial de la junta."


class ParticipacionEstado(CambiarEstado):
    model = ParticipacionJunta
    campo_delegacion = "junta__delegacion_id"
    permiso = PERMISO
    url_lista = "atencion:participaciones"
    singular = "participación"
    genero = "la"


# =========================================================================
# Gestiones sociales
# =========================================================================


def _chip_gestion(caso):
    mapa = {
        CasoSocial.Estado.EN_CURSO: ("warn", "En curso"),
        CasoSocial.Estado.CERRADO: ("ok", "Cerrado"),
        CasoSocial.Estado.ANULADO: ("off", "Anulado"),
    }
    clase, texto = mapa.get(caso.estado, ("neu", caso.get_estado_display()))
    if clase == "off":
        return format_html('<span class="chip off"><span class="t">{}</span></span>', texto)
    return format_html('<span class="chip {}">{}</span>', clase, texto)


class _Gestion:
    lateral = "comun/_lateral_anulable.html"
    model = CasoSocial
    campo_delegacion = "atencion__delegacion_id"
    permiso = ""          # solo con permisos de Django: el flujo operativo está en «Casos sociales»
    menu = "gestiones"
    singular = "gestión social"
    plural = "gestiones sociales"
    genero = "la"
    url_lista = "atencion:gestiones"
    url_detalle = "atencion:gestion_detalle"


class GestionesLista(_Gestion, ListaMantenedor):
    titulo = "Gestiones sociales"
    bajada = (
        "Cada atención social con su seguimiento completo: beneficiario, "
        "tipo y subtipo, visita, informe, beneficio, derivación y resultado."
    )
    placeholder = "Código, beneficiario, RUT o subtipo"
    rotulo_nuevo = "Nueva gestión social"
    busca = ["codigo", "atencion__solicitante__nombres", "atencion__solicitante__apellidos",
             "atencion__solicitante__rut", "atencion__subatencion__nombre", "derivacion"]
    orden_inicial = "-ingreso"
    url_nueva = "atencion:gestion_nueva"
    url_editar = "atencion:gestion_editar"
    url_estado = ""
    filtros = [
        Filtro("situacion", "Estado", CasoSocial.Estado.choices, campo="estado", vacio="Todos"),
        Filtro("delegacion", "Delegación", _delegaciones, campo="atencion__delegacion_id", vacio="Todas"),
    ]
    columnas = [
        Columna("codigo", "Código", clase="mono"),
        Columna("beneficiario", "Beneficiario", orden="atencion__solicitante__apellidos", clase="w",
                celda=lambda o: format_html(
                    '<a class="link" href="{}">{}</a><span class="t2">{} · {}</span>',
                    reverse("atencion:gestion_detalle", args=[o.pk]),
                    o.atencion.solicitante.nombre, o.atencion.subatencion.tipo_atencion.nombre,
                    o.atencion.subatencion.nombre),
                valor=lambda o: o.atencion.solicitante.nombre),
        Columna("ingreso", "Ingreso", orden="ingreso", valor=lambda o: o.ingreso.strftime("%d-%m-%Y")),
        Columna("responsable", "Responsable", orden="responsable__first_name",
                valor=lambda o: nombre_de_usuario(o.responsable)),
        Columna("delegacion", "Delegación", orden="atencion__delegacion__nombre",
                valor=lambda o: o.atencion.delegacion.nombre),
        Columna("estado", "Estado", orden="estado", celda=_chip_gestion,
                valor=lambda o: o.get_estado_display()),
    ]
    nota = (
        "<b>Se anula, no se borra.</b> Una gestión social anulada queda en "
        "el listado con su motivo. El seguimiento de plazos de las que están "
        "en curso está en Comunidad › Casos sociales."
    )

    def base_queryset(self):
        return CasoSocial.objects.select_related(
            "atencion__solicitante", "atencion__subatencion__tipo_atencion",
            "atencion__delegacion", "responsable")


class GestionNueva(_Gestion, CrearMantenedor):
    form_class = GestionSocialForm
    pasa_usuario = True
    secciones = [
        ("Quién y qué", "El beneficiario y el tipo de atención. El subtipo tiene que ser del tipo elegido.",
         ["beneficiario", "tipo", "subtipo", "delegacion", "detalle", "documento"]),
        ("Fechas y responsable", "La atención no puede ser posterior al ingreso; ninguna fecha puede ser futura.",
         ["fecha_atencion", "ingreso", "responsable", "asignacion"]),
        ("Seguimiento", "Visita, informe y beneficio, en ese orden.",
         ["requiere_visita", "visita_programada", "visita_realizada", "informe_entregado",
          "devoluciones", "lleva_beneficio", "beneficio_entregado"]),
        ("Actuaciones y resultado", "Lo que se hizo y cómo terminó.",
         ["actuaciones", "derivacion", "resultado", "observacion"]),
    ]


class GestionEditar(_Gestion, EditarMantenedor):
    form_class = GestionSocialForm
    pasa_usuario = True
    secciones = GestionNueva.secciones

    def get_object(self, queryset=None):
        caso = super().get_object(queryset)
        if caso.anulado:
            from django.core.exceptions import PermissionDenied

            raise PermissionDenied("Esta gestión social está anulada: ya no se edita.")
        return caso


class GestionDetalle(_Gestion, DetalleMantenedor):
    template_name = "comun/registro_detalle.html"
    url_editar = "atencion:gestion_editar"
    url_anular = "atencion:gestion_anular"
    campos = [
        ("Código", "codigo", {"mono": True}),
        ("Beneficiario", lambda o: f"{o.atencion.solicitante.nombre} · {o.atencion.solicitante.rut}"),
        ("Tipo de atención", lambda o: o.atencion.subatencion.tipo_atencion.nombre),
        ("Subtipo de atención", lambda o: o.atencion.subatencion.nombre),
        ("Delegación", lambda o: o.atencion.delegacion.nombre),
        ("Qué pidió", lambda o: o.atencion.detalle, {"ancho": True}),
        ("Fecha de atención", lambda o: o.fecha_atencion.strftime("%d-%m-%Y") if o.fecha_atencion else "—"),
        ("Fecha de ingreso", lambda o: o.ingreso.strftime("%d-%m-%Y")),
        ("Responsable", lambda o: nombre_de_usuario(o.responsable)),
        ("Asignación de meta", lambda o: str(o.asignacion) if o.asignacion_id else "Sin asignación"),
        ("Visita", lambda o: ("No requiere" if not o.requiere_visita else
                              "Realizada el %s" % o.visita_realizada.strftime("%d-%m-%Y") if o.visita_realizada else
                              "Programada para el %s" % o.visita_programada.strftime("%d-%m-%Y") if o.visita_programada else
                              "Sin programar")),
        ("Informe", lambda o: o.informe_entregado.strftime("%d-%m-%Y") if o.informe_entregado else "Pendiente"),
        ("Beneficio", lambda o: ("No corresponde" if not o.lleva_beneficio else
                                 o.beneficio_entregado.strftime("%d-%m-%Y") if o.beneficio_entregado else "Pendiente")),
        ("Derivación", lambda o: o.derivacion or "—"),
        ("Actuaciones", lambda o: o.actuaciones or "—", {"ancho": True}),
        ("Resultado", lambda o: o.resultado or "—", {"ancho": True}),
    ]
    kpis = [
        ("Evidencias", lambda o: o.evidencias.filter(anulada=False).count(), "Que la respaldan"),
        ("Devoluciones del informe", lambda o: o.devoluciones, "Antes de aceptarse"),
    ]
    pie = "Una gestión social anulada conserva sus datos y su motivo."

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        obj = ctx["obj"]
        ctx.update({
            "chip_estado": _chip_gestion(obj),
            "anulado": obj.anulado,
            "motivo_anulacion": obj.motivo_anulacion,
            "motivo_bloqueo": "",
        })
        if obj.anulado:
            ctx["url_editar"] = ""
        return ctx


class GestionAnular(_Gestion, AnularMantenedor):
    consecuencia = ("La gestión social sale del seguimiento de plazos y sus "
                    "evidencias quedan anuladas con el mismo motivo.")

    def motivo_bloqueo(self, obj):
        if obj.anulado:
            return "Ya está anulada."
        return ""

    def anular(self, obj, motivo):
        obj.estado = CasoSocial.Estado.ANULADO
        obj.motivo_anulacion = motivo
        obj.save(update_fields=["estado", "motivo_anulacion", "actualizado"])
        obj.evidencias.filter(anulada=False).update(anulada=True, motivo_anulacion=motivo)

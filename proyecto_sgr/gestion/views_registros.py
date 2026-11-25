"""
Hitos, y actividades y evidencias como registros completos (Evaluación 3).

Las tres pantallas siguen el patrón de ``comun/mantenedor.py``. Hitos se
abren con la acción «Configurar períodos» o con el permiso de Django;
actividades y evidencias, solo con permisos de Django: sus flujos de trabajo
(«Mis actividades» y «Validar evidencias») siguen siendo los de siempre.

Cómo se elimina
---------------
* Un hito **se desactiva**, salvo que tenga actividades vigentes.
* Una actividad y una evidencia **se anulan** con un motivo: son el
  respaldo del puntaje y no pueden desaparecer.
"""

from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.urls import reverse
from django.utils.html import format_html

from comun import permisos as P
from comun.formularios import nombre_de_usuario
from comun.mantenedor import (
    Desde,
    AnularMantenedor, CambiarEstado, Columna, CrearMantenedor, DetalleMantenedor,
    EditarMantenedor, Filtro, ListaMantenedor, chip_estado, enlace_nombre, filtro_estado,
)
from gestion.forms_registros import ActividadRegistroForm, EvidenciaRegistroForm, HitoForm
from gestion.modelos_actividad import Actividad, Evidencia
from gestion.models import Hito, Periodo
from organizacion.models import Delegacion


def _delegaciones():
    return [(d.pk, d.nombre) for d in Delegacion.objects.filter(activo=True)]


# =========================================================================
# Hitos
# =========================================================================


class _Hito:
    model = Hito
    campo_delegacion = "delegacion_id"
    permiso = P.CONFIGURAR_PERIODO
    menu = "hitos"
    singular = "hito"
    plural = "hitos"
    genero = "el"
    url_lista = "gestion:hitos"
    url_detalle = "gestion:hito_detalle"


class HitosLista(_Hito, ListaMantenedor):
    titulo = "Hitos"
    bajada = (
        "Lo que la delegación sabe de antemano que va a ocurrir: operativos, "
        "ferias, celebraciones. Con su periodicidad, sus fechas y sus responsables."
    )
    placeholder = "Nombre, código o descripción"
    rotulo_nuevo = "Nuevo hito"
    busca = ["codigo", "nombre", "descripcion", "territorio__nombre"]
    orden_inicial = "fecha_inicio"
    url_nueva = "gestion:hito_nuevo"
    url_editar = "gestion:hito_editar"
    url_estado = "gestion:hito_estado"
    filtros = [
        Filtro("delegacion", "Delegación", _delegaciones, campo="delegacion_id", vacio="Todas"),
        Filtro("periodicidad", "Periodicidad", Hito.Periodicidad.choices, vacio="Todas"),
        filtro_estado(),
    ]
    columnas = [
        Columna("codigo", "Código", clase="mono"),
        Columna("nombre", "Hito", orden="nombre", clase="w",
                celda=lambda o: enlace_nombre(
                    o, "gestion:hito_detalle",
                    extra=format_html('<span class="t2">{}</span>', o.get_periodicidad_display()))),
        Columna("fechas", "Fechas", orden="fecha_inicio",
                valor=lambda o: f"{o.fecha_inicio:%d-%m-%Y} al {o.fecha_termino:%d-%m-%Y}"),
        Columna("delegacion", "Delegación", orden="delegacion__nombre",
                valor=lambda o: o.delegacion.nombre),
        Columna("actividades", "Actividades", orden="n_actividades", alineado="r",
                valor=lambda o: o.n_actividades),
        Columna("estado", "Estado", orden="activo", celda=chip_estado,
                valor=lambda o: "Activo" if o.activo else "Inactivo"),
    ]
    nota = (
        "<b>El hito ordena, no suma.</b> Una actividad puede asociarse a un "
        "hito para ver qué se hizo en cada uno; lo que cuenta para la meta "
        "sigue siendo la actividad aprobada."
    )

    def base_queryset(self):
        return (Hito.objects.select_related("delegacion", "territorio")
                .annotate(n_actividades=Count("actividades", filter=~Q(actividades__estado="anulada"))))


class HitoNuevo(_Hito, CrearMantenedor):
    prellenables = ["delegacion", "territorio"]
    form_class = HitoForm
    pasa_usuario = True
    secciones = [
        ("Identificación", "El código se asigna solo.", ["codigo", "nombre", "descripcion"]),
        ("Cuándo", "El término no puede ser anterior al inicio.",
         ["periodicidad", "fecha_inicio", "fecha_termino"]),
        ("Dónde y quiénes", "El territorio, si se indica, es de la misma delegación; los "
         "responsables trabajan en ella.", ["delegacion", "territorio", "responsables"]),
    ]


class HitoEditar(_Hito, EditarMantenedor):
    form_class = HitoForm
    pasa_usuario = True
    secciones = HitoNuevo.secciones


class HitoDetalle(_Hito, DetalleMantenedor):
    desde_aqui = [
        Desde("Registrar una actividad del hito", "gestion:registro_actividad_nueva", "actividad",
              lambda o: {"hito": o.pk, "delegacion": o.delegacion_id, "territorio": o.territorio_id},
              cuando=lambda o: o.activo, detalle="Con el hito, su delegación y su territorio"),
    ]
    url_editar = "gestion:hito_editar"
    url_estado = "gestion:hito_estado"
    campos = [
        ("Código", "codigo", {"mono": True}),
        ("Nombre", "nombre"),
        ("Periodicidad", "periodicidad"),
        ("Fechas", lambda o: f"Del {o.fecha_inicio:%d-%m-%Y} al {o.fecha_termino:%d-%m-%Y}"),
        ("Delegación", lambda o: o.delegacion.nombre),
        ("Territorio", lambda o: o.territorio.nombre if o.territorio_id else "Toda la delegación"),
        ("Responsables", lambda o: o.nombres_responsables or "—", {"ancho": True}),
        ("Descripción", "descripcion", {"ancho": True}),
    ]
    kpis = [
        ("Actividades asociadas", lambda o: o.actividades.exclude(estado="anulada").count(),
         "Sin contar las anuladas"),
        ("Responsables", lambda o: o.responsables.count(), "Personas a cargo"),
    ]
    pie = "Un hito con actividades asociadas no se desactiva."


class HitoEstado(CambiarEstado):
    model = Hito
    campo_delegacion = "delegacion_id"
    permiso = P.CONFIGURAR_PERIODO
    url_lista = "gestion:hitos"
    singular = "hito"
    genero = "el"


# =========================================================================
# Actividades (registro completo)
# =========================================================================


def chip_actividad(actividad):
    mapa = {
        Actividad.Estado.BORRADOR: ("neu", "Sin evidencia"),
        Actividad.Estado.PENDIENTE: ("warn", "Por validar"),
        Actividad.Estado.APROBADA: ("ok", "Aprobada"),
        Actividad.Estado.RECHAZADA: ("bad", "Rechazada"),
    }
    if actividad.estado == Actividad.Estado.ANULADA:
        return format_html('<span class="chip off"><span class="t">Anulada</span></span>')
    clase, texto = mapa.get(actividad.estado, ("neu", actividad.get_estado_display()))
    return format_html('<span class="chip {}">{}</span>', clase, texto)


class _Actividad:
    lateral = "comun/_lateral_anulable.html"
    model = Actividad
    campo_delegacion = "delegacion_id"
    permiso = ""
    menu = "registro_actividades"
    singular = "actividad"
    plural = "actividades"
    genero = "la"
    url_lista = "gestion:registro_actividades"
    url_detalle = "gestion:registro_actividad"


class RegistroActividades(_Actividad, ListaMantenedor):
    titulo = "Actividades"
    bajada = (
        "Todas las actividades del alcance, con su asignación de meta, su "
        "origen, su territorio y su seguimiento. Cada funcionario registra "
        "las suyas en «Mis actividades»."
    )
    placeholder = "Código, descripción, funcionario o territorio"
    rotulo_nuevo = "Registrar actividad"
    busca = ["codigo", "accion", "detalle", "funcionario__first_name",
             "funcionario__last_name", "territorio__nombre"]
    orden_inicial = "-fecha"
    url_nueva = "gestion:registro_actividad_nueva"
    url_editar = "gestion:registro_actividad_editar"
    url_estado = ""
    filtros = [
        Filtro("situacion", "Estado", Actividad.Estado.choices, campo="estado", vacio="Todos"),
        Filtro("periodo", "Trimestre",
               lambda: [(p.pk, p.nombre) for p in Periodo.objects.filter(activo=True)],
               campo="periodo_id", vacio="Todos"),
        Filtro("delegacion", "Delegación", _delegaciones, campo="delegacion_id", vacio="Todas"),
    ]
    columnas = [
        Columna("codigo", "Código", clase="mono"),
        Columna("fecha", "Fecha", orden="fecha", valor=lambda o: f"{o.fecha:%d-%m-%Y}"),
        Columna("accion", "Actividad", orden="accion", clase="w",
                celda=lambda o: format_html(
                    '<a class="link" href="{}">{}</a><span class="t2">{} · {}</span>',
                    reverse("gestion:registro_actividad", args=[o.pk]), o.accion,
                    nombre_de_usuario(o.funcionario), o.item.nombre),
                valor=lambda o: o.accion),
        Columna("tipo", "Tipo", orden="tipo", valor=lambda o: o.get_tipo_display()),
        Columna("avance", "Avance", orden="avance", alineado="r", valor=lambda o: f"{o.avance} %"),
        Columna("estado", "Estado", orden="estado", celda=chip_actividad,
                valor=lambda o: o.get_estado_display()),
    ]
    nota = (
        "<b>El estado no se edita a mano.</b> Lo cambia la validación de la "
        "evidencia, que hace otra persona. Una actividad se anula con un "
        "motivo; no se borra, porque respalda el puntaje del trimestre."
    )

    def base_queryset(self):
        return Actividad.objects.select_related("funcionario", "item", "periodo", "delegacion")


class RegistroActividadNueva(_Actividad, CrearMantenedor):
    prellenables = ["funcionario", "delegacion", "asignacion", "origen", "solicitante",
                    "territorio", "hito"]
    form_class = ActividadRegistroForm
    pasa_usuario = True
    secciones = [
        ("Quién y a qué meta", "La asignación define la meta y el trimestre, y tiene que medir al funcionario.",
         ["codigo", "funcionario", "delegacion", "asignacion"]),
        ("Qué se hizo", "La fecha cae dentro del trimestre y no es futura.",
         ["fecha", "cantidad", "tipo", "accion", "detalle"]),
        ("Antecedentes", "De dónde vino y dónde ocurrió. El territorio y el hito son de la misma delegación.",
         ["origen", "solicitante", "territorio", "hito"]),
        ("Seguimiento", "La fecha de compromiso no puede ser anterior a la fecha de la actividad.",
         ["responsable", "fecha_compromiso", "apoyo", "avance", "resultado"]),
    ]


class RegistroActividadEditar(_Actividad, EditarMantenedor):
    form_class = ActividadRegistroForm
    pasa_usuario = True
    secciones = RegistroActividadNueva.secciones

    def get_object(self, queryset=None):
        actividad = super().get_object(queryset)
        if actividad.estado == Actividad.Estado.ANULADA:
            raise PermissionDenied("Esta actividad está anulada: ya no se edita.")
        if actividad.periodo.estado == Periodo.Estado.CERRADO:
            raise PermissionDenied("Su trimestre está cerrado: el resultado quedó congelado.")
        return actividad


class RegistroActividadDetalle(_Actividad, DetalleMantenedor):
    desde_aqui = [
        Desde("Adjuntar evidencia", "gestion:registro_evidencia_nueva", "evidencia",
              lambda o: {"origen": "actividad", "actividad": o.pk},
              cuando=lambda o: not o.anulada, detalle="Queda enlazada a esta actividad"),
    ]
    template_name = "comun/registro_detalle.html"
    url_editar = "gestion:registro_actividad_editar"
    url_anular = "gestion:registro_actividad_anular"
    campos = [
        ("Código", "codigo", {"mono": True}),
        ("Fecha", lambda o: f"{o.fecha:%d-%m-%Y}"),
        ("Funcionario", lambda o: nombre_de_usuario(o.funcionario)),
        ("Delegación", lambda o: o.delegacion.nombre),
        ("Asignación de meta", lambda o: str(o.asignacion) if o.asignacion_id else "Sin asignación"),
        ("Trimestre", lambda o: o.periodo.nombre),
        ("Cuánto acredita", lambda o: f"{o.cantidad} {o.item.get_unidad_display().lower()}"),
        ("Tipo", "tipo"),
        ("Descripción", "accion", {"ancho": True}),
        ("Detalle", "detalle", {"ancho": True}),
        ("Origen", "origen"),
        ("Solicitante", lambda o: o.solicitante.nombre if o.solicitante_id else "—"),
        ("Territorio", lambda o: o.territorio.nombre if o.territorio_id else "—"),
        ("Hito", lambda o: o.hito.nombre if o.hito_id else "—"),
        ("Responsable", lambda o: nombre_de_usuario(o.responsable) if o.responsable_id else "—"),
        ("Fecha de compromiso", lambda o: f"{o.fecha_compromiso:%d-%m-%Y}" if o.fecha_compromiso else "—"),
        ("Apoyo", lambda o: o.apoyo or "—"),
        ("Avance", lambda o: f"{o.avance} %"),
        ("Resultado", lambda o: o.resultado or "—", {"ancho": True}),
    ]
    kpis = [
        ("Evidencias", lambda o: o.evidencias.filter(anulada=False).count(), "Vigentes"),
    ]
    pie = "El estado lo cambia la validación de la evidencia; anular deja el motivo."

    def get_queryset(self):
        return super().get_queryset().select_related(
            "funcionario", "delegacion", "asignacion", "periodo", "item",
            "solicitante", "territorio", "hito", "responsable")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        obj = ctx["obj"]
        cerrado = obj.periodo.estado == Periodo.Estado.CERRADO
        ctx.update({
            "chip_estado": chip_actividad(obj),
            "anulado": obj.anulada,
            "motivo_anulacion": obj.motivo_anulacion,
            "motivo_bloqueo": ("Su trimestre está cerrado: el resultado quedó congelado."
                               if cerrado and not obj.anulada else ""),
        })
        if obj.anulada or cerrado:
            ctx["url_editar"] = ""
        return ctx


class RegistroActividadAnular(_Actividad, AnularMantenedor):
    consecuencia = ("La actividad deja de sumar a la meta y sus evidencias "
                    "vigentes quedan anuladas con el mismo motivo.")

    def motivo_bloqueo(self, obj):
        if obj.anulada:
            return "Ya está anulada."
        if obj.periodo.estado == Periodo.Estado.CERRADO:
            return "Su trimestre está cerrado: el resultado quedó congelado. Reábrelo primero."
        return ""

    def anular(self, obj, motivo):
        obj.estado = Actividad.Estado.ANULADA
        obj.motivo_anulacion = motivo
        obj.save(update_fields=["estado", "motivo_anulacion", "actualizada"])
        obj.evidencias.filter(anulada=False).update(anulada=True, motivo_anulacion=motivo)


# =========================================================================
# Evidencias (registro completo)
# =========================================================================


def chip_evidencia(evidencia):
    if evidencia.anulada:
        return format_html('<span class="chip off"><span class="t">Anulada</span></span>')
    mapa = {
        Evidencia.Decision.PENDIENTE: ("warn", "Pendiente"),
        Evidencia.Decision.APROBADA: ("ok", "Aprobada"),
        Evidencia.Decision.RECHAZADA: ("bad", "Rechazada"),
    }
    clase, texto = mapa[evidencia.decision]
    return format_html('<span class="chip {}">{}</span>', clase, texto)


class _Evidencia:
    lateral = "comun/_lateral_anulable.html"
    model = Evidencia
    permiso = ""
    menu = "registro_evidencias"
    singular = "evidencia"
    plural = "evidencias"
    genero = "la"
    url_lista = "gestion:registro_evidencias"
    url_detalle = "gestion:registro_evidencia"

    # La evidencia llega a su delegación por la actividad o por la gestión
    # social: el límite de alcance mira los dos caminos.
    def limitar(self, consulta):
        permitidas = self.delegaciones_permitidas()
        if permitidas is None:
            return consulta
        return consulta.filter(Q(actividad__delegacion_id__in=permitidas)
                               | Q(caso__atencion__delegacion_id__in=permitidas))


class RegistroEvidencias(_Evidencia, ListaMantenedor):
    titulo = "Evidencias"
    bajada = (
        "El respaldo de cada actividad y de cada gestión social, con su autor, "
        "su estado y quién la verificó. Se validan en «Validar evidencias»."
    )
    placeholder = "Código, descripción o referencia"
    rotulo_nuevo = "Nueva evidencia"
    busca = ["codigo", "descripcion", "referencia", "actividad__accion", "caso__codigo"]
    orden_inicial = "-creada"
    url_nueva = "gestion:registro_evidencia_nueva"
    url_editar = "gestion:registro_evidencia_editar"
    url_estado = ""
    filtros = [
        Filtro("decision", "Estado", Evidencia.Decision.choices, vacio="Todos"),
        Filtro("origen", "Respalda", [("actividad", "Actividades"), ("caso", "Gestiones sociales")],
               consulta=lambda v: Q(actividad__isnull=(v != "actividad")), vacio="Todo"),
        Filtro("tipo", "Tipo", Evidencia.Tipo.choices, vacio="Todos"),
    ]
    columnas = [
        Columna("codigo", "Código", clase="mono"),
        Columna("descripcion", "Evidencia", orden="descripcion", clase="w",
                celda=lambda o: format_html(
                    '<a class="link" href="{}">{}</a><span class="t2">{}</span>',
                    reverse("gestion:registro_evidencia", args=[o.pk]), o.descripcion, o.origen_texto),
                valor=lambda o: o.descripcion),
        Columna("tipo", "Tipo", orden="tipo", valor=lambda o: o.get_tipo_display()),
        Columna("autor", "Autor", orden="autor__first_name", valor=lambda o: nombre_de_usuario(o.autor)),
        Columna("creada", "Fecha", orden="creada", valor=lambda o: f"{o.creada:%d-%m-%Y}"),
        Columna("decision", "Estado", orden="decision", celda=chip_evidencia,
                valor=lambda o: "Anulada" if o.anulada else o.get_decision_display()),
    ]
    nota = (
        "<b>Una evidencia, un origen.</b> Cada una respalda exactamente una "
        "actividad o una gestión social. Se edita mientras está pendiente; "
        "después la decide un verificador y solo se puede anular."
    )

    def base_queryset(self):
        return Evidencia.objects.select_related(
            "actividad", "caso", "autor", "verificador", "caso__atencion__solicitante")


class RegistroEvidenciaNueva(_Evidencia, CrearMantenedor):
    prellenables = ["origen", "actividad", "caso"]
    form_class = EvidenciaRegistroForm
    pasa_usuario = True
    secciones = [
        ("Qué respalda", "Una actividad o una gestión social, nunca las dos.",
         ["codigo", "origen", "actividad", "caso"]),
        ("El documento", "Puede ser solo una referencia: el folio del acta o la ruta del archivo.",
         ["tipo", "descripcion", "referencia", "observacion"]),
    ]


class RegistroEvidenciaEditar(_Evidencia, EditarMantenedor):
    form_class = EvidenciaRegistroForm
    pasa_usuario = True
    secciones = RegistroEvidenciaNueva.secciones
    # Solo se edita una evidencia pendiente. Lo decide
    # Evidencia.motivo_no_editable(), que el motor consulta antes de abrir el
    # formulario y antes de guardar (comun/mantenedor.py).


class RegistroEvidenciaDetalle(_Evidencia, DetalleMantenedor):
    template_name = "comun/registro_detalle.html"
    url_editar = "gestion:registro_evidencia_editar"
    url_anular = "gestion:registro_evidencia_anular"
    campos = [
        ("Código", "codigo", {"mono": True}),
        ("Respalda", lambda o: o.origen_texto, {"ancho": True}),
        ("Tipo", "tipo"),
        ("Descripción", "descripcion", {"ancho": True}),
        ("Ubicación o referencia", lambda o: o.referencia or (o.archivo_nombre if o.archivo else "—")),
        ("Autor", lambda o: nombre_de_usuario(o.autor)),
        ("Fecha", lambda o: f"{o.creada:%d-%m-%Y %H:%M}"),
        ("Estado", lambda o: "Anulada" if o.anulada else o.get_decision_display()),
        ("Verificador", lambda o: o.verificador_visible),
        ("Decidida el", lambda o: f"{o.decidida:%d-%m-%Y %H:%M}" if o.decidida else "—"),
        ("Motivo del rechazo", lambda o: o.motivo or "—", {"ancho": True}),
        ("Observación", lambda o: o.observacion or "—", {"ancho": True}),
    ]
    pie = "La decide un verificador que no sea su autor ni quien hizo el trabajo."

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        obj = ctx["obj"]
        ctx.update({
            "chip_estado": chip_evidencia(obj),
            "anulado": obj.anulada,
            "motivo_anulacion": obj.motivo_anulacion,
            "motivo_bloqueo": RegistroEvidenciaAnular.bloqueo_para(self.request.user, obj),
        })
        if not obj.pendiente:
            ctx["url_editar"] = ""
        return ctx


class RegistroEvidenciaAnular(_Evidencia, AnularMantenedor):
    consecuencia = ("Si estaba aprobada, su actividad deja de sumar y queda anulada "
                    "con el mismo motivo.")

    @staticmethod
    def bloqueo_para(usuario, obj):
        if obj.anulada:
            return ""
        if (obj.decision == Evidencia.Decision.APROBADA
                and usuario.pk in (obj.responsable_id_origen, obj.autor_id)):
            return ("Es tu propio trabajo y ya fue aprobado: lo anula otro verificador "
                    "o el administrador.")
        return ""

    def motivo_bloqueo(self, obj):
        if obj.anulada:
            return "Ya está anulada."
        return self.bloqueo_para(self.request.user, obj)

    def anular(self, obj, motivo):
        aprobada = obj.decision == Evidencia.Decision.APROBADA
        obj.anulada = True
        obj.motivo_anulacion = motivo
        obj.save(update_fields=["anulada", "motivo_anulacion"])
        actividad = obj.actividad
        if actividad is None or actividad.estado == Actividad.Estado.ANULADA:
            return
        if aprobada:
            actividad.estado = Actividad.Estado.ANULADA
            actividad.motivo_anulacion = motivo
            actividad.save(update_fields=["estado", "motivo_anulacion"])
        elif not actividad.evidencias.filter(anulada=False).exists():
            # Sin evidencias vigentes, la actividad vuelve a «sin evidencia».
            actividad.estado = Actividad.Estado.BORRADOR
            actividad.save(update_fields=["estado"])

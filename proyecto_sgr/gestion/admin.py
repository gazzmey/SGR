"""Django Admin de períodos, cargos y metas."""

from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from config.admin_base import SoloActivosEnSelectores, activar, desactivar

from .models import (
    Actividad,
    CambioCompromiso,
    Cargo,
    Compromiso,
    Evidencia,
    MetaPeriodo,
    Periodo,
    ReglaCalculo,
)


class MetaInline(SoloActivosEnSelectores, admin.TabularInline):
    """Las metas de un período, desde el período."""

    model = MetaPeriodo
    fields = ("cargo", "item", "meta", "ponderador", "activo")
    selectores_solo_activos = ("cargo", "item")
    ordering = ("cargo", "item")
    extra = 0


@admin.register(Periodo)
class PeriodoAdmin(admin.ModelAdmin):
    list_display = ("codigo", "nombre", "inicio", "termino", "dias", "estado", "activo")
    list_filter = ("estado", "activo")
    search_fields = ("codigo", "nombre", "observacion")
    ordering = ("-inicio",)
    readonly_fields = ("cerrado_el", "cerrado_por")
    inlines = [MetaInline]
    actions = [activar, desactivar]

    @admin.display(description="días")
    def dias(self, obj):
        return obj.dias_totales


@admin.register(Cargo)
class CargoAdmin(admin.ModelAdmin):
    list_display = ("codigo", "nombre", "total_usuarios", "activo")
    list_filter = ("activo",)
    search_fields = ("codigo", "nombre", "descripcion")
    ordering = ("codigo",)
    list_editable = ("activo",)
    actions = [activar, desactivar]

    @admin.display(description="usuarios")
    def total_usuarios(self, obj):
        return obj.perfiles.count()


@admin.register(MetaPeriodo)
class MetaPeriodoAdmin(SoloActivosEnSelectores, admin.ModelAdmin):
    list_display = ("periodo", "cargo", "item", "meta", "ponderador", "activo")
    list_filter = ("activo", "periodo", "cargo")
    search_fields = ("periodo__nombre", "cargo__nombre", "item__nombre")
    ordering = ("periodo", "cargo", "item")
    list_select_related = ("periodo", "cargo", "item")
    selectores_solo_activos = ("periodo", "cargo", "item")
    actions = [activar, desactivar]


@admin.register(ReglaCalculo)
class ReglaCalculoAdmin(admin.ModelAdmin):
    """
    Los parámetros del cálculo.

    Se administran también desde el sistema, en Período → Reglas de cálculo.
    Están aquí porque el administrador tiene que poder revisarlos y
    corregirlos sin depender de que el rol correspondiente exista.
    """

    list_display = ("nombre", "alcance", "tope_aporte", "umbral_realizado",
                    "umbral_ambar", "aprobada", "activo")
    list_filter = ("aprobada", "activo", "convencion_dias")
    search_fields = ("nombre", "observacion", "aprobada_por", "periodo__nombre")
    ordering = ("nombre",)
    list_select_related = ("periodo",)
    actions = [activar, desactivar]

    @admin.display(description="alcance")
    def alcance(self, obj):
        return obj.periodo.nombre if obj.periodo_id else "General"


def _enlace_archivo(evidencia):
    """
    El archivo de la evidencia, abierto por la vista que comprueba permisos.

    El campo ``archivo`` no se edita desde el administrador: reemplazarlo ahí
    saltaría la validación de formato y tamaño, y el enlace que dibuja Django
    apuntaría a una dirección pública que a propósito no existe.
    """
    if not evidencia.archivo:
        return "—"
    return format_html(
        '<a href="{}" target="_blank" rel="noopener">{} · {}</a> {}',
        reverse("gestion:evidencia_archivo", args=[evidencia.pk]),
        evidencia.archivo_formato, evidencia.archivo_nombre, evidencia.archivo_tamano,
    )


class EvidenciaInline(admin.TabularInline):
    """Las evidencias de una actividad, desde la actividad."""

    model = Evidencia
    fields = ("codigo", "descripcion", "referencia", "archivo_enlace", "decision",
              "verificador", "anulada")
    readonly_fields = ("codigo", "archivo_enlace")
    ordering = ("-creada",)
    extra = 0

    @admin.display(description="archivo")
    def archivo_enlace(self, obj):
        return _enlace_archivo(obj)


@admin.register(Actividad)
class ActividadAdmin(admin.ModelAdmin):
    list_display = ("codigo", "fecha", "accion", "item", "cantidad",
                    "funcionario", "delegacion", "estado")
    list_filter = ("estado", "periodo", "delegacion", "item")
    search_fields = ("codigo", "accion", "detalle", "contacto",
                     "funcionario__first_name", "funcionario__email")
    ordering = ("-fecha", "-registrada")
    date_hierarchy = "fecha"
    list_select_related = ("item", "funcionario", "delegacion", "periodo")
    readonly_fields = ("codigo", "registrada", "actualizada")
    inlines = [EvidenciaInline]


@admin.register(Evidencia)
class EvidenciaAdmin(admin.ModelAdmin):
    list_display = ("codigo", "actividad", "descripcion", "autor",
                    "decision", "verificador", "anulada")
    list_filter = ("decision", "anulada")
    search_fields = ("codigo", "descripcion", "referencia",
                     "actividad__codigo", "actividad__accion")
    ordering = ("-creada",)
    list_select_related = ("actividad", "autor", "verificador")
    exclude = ("archivo",)
    readonly_fields = ("codigo", "creada", "decidida", "archivo_enlace",
                       "nombre_original", "tamano")

    @admin.display(description="archivo")
    def archivo_enlace(self, obj):
        return _enlace_archivo(obj)


# =========================================================================
# Agenda colectiva
# =========================================================================


class CambioInline(admin.TabularInline):
    """
    El historial del compromiso, en modo lectura.

    Sin ``extra`` y todo de solo lectura a propósito: el historial se escribe
    desde el sistema, cuando algo pasa de verdad. Dejar agregar filas a mano
    desde el administrador permitiría inventar un pasado que no ocurrió.
    """

    model = CambioCompromiso
    fields = ("cuando", "tipo", "estado_anterior", "estado_nuevo",
              "responsable_anterior", "responsable_nuevo", "quien",
              "observacion")
    readonly_fields = fields
    ordering = ("-cuando",)
    extra = 0
    can_delete = False

    def has_add_permission(self, request, obj):
        return False


@admin.register(Compromiso)
class CompromisoAdmin(admin.ModelAdmin):
    list_display = ("codigo", "solicitante", "territorio", "responsable",
                    "vencimiento", "estado", "puntua")
    list_filter = ("estado", "periodo", "delegacion", "requiere_validacion",
                   "validado", "cerrado_con_atraso")
    search_fields = ("codigo", "solicitante", "territorio", "descripcion",
                     "apoyo", "responsable__first_name", "responsable__email")
    ordering = ("vencimiento", "codigo")
    date_hierarchy = "vencimiento"
    list_select_related = ("responsable", "item", "delegacion", "periodo")
    readonly_fields = ("codigo", "responsable_original", "creado",
                       "actualizado", "cerrado_el", "cerrado_con_atraso",
                       "dias_de_atraso", "validado_el")
    inlines = [CambioInline]

    @admin.display(description="¿puntúa?", boolean=True)
    def puntua(self, obj):
        return obj.aporta


@admin.register(CambioCompromiso)
class CambioCompromisoAdmin(admin.ModelAdmin):
    """
    El historial completo, para auditar.

    Todo de solo lectura y sin poder agregar: es un registro de hechos, no una
    tabla que se edite.
    """

    list_display = ("cuando", "compromiso", "tipo", "estado_anterior",
                    "estado_nuevo", "quien")
    list_filter = ("tipo", "estado_nuevo")
    search_fields = ("compromiso__codigo", "compromiso__solicitante",
                     "observacion")
    ordering = ("-cuando",)
    list_select_related = ("compromiso", "quien", "responsable_anterior",
                           "responsable_nuevo")

    def get_readonly_fields(self, request, obj=None):
        return [campo.name for campo in self.model._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

"""Configuración de Django Admin para los catálogos del SGR."""

from django.contrib import admin

from config.admin_base import SoloActivosEnSelectores, activar, desactivar

from .models import Item, SubAtencion, TipoAtencion


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = (
        "codigo", "nombre", "area", "unidad", "meta", "ponderador", "activo",
    )
    list_filter = ("activo", "area", "unidad")
    search_fields = ("codigo", "nombre", "descripcion")
    ordering = ("codigo",)
    list_editable = ("activo",)
    actions = [activar, desactivar]


class SubAtencionInline(admin.TabularInline):
    """Permite revisar y editar las subatenciones desde su tipo."""

    model = SubAtencion
    fields = ("codigo", "nombre", "documento", "activo")
    ordering = ("codigo",)
    extra = 0


@admin.register(TipoAtencion)
class TipoAtencionAdmin(admin.ModelAdmin):
    list_display = ("codigo", "nombre", "area", "activo", "total_subatenciones")
    list_filter = ("activo", "area")
    search_fields = ("codigo", "nombre", "descripcion")
    ordering = ("codigo",)
    list_editable = ("activo",)
    inlines = [SubAtencionInline]
    actions = [activar, desactivar]

    @admin.display(description="subatenciones")
    def total_subatenciones(self, obj):
        return obj.subatenciones.count()


@admin.register(SubAtencion)
class SubAtencionAdmin(SoloActivosEnSelectores, admin.ModelAdmin):
    list_display = ("codigo", "nombre", "tipo_atencion", "documento", "activo")
    list_filter = ("activo", "documento", "tipo_atencion")
    search_fields = ("codigo", "nombre", "tipo_atencion__nombre")
    ordering = ("tipo_atencion__codigo", "codigo")
    list_select_related = ("tipo_atencion",)
    selectores_solo_activos = ("tipo_atencion",)
    actions = [activar, desactivar]

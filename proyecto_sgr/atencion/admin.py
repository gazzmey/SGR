"""Configuración de Django Admin para la atención ciudadana."""

from django.contrib import admin

from .models import Atencion, Solicitante


class AtencionInline(admin.TabularInline):
    """Las atenciones de una persona, desde su ficha."""

    model = Atencion
    fields = ("registrada", "subatencion", "delegacion", "documento")
    readonly_fields = ("registrada",)
    ordering = ("-registrada",)
    extra = 0
    show_change_link = True


@admin.register(Solicitante)
class SolicitanteAdmin(admin.ModelAdmin):
    list_display = ("rut", "nombre", "territorio", "telefono", "total_atenciones")
    search_fields = ("rut", "nombre", "territorio")
    ordering = ("nombre",)
    inlines = [AtencionInline]

    @admin.display(description="atenciones")
    def total_atenciones(self, obj):
        return obj.atenciones.count()


@admin.register(Atencion)
class AtencionAdmin(admin.ModelAdmin):
    """
    Una atención es un hecho con fecha y responsable.

    Se puede consultar y corregir desde aquí porque el administrador existe
    justamente para eso, pero ``registrada`` es de solo lectura: la pone el
    servidor con ``auto_now_add`` y cambiarla a mano desarmaría los informes
    del período.
    """

    list_display = (
        "registrada", "solicitante", "subatencion", "delegacion", "funcionario",
    )
    list_filter = ("delegacion", "subatencion__tipo_atencion", "subatencion")
    search_fields = (
        "solicitante__rut", "solicitante__nombre",
        "subatencion__nombre", "detalle", "documento",
    )
    ordering = ("-registrada",)
    readonly_fields = ("registrada",)
    list_select_related = ("solicitante", "subatencion", "delegacion", "funcionario")
    autocomplete_fields = ("solicitante",)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """En los selectores solo se ofrece lo que está activo."""
        if db_field.name == "subatencion":
            from catalogos.models import SubAtencion

            kwargs["queryset"] = SubAtencion.objects.filter(
                activo=True, tipo_atencion__activo=True
            ).select_related("tipo_atencion")
        if db_field.name == "delegacion":
            from organizacion.models import Delegacion

            kwargs["queryset"] = Delegacion.objects.filter(activo=True)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

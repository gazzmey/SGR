"""
La auditoría en el administrador de Django: visible y de solo lectura.

Los eventos se muestran para poder revisarlos, pero no se pueden crear,
editar ni borrar. Es la misma regla que en el sistema: el caso INT-03 pide
que la auditoría no se pueda alterar, y dejarla editable aquí sería dejar
abierta por detrás la puerta que se cerró por delante.
"""

from django.contrib import admin

from .models import AlertaRevisada, EventoAuditoria


@admin.register(EventoAuditoria)
class EventoAuditoriaAdmin(admin.ModelAdmin):
    list_display = ("cuando", "quien_texto", "accion", "entidad",
                    "objeto_texto", "origen")
    list_filter = ("accion", "entidad", "delegacion")
    search_fields = ("quien_texto", "entidad", "objeto_texto", "detalle",
                     "antes", "despues")
    date_hierarchy = "cuando"
    ordering = ("-cuando",)
    list_select_related = ("quien", "delegacion")

    def get_readonly_fields(self, request, obj=None):
        return [campo.name for campo in self.model._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(AlertaRevisada)
class AlertaRevisadaAdmin(admin.ModelAdmin):
    list_display = ("cuando", "titulo", "tipo", "delegacion", "quien")
    list_filter = ("tipo", "delegacion")
    search_fields = ("titulo", "detalle", "clave")
    ordering = ("-cuando",)
    list_select_related = ("quien", "delegacion")

    def get_readonly_fields(self, request, obj=None):
        return [campo.name for campo in self.model._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

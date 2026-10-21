"""
Django Admin para los códigos de recuperación.

Es de **solo lectura y sin mostrar el código**. Un administrador necesita
poder revisar que el mecanismo funciona —cuántos códigos se pidieron, si
están vencidos, cuántos intentos hubo— pero no necesita ver los seis
dígitos: si pudiera verlos, podría cambiar la contraseña de cualquier
persona sin su consentimiento. En su lugar se muestra el estado.

Tampoco se permite crear ni modificar: los códigos los emite
``CodigoRecuperacion.emitir()``, que anula los anteriores y fija el
vencimiento. Uno creado a mano se saltaría esas dos reglas.
"""

from django.contrib import admin

from .models import CodigoRecuperacion


@admin.register(CodigoRecuperacion)
class CodigoRecuperacionAdmin(admin.ModelAdmin):
    list_display = ("usuario", "creado", "expira", "estado", "intentos")
    list_filter = ("usado",)
    search_fields = ("usuario__username", "usuario__email")
    ordering = ("-creado",)
    list_select_related = ("usuario",)

    # El código no está en la lista ni en el formulario, a propósito.
    fields = ("usuario", "creado", "expira", "usado", "intentos")
    readonly_fields = fields

    @admin.display(description="estado")
    def estado(self, obj):
        if obj.usado:
            return "Usado"
        if obj.vencido:
            return "Vencido"
        if obj.agotado:
            return "Intentos agotados"
        return "Vigente · %d min" % max(1, round(obj.segundos_restantes / 60))

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

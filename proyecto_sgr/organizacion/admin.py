"""Configuración de Django Admin para la estructura organizacional."""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as UserAdminBase
from django.contrib.auth.models import User

from config.admin_base import SoloActivosEnSelectores, activar, desactivar

from .models import Delegacion, PerfilUsuario, Rol


@admin.register(Delegacion)
class DelegacionAdmin(admin.ModelAdmin):
    list_display = ("codigo", "nombre", "zona", "comuna", "activo", "total_perfiles")
    list_filter = ("activo", "zona")
    search_fields = ("codigo", "nombre", "comuna", "direccion")
    ordering = ("codigo",)
    list_editable = ("activo",)
    actions = [activar, desactivar]

    @admin.display(description="usuarios asignados")
    def total_perfiles(self, obj):
        return obj.perfiles.count()


@admin.register(Rol)
class RolAdmin(admin.ModelAdmin):
    list_display = (
        "codigo", "nombre", "alcance", "total_permisos", "activo", "total_perfiles",
    )
    list_filter = ("activo", "alcance")
    search_fields = ("codigo", "nombre", "descripcion")
    ordering = ("codigo",)
    list_editable = ("activo",)
    actions = [activar, desactivar]

    @admin.display(description="usuarios asignados")
    def total_perfiles(self, obj):
        return obj.perfiles.count()

    @admin.display(description="acciones habilitadas")
    def total_permisos(self, obj):
        """
        Cuántas acciones habilita el rol.

        El detalle se edita cómodamente en el mantenedor de roles, que dibuja
        las casillas agrupadas; aquí el JSONField se ve como texto, así que
        basta con el número para saber si el rol está configurado.
        """
        return len(obj.permisos or [])


@admin.register(PerfilUsuario)
class PerfilUsuarioAdmin(SoloActivosEnSelectores, admin.ModelAdmin):
    list_display = (
        "codigo", "usuario", "nombre_completo", "rol", "delegacion", "activo",
    )
    list_filter = ("activo", "rol", "delegacion")
    filter_horizontal = ("delegaciones_autorizadas",)
    search_fields = (
        "usuario__username",
        "usuario__first_name",
        "usuario__last_name",
        "usuario__email",
    )
    ordering = ("codigo",)
    list_select_related = ("usuario", "rol", "delegacion")
    selectores_solo_activos = ("rol", "delegacion")
    actions = [activar, desactivar]

    @admin.display(description="nombre", ordering="usuario__first_name")
    def nombre_completo(self, obj):
        return obj.usuario.get_full_name() or "—"


class PerfilUsuarioInline(SoloActivosEnSelectores, admin.StackedInline):
    """Permite asignar rol y delegación al crear o editar un usuario."""

    model = PerfilUsuario
    can_delete = False
    verbose_name_plural = "perfil del SGR"
    selectores_solo_activos = ("rol", "delegacion")
    filter_horizontal = ("delegaciones_autorizadas",)
    extra = 0


# Se reemplaza el administrador de usuarios para incorporar el perfil del SGR.
admin.site.unregister(User)


@admin.register(User)
class UserAdmin(UserAdminBase):
    inlines = [PerfilUsuarioInline]
    list_display = (
        "username", "first_name", "last_name", "email",
        "rol_sgr", "delegacion_sgr", "is_active", "is_staff",
    )
    list_filter = (
        "is_active", "is_staff", "is_superuser",
        "perfil__rol", "perfil__delegacion",
    )

    def get_queryset(self, request):
        consulta = super().get_queryset(request)
        return consulta.select_related("perfil__rol", "perfil__delegacion")

    @admin.display(description="rol", ordering="perfil__rol__nombre")
    def rol_sgr(self, obj):
        perfil = getattr(obj, "perfil", None)
        return perfil.rol.nombre if perfil else "—"

    @admin.display(description="delegación", ordering="perfil__delegacion__nombre")
    def delegacion_sgr(self, obj):
        perfil = getattr(obj, "perfil", None)
        return perfil.delegacion.nombre if perfil else "—"

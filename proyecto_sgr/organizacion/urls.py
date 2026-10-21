"""
Rutas de los mantenedores de organización.

Cada mantenedor tiene las mismas cinco rutas, con los mismos sufijos. Es
deliberado: así el nombre de una ruta se adivina y las plantillas compartidas
pueden recibirlo como un dato más.

    ''              listado con búsqueda, filtros, orden y paginador
    'nueva/'        formulario de creación
    '<pk>/'         ficha de consulta
    '<pk>/editar/'  formulario de edición
    '<pk>/estado/'  activar o desactivar (solo POST)
"""

from django.urls import path

from organizacion import views

app_name = "organizacion"

urlpatterns = [
    # --- delegaciones ---
    path("delegaciones/", views.DelegacionesLista.as_view(), name="delegaciones"),
    path("delegaciones/nueva/", views.DelegacionNueva.as_view(), name="delegacion_nueva"),
    path("delegaciones/<int:pk>/", views.DelegacionDetalle.as_view(), name="delegacion_detalle"),
    path("delegaciones/<int:pk>/editar/", views.DelegacionEditar.as_view(), name="delegacion_editar"),
    path("delegaciones/<int:pk>/estado/", views.DelegacionEstado.as_view(), name="delegacion_estado"),

    # --- roles ---
    path("roles/", views.RolesLista.as_view(), name="roles"),
    path("roles/nuevo/", views.RolNuevo.as_view(), name="rol_nuevo"),
    path("roles/<int:pk>/", views.RolDetalle.as_view(), name="rol_detalle"),
    path("roles/<int:pk>/editar/", views.RolEditar.as_view(), name="rol_editar"),
    path("roles/<int:pk>/estado/", views.RolEstado.as_view(), name="rol_estado"),

    # --- usuarios ---
    path("usuarios/", views.UsuariosLista.as_view(), name="usuarios"),
    path("usuarios/nuevo/", views.UsuarioNuevo.as_view(), name="usuario_nuevo"),
    path("usuarios/<int:pk>/", views.UsuarioDetalle.as_view(), name="usuario_detalle"),
    path("usuarios/<int:pk>/editar/", views.UsuarioEditar.as_view(), name="usuario_editar"),
    path("usuarios/<int:pk>/estado/", views.UsuarioEstado.as_view(), name="usuario_estado"),
]

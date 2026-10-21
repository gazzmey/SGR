"""Rutas de los mantenedores de catálogos."""

from django.urls import path

from catalogos import views

app_name = "catalogos"

urlpatterns = [
    # --- ítems y metas ---
    path("items/", views.ItemsLista.as_view(), name="items"),
    path("items/nuevo/", views.ItemNuevo.as_view(), name="item_nuevo"),
    path("items/<int:pk>/", views.ItemDetalle.as_view(), name="item_detalle"),
    path("items/<int:pk>/editar/", views.ItemEditar.as_view(), name="item_editar"),
    path("items/<int:pk>/estado/", views.ItemEstado.as_view(), name="item_estado"),

    # --- tipos de atención ---
    path("tipos-atencion/", views.TiposLista.as_view(), name="tipos"),
    path("tipos-atencion/nuevo/", views.TipoNuevo.as_view(), name="tipo_nuevo"),
    path("tipos-atencion/<int:pk>/", views.TipoDetalle.as_view(), name="tipo_detalle"),
    path("tipos-atencion/<int:pk>/editar/", views.TipoEditar.as_view(), name="tipo_editar"),
    path("tipos-atencion/<int:pk>/estado/", views.TipoEstado.as_view(), name="tipo_estado"),

    # --- subatenciones ---
    path("subatenciones/", views.SubatencionesLista.as_view(), name="subatenciones"),
    path("subatenciones/nueva/", views.SubatencionNueva.as_view(), name="subatencion_nueva"),
    path("subatenciones/<int:pk>/", views.SubatencionDetalle.as_view(), name="subatencion_detalle"),
    path("subatenciones/<int:pk>/editar/", views.SubatencionEditar.as_view(), name="subatencion_editar"),
    path("subatenciones/<int:pk>/estado/", views.SubatencionEstado.as_view(), name="subatencion_estado"),
]

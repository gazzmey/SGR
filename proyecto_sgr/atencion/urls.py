"""Rutas de atención ciudadana."""

from django.urls import path

from atencion import views, views_casos, views_regalos as rg

app_name = "atencion"

urlpatterns = [
    path("ingreso/", views.ingreso, name="ingreso"),
    path("registradas/", views.registradas, name="registradas"),
    path("solicitante/", views.buscar_solicitante, name="buscar_solicitante"),
    path("casos/", views_casos.CasosLista.as_view(), name="casos"),
    path("casos/<int:pk>/", views_casos.caso_detalle, name="caso"),
    path("<int:atencion_pk>/caso/", views_casos.caso_abrir, name="caso_abrir"),

    # --- regalos para niños ---
    path("regalos/", rg.RegalosLista.as_view(), name="regalos"),
    path("regalos/nuevo/", rg.RegaloNuevo.as_view(), name="regalo_nuevo"),
    path("regalos/<int:pk>/", rg.RegaloDetalle.as_view(), name="regalo"),
    path("regalos/<int:pk>/editar/", rg.RegaloEditar.as_view(), name="regalo_editar"),
    path("regalos/<int:pk>/estado/", rg.RegaloEstado.as_view(), name="regalo_estado"),
    path("regalos/<int:pk>/entregar/", rg.RegaloEntregar.as_view(), name="regalo_entregar"),
    path("campanas/", rg.CampanasLista.as_view(), name="campanas"),
    path("campanas/nueva/", rg.CampanaNueva.as_view(), name="campana_nueva"),
    path("campanas/<int:pk>/", rg.CampanaDetalle.as_view(), name="campana_detalle"),
    path("campanas/<int:pk>/editar/", rg.CampanaEditar.as_view(), name="campana_editar"),
    path("campanas/<int:pk>/estado/", rg.CampanaEstado.as_view(), name="campana_estado"),
]

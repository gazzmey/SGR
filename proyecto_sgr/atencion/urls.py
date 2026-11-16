"""Rutas de atención ciudadana."""

from django.urls import path

from atencion import views, views_casos, views_comunidad as vc, views_regalos as rg

app_name = "atencion"

urlpatterns = [
    path("ingreso/", views.ingreso, name="ingreso"),
    path("registradas/", views.registradas, name="registradas"),
    path("solicitante/", views.buscar_solicitante, name="buscar_solicitante"),
    path("casos/", views_casos.CasosLista.as_view(), name="casos"),
    path("casos/<int:pk>/", views_casos.caso_detalle, name="caso"),
    path("<int:atencion_pk>/caso/", views_casos.caso_abrir, name="caso_abrir"),

    # --- Evaluación 3: vecinos, juntas, participaciones y gestiones sociales ---
    path("vecinos/", vc.VecinosLista.as_view(), name="vecinos"),
    path("vecinos/nuevo/", vc.VecinoNuevo.as_view(), name="vecino_nuevo"),
    path("vecinos/<int:pk>/", vc.VecinoDetalle.as_view(), name="vecino_detalle"),
    path("vecinos/<int:pk>/editar/", vc.VecinoEditar.as_view(), name="vecino_editar"),
    path("vecinos/<int:pk>/estado/", vc.VecinoEstado.as_view(), name="vecino_estado"),
    path("juntas/", vc.JuntasLista.as_view(), name="juntas"),
    path("juntas/nueva/", vc.JuntaNueva.as_view(), name="junta_nueva"),
    path("juntas/<int:pk>/", vc.JuntaDetalle.as_view(), name="junta_detalle"),
    path("juntas/<int:pk>/editar/", vc.JuntaEditar.as_view(), name="junta_editar"),
    path("juntas/<int:pk>/estado/", vc.JuntaEstado.as_view(), name="junta_estado"),
    path("participaciones/", vc.ParticipacionesLista.as_view(), name="participaciones"),
    path("participaciones/nueva/", vc.ParticipacionNueva.as_view(), name="participacion_nueva"),
    path("participaciones/<int:pk>/", vc.ParticipacionDetalle.as_view(), name="participacion_detalle"),
    path("participaciones/<int:pk>/editar/", vc.ParticipacionEditar.as_view(), name="participacion_editar"),
    path("participaciones/<int:pk>/estado/", vc.ParticipacionEstado.as_view(), name="participacion_estado"),
    path("gestiones/", vc.GestionesLista.as_view(), name="gestiones"),
    path("gestiones/nueva/", vc.GestionNueva.as_view(), name="gestion_nueva"),
    path("gestiones/<int:pk>/", vc.GestionDetalle.as_view(), name="gestion_detalle"),
    path("gestiones/<int:pk>/editar/", vc.GestionEditar.as_view(), name="gestion_editar"),
    path("gestiones/<int:pk>/anular/", vc.GestionAnular.as_view(), name="gestion_anular"),

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

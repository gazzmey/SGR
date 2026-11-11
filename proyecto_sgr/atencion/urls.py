"""Rutas de atención ciudadana."""

from django.urls import path

from atencion import views, views_casos

app_name = "atencion"

urlpatterns = [
    path("ingreso/", views.ingreso, name="ingreso"),
    path("registradas/", views.registradas, name="registradas"),
    path("solicitante/", views.buscar_solicitante, name="buscar_solicitante"),
    path("casos/", views_casos.CasosLista.as_view(), name="casos"),
    path("casos/<int:pk>/", views_casos.caso_detalle, name="caso"),
    path("<int:atencion_pk>/caso/", views_casos.caso_abrir, name="caso_abrir"),
]

"""Rutas de atención ciudadana."""

from django.urls import path

from atencion import views

app_name = "atencion"

urlpatterns = [
    path("ingreso/", views.ingreso, name="ingreso"),
    path("registradas/", views.registradas, name="registradas"),
    path("solicitante/", views.buscar_solicitante, name="buscar_solicitante"),
]

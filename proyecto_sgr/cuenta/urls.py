"""Rutas de acceso y recuperación de contraseña."""

from django.urls import path

from cuenta import views

app_name = "cuenta"

urlpatterns = [
    path("ingresar/", views.Acceso.as_view(), name="login"),
    path("salir/", views.Salida.as_view(), name="logout"),

    # El recorrido de recuperación, en el orden en que se recorre.
    path("recuperar/", views.recuperar, name="recuperar"),
    path("recuperar/codigo/", views.codigo, name="codigo"),
    path("recuperar/reenviar/", views.reenviar, name="reenviar"),
    path("recuperar/clave/", views.nueva_clave, name="nueva_clave"),
]

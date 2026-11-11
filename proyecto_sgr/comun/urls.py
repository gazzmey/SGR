from django.urls import path

from comun import views, views_observaciones

app_name = "comun"

urlpatterns = [
    path("", views.panel, name="panel"),
    path("delegacion-activa/", views.cambiar_delegacion, name="cambiar_delegacion"),
    path("observaciones/", views_observaciones.recientes, name="observaciones"),
    path("observaciones/nueva/", views_observaciones.nueva, name="observacion_nueva"),
]

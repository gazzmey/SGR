from django.urls import path

from comun import views

app_name = "comun"

urlpatterns = [
    path("", views.panel, name="panel"),
    path("delegacion-activa/", views.cambiar_delegacion, name="cambiar_delegacion"),
]

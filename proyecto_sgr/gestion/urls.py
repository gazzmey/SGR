"""Rutas del período, las actividades, la agenda y el resultado."""

from django.urls import path

from gestion import (
    views,
    views_actividad as va,
    views_agenda as ag,
    views_alertas as al,
    views_informes as inf,
    views_tablero as vt,
)

app_name = "gestion"

urlpatterns = [
    # --- resultado y tablero ---
    path("mi-resultado/", vt.mi_resultado, name="mi_resultado"),
    path("tablero/", vt.tablero, name="tablero"),

    # --- alertas y auditoría ---
    path("alertas/", al.alertas, name="alertas"),
    path("informes/", inf.informes, name="informes"),
    path("alertas/revisar/", al.RevisarAlerta.as_view(), name="alerta_revisar"),
    # La auditoría solo tiene listado: no hay creación, edición ni borrado, y
    # esa ausencia es la protección que pide INT-03.
    path("auditoria/", al.Auditoria.as_view(), name="auditoria"),

    # --- períodos ---
    path("periodos/", views.PeriodosLista.as_view(), name="periodos"),
    path("periodos/nuevo/", views.PeriodoNuevo.as_view(), name="periodo_nuevo"),
    path("periodos/<int:pk>/", views.PeriodoDetalle.as_view(), name="periodo_detalle"),
    path("periodos/<int:pk>/editar/", views.PeriodoEditar.as_view(), name="periodo_editar"),
    path("periodos/<int:pk>/estado/", views.PeriodoEstado.as_view(), name="periodo_estado"),
    # Abrir, cerrar y reabrir: el ciclo del período, no su activo/inactivo.
    path("periodos/<int:pk>/<str:paso>/", views.PeriodoTransicion.as_view(),
         name="periodo_paso"),

    # --- cargos ---
    path("cargos/", views.CargosLista.as_view(), name="cargos"),
    path("cargos/nuevo/", views.CargoNuevo.as_view(), name="cargo_nuevo"),
    path("cargos/<int:pk>/", views.CargoDetalle.as_view(), name="cargo_detalle"),
    path("cargos/<int:pk>/editar/", views.CargoEditar.as_view(), name="cargo_editar"),
    path("cargos/<int:pk>/estado/", views.CargoEstado.as_view(), name="cargo_estado"),

    # --- metas y ponderadores ---
    path("metas/", views.MetasLista.as_view(), name="metas"),
    path("metas/nueva/", views.MetaNueva.as_view(), name="meta_nueva"),
    path("metas/<int:pk>/", views.MetaDetalle.as_view(), name="meta_detalle"),
    path("metas/<int:pk>/editar/", views.MetaEditar.as_view(), name="meta_editar"),
    path("metas/<int:pk>/estado/", views.MetaEstado.as_view(), name="meta_estado"),

    # --- reglas de cálculo ---
    path("reglas/", views.ReglasLista.as_view(), name="reglas"),
    path("reglas/nueva/", views.ReglaNueva.as_view(), name="regla_nueva"),
    path("reglas/<int:pk>/", views.ReglaDetalle.as_view(), name="regla_detalle"),
    path("reglas/<int:pk>/editar/", views.ReglaEditar.as_view(), name="regla_editar"),
    path("reglas/<int:pk>/estado/", views.ReglaEstado.as_view(), name="regla_estado"),

    # --- actividades ---
    path("actividades/", va.MisActividades.as_view(), name="actividades"),
    path("actividades/nueva/", va.actividad_nueva, name="actividad_nueva"),
    path("actividades/<int:pk>/", va.actividad_detalle, name="actividad_detalle"),
    path("actividades/<int:pk>/evidencia/", va.evidencia_nueva, name="evidencia_nueva"),

    # --- agenda colectiva ---
    path("agenda/", ag.Agenda.as_view(), name="agenda"),
    path("agenda/nuevo/", ag.compromiso_nuevo, name="compromiso_nuevo"),
    path("agenda/<int:pk>/", ag.compromiso_detalle, name="compromiso_detalle"),
    path("agenda/<int:pk>/reasignar/", ag.CompromisoReasignar.as_view(),
         name="compromiso_reasignar"),
    path("agenda/<int:pk>/validar/", ag.CompromisoValidar.as_view(),
         name="compromiso_validar"),
    # El paso va al final: así una ruta más específica como «reasignar» se
    # resuelve antes y no la captura este patrón.
    path("agenda/<int:pk>/<str:paso>/", ag.CompromisoTransicion.as_view(),
         name="compromiso_paso"),

    # --- validación de evidencias ---
    path("validar/", va.ColaValidacion.as_view(), name="validar"),
    path("validar/<int:pk>/", va.evidencia_detalle, name="evidencia_detalle"),
    path("validar/<int:pk>/<str:paso>/", va.DecidirEvidencia.as_view(),
         name="evidencia_decidir"),
]

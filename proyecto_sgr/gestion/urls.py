"""Rutas del período, las actividades, la agenda y el resultado."""

from django.urls import path

from gestion import (
    views,
    views_actividad as va,
    views_agenda as ag,
    views_ajustes as aj,
    views_cartas as ct,
    views_versiones as vv,
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
    path("informes/brecha/", inf.brecha, name="brecha"),
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

    # --- historial de parámetros (HU-38) ---
    path("historial/", vv.HistorialParametros.as_view(), name="historial"),

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

    # --- felicitaciones, reclamos y ausencias ---
    path("reconocimientos/", aj.ReconocimientosLista.as_view(), name="reconocimientos"),
    path("reconocimientos/nuevo/", aj.ReconocimientoNuevo.as_view(),
         name="reconocimiento_nuevo"),
    path("reconocimientos/<int:pk>/", aj.ReconocimientoDetalle.as_view(),
         name="reconocimiento_detalle"),
    path("reconocimientos/<int:pk>/editar/", aj.ReconocimientoEditar.as_view(),
         name="reconocimiento_editar"),
    path("reconocimientos/<int:pk>/estado/", aj.ReconocimientoEstado.as_view(),
         name="reconocimiento_estado"),
    path("ausencias/", aj.AusenciasLista.as_view(), name="ausencias"),
    path("ausencias/nueva/", aj.AusenciaNueva.as_view(), name="ausencia_nueva"),
    path("ausencias/<int:pk>/", aj.AusenciaDetalle.as_view(), name="ausencia_detalle"),
    path("ausencias/<int:pk>/editar/", aj.AusenciaEditar.as_view(), name="ausencia_editar"),
    path("ausencias/<int:pk>/estado/", aj.AusenciaEstado.as_view(), name="ausencia_estado"),

    # --- tubo de cartas de oficina de partes ---
    path("cartas/", ct.CartasLista.as_view(), name="cartas"),
    path("cartas/nueva/", ct.CartaNueva.as_view(), name="carta_nueva"),
    path("cartas/<int:pk>/", ct.CartaDetalle.as_view(), name="carta_detalle"),
    path("cartas/<int:pk>/editar/", ct.CartaEditar.as_view(), name="carta_editar"),
    path("cartas/<int:pk>/estado/", ct.CartaEstado.as_view(), name="carta_estado"),

    # --- validación de evidencias ---
    path("validar/", va.ColaValidacion.as_view(), name="validar"),
    path("validar/<int:pk>/", va.evidencia_detalle, name="evidencia_detalle"),
    path("evidencias/<int:pk>/archivo/", va.evidencia_archivo, name="evidencia_archivo"),
    path("validar/<int:pk>/<str:paso>/", va.DecidirEvidencia.as_view(),
         name="evidencia_decidir"),
]

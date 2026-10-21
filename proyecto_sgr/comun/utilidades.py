"""Utilidades pequeñas que comparten varias aplicaciones."""

from django.db.models import Sum


def proximo_codigo(modelo, prefijo, ancho=2):
    """
    El siguiente correlativo de un modelo: DEL-01, DEL-02, …

    Se calcula leyendo el mayor que haya, no contando filas: si alguna vez
    se borra un registro del medio, contar daría un código repetido.

    No es a prueba de dos altas exactamente simultáneas. Para este sistema
    —una persona creando una delegación cada tanto— es suficiente, y la
    restricción ``unique`` de la base es la red de seguridad: si llegara a
    repetirse, la base lo rechaza en vez de guardar basura.
    """
    ultimos = (
        modelo._default_manager
        .filter(codigo__startswith=f"{prefijo}-")
        .values_list("codigo", flat=True)
    )
    mayor = 0
    for codigo in ultimos:
        sufijo = codigo.split("-", 1)[-1]
        if sufijo.isdigit():
            mayor = max(mayor, int(sufijo))
    return f"{prefijo}-{mayor + 1:0{ancho}d}"


def suma_ponderadores(modelo, excluir_pk=None):
    """
    Cuánto suman los ponderadores de los registros activos.

    ``excluir_pk`` deja fuera el que se está editando, para poder sumarle
    aparte el valor nuevo y avisar antes de guardar.
    """
    consulta = modelo._default_manager.filter(activo=True)
    if excluir_pk:
        consulta = consulta.exclude(pk=excluir_pk)
    return consulta.aggregate(total=Sum("ponderador"))["total"] or 0

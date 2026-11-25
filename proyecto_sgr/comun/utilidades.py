"""Utilidades pequeñas que comparten varias aplicaciones."""

from django.db.models import Sum


def proximo_codigo(modelo, prefijo, ancho=2):
    """
    El siguiente correlativo de un modelo: DEL-01, DEL-02, …

    Se calcula leyendo el mayor que haya, no contando filas: si alguna vez
    se borra un registro del medio, contar daría un código repetido.

    Dos altas exactamente simultáneas pueden leer el mismo mayor y proponer
    el mismo código. La restricción ``unique`` de la base lo impide, y
    ``guardar_con_codigo`` reintenta con el siguiente: así nadie recibe un
    error por haber guardado al mismo tiempo que otra persona (DEF-09).
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


def guardar_con_codigo(objeto, prefijo, ancho=2, intentos=12):
    """
    Guarda un registro nuevo con su código correlativo, aunque otra persona
    esté guardando otro del mismo tipo en el mismo instante (DEF-09).

    El protocolo de pruebas (INT-01) mandó dos actividades a la vez: las dos
    calcularon ACT-0042, la base rechazó la segunda por código repetido y esa
    persona recibió un error 500 y perdió lo que había escrito. Ahora, si el
    código ya lo tomó otra alta, se calcula el siguiente y se vuelve a
    guardar. Cada intento va en su propio punto de guardado, así que un
    intento fallido no deja nada a medias.

    También se reintenta, tras una pausa breve, cuando la base responde que
    la otra escritura la tiene ocupada: en MariaDB es un «Deadlock found» y
    en SQLite un «database is locked». En los dos casos la escritura no se
    hizo, y repetirla es lo que recomienda cada motor.
    """
    import random
    import time

    from django.db import IntegrityError, OperationalError, transaction

    modelo = type(objeto)
    for intento in range(intentos):
        try:
            with transaction.atomic():
                objeto.save()
            return objeto
        except IntegrityError:
            tomado = modelo._default_manager.filter(codigo=objeto.codigo).exists()
            if not tomado or intento == intentos - 1:
                raise
            # Con muchas altas a la vez, todas calculan el mismo «siguiente»:
            # una pausa al azar las desfasa para que no vuelvan a chocar.
            time.sleep(random.random() * 0.05 * (intento + 1))
            objeto.codigo = proximo_codigo(modelo, prefijo, ancho)
        except OperationalError as error:
            texto = str(error).lower()
            if intento == intentos - 1 or not ("locked" in texto or "deadlock" in texto):
                raise
            time.sleep(0.05 + random.random() * 0.2)
            objeto.codigo = proximo_codigo(modelo, prefijo, ancho)
    return objeto


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

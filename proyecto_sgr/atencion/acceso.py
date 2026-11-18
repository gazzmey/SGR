"""
Quién puede consultar las atenciones registradas.

Registrar una atención es del rol que atiende (``registrar_atencion``). Mirar
lo registrado es más amplio: también lo necesitan quienes supervisan la
delegación (``ver_tablero``) y quienes administran los registros, que ya ven
las gestiones sociales por el permiso de Django de esa entidad. Ninguno de
ellos gana con esto la posibilidad de registrar: la pantalla es de lectura.

Vive aparte de las vistas para que el menú, el panel y la vista usen la misma
regla sin importarse entre sí.
"""

from comun import permisos as P


def puede_consultar_atenciones(usuario):
    from comun.entidades import puede

    return (
        P.tiene_permiso(usuario, P.REGISTRAR_ATENCION)
        or P.tiene_permiso(usuario, P.VER_TABLERO)
        or puede(usuario, "gestion_social", "view")
    )

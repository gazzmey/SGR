"""
El cierre semanal (regla del cliente, guía de la evaluación 3).

La semana de trabajo va de lunes a domingo. Lo que se hizo en una semana se
ingresa hasta ``dias_gracia_semana`` días después del domingo —con 1, hasta
que termina el lunes siguiente—; desde entonces esa semana está cerrada y no
admite actividades ni gestiones sociales nuevas, ni que se cambie la fecha de
una existente hacia ella.

Por qué: el resultado de la semana se informa y se compara, y si se pudiera
seguir cargando trabajo atrasado cuando ya se informó, el informe dejaría de
cuadrar con el sistema. Es la misma razón por la que un trimestre cerrado no
admite nada, en una escala más corta.

El parámetro vive en la regla de cálculo, como los demás, para cambiarlo sin
tocar código.
"""

from datetime import date, timedelta


def lunes_de(fecha):
    return fecha - timedelta(days=fecha.weekday())


def cierre_de(fecha, gracia):
    """El último día en que todavía se puede ingresar algo de esa semana."""
    return lunes_de(fecha) + timedelta(days=6 + gracia)


def motivo_semana_cerrada(fecha, periodo=None, hoy=None):
    """Por qué esa fecha ya no admite registros, o "" si todavía los admite."""
    if fecha is None:
        return ""
    from gestion.reglas import vigente

    hoy = hoy or date.today()
    gracia = vigente(periodo).dias_gracia_semana
    cierre = cierre_de(fecha, gracia)
    if hoy <= cierre:
        return ""
    lunes = lunes_de(fecha)
    return (
        "La semana del %s al %s se cerró el %s: ya no admite registros "
        "nuevos. Lo de cada semana se ingresa hasta %s."
        % (lunes.strftime("%d-%m"), (lunes + timedelta(days=6)).strftime("%d-%m-%Y"),
           cierre.strftime("%d-%m-%Y"), texto_plazo(gracia))
    )


def texto_plazo(gracia):
    if gracia == 0:
        return "el domingo"
    if gracia == 1:
        return "el lunes siguiente"
    return "%d días después del domingo" % gracia

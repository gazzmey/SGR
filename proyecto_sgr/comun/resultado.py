"""
El resultado de una operación, anunciado con SweetAlert2.

Los requisitos de la entrega piden que las alertas, las confirmaciones y los
**resultados de operación** se comuniquen con SweetAlert2, y que el éxito se
informe únicamente después de guardar. Esas dos frases, juntas, descartan
mostrar el aviso desde el formulario: en ese momento todavía no se sabe si la
operación va a funcionar.

Cómo se resuelve
----------------
La vista guarda el resultado en la **sesión** justo después de que la
operación terminó bien (o mal), y redirige. La página siguiente lo lee, lo
muestra y lo borra. Así:

- el aviso aparece después de guardar, nunca antes;
- sobrevive al redirect, que es lo que hace que recargar no repita el POST;
- se muestra una sola vez, porque se consume al leerlo.

Sin JavaScript el aviso igual se ve: la plantilla lo dibuja dentro de un
``<noscript>`` con el mismo texto.
"""

CLAVE = "sgr_resultado"

ICONOS = {"success", "error", "warning", "info", "question"}


def anunciar(request, titulo, texto="", *, icono="success", acciones=None):
    """
    Deja preparado el aviso que verá la próxima pantalla.

    ``acciones`` es una lista de hasta dos pares ``(texto, url)``. La primera
    es el botón principal; la segunda, la alternativa. Sirven para el caso que
    pide el anexo C6: tras registrar una atención, poder iniciar otra o
    consultar la que se acaba de registrar.

    Las entradas vacías se descartan, para que quien llama pueda escribir una
    acción condicional sin armar la lista aparte.
    """
    if icono not in ICONOS:
        icono = "info"

    request.session[CLAVE] = {
        "titulo": str(titulo),
        "texto": str(texto),
        "icono": icono,
        "acciones": [
            {"texto": str(par[0]), "url": str(par[1])}
            for par in (acciones or []) if par
        ][:2],
    }


def tomar(request):
    """Devuelve el aviso pendiente y lo borra. None si no hay ninguno."""
    sesion = getattr(request, "session", None)
    if sesion is None:
        return None
    return sesion.pop(CLAVE, None)

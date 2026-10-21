"""
Un formulario, un registro: el control de doble envío.

El problema es viejo y conocido: alguien pulsa Guardar dos veces, o la
conexión va lenta y vuelve a intentarlo, o recarga la página después de un
POST. Si el servidor no se defiende, quedan dos atenciones idénticas y nadie
sabe cuál borrar.

Deshabilitar el botón con JavaScript ayuda a la primera persona, pero no es
una defensa: basta con tener JavaScript apagado o reenviar la petición. La
defensa está aquí.

Cómo funciona
-------------
Al dibujar el formulario se genera una ficha de un solo uso y se guarda en la
sesión. El formulario la lleva en un campo oculto. Al recibir el POST:

- si la ficha está en la sesión, se consume y la operación sigue;
- si no está —porque ya se usó, o porque nunca existió— se rechaza.

La sesión es del servidor, así que el navegador no puede inventarse una ficha
válida. Se guardan unas pocas: si alguien abre varios formularios a la vez,
todos funcionan, y las más viejas se van descartando.
"""

import secrets

CLAVE = "sgr_envios"
CAMPO = "envio"
MAXIMO = 12


def nueva_ficha(request):
    """Crea una ficha de un solo uso y la registra en la sesión."""
    ficha = secrets.token_urlsafe(16)
    pendientes = list(request.session.get(CLAVE, []))
    pendientes.append(ficha)
    # Solo las últimas: una sesión larga no debe acumular fichas sin fin.
    request.session[CLAVE] = pendientes[-MAXIMO:]
    return ficha


def consumir(request):
    """
    Gasta la ficha que vino en el POST.

    Devuelve True si era válida; False si no venía, ya se había usado o no
    pertenece a esta sesión.
    """
    ficha = (request.POST.get(CAMPO) or "").strip()
    if not ficha:
        return False

    pendientes = list(request.session.get(CLAVE, []))
    if ficha not in pendientes:
        return False

    pendientes.remove(ficha)
    request.session[CLAVE] = pendientes
    return True

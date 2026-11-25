"""
Cambio obligatorio de la contraseña temporal.

Quien entra con una contraseña temporal (``PerfilUsuario.debe_cambiar_clave``)
no puede abrir ninguna pantalla del sistema hasta cambiarla: cualquier
dirección lo lleva a «Crea tu contraseña». Solo quedan abiertas esa pantalla,
cerrar sesión y los archivos estáticos.

Va en un middleware y no en cada vista para que no haya una pantalla que se
olvide: también vale para direcciones escritas a mano y para el
administrador de Django.
"""

from django.shortcuts import redirect
from django.urls import reverse
from django.utils.cache import add_never_cache_headers


class CambioDeClaveObligatorio:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        usuario = getattr(request, "user", None)
        if usuario is not None and usuario.is_authenticated:
            perfil = getattr(usuario, "perfil", None)
            if perfil is not None and perfil.debe_cambiar_clave:
                libres = (reverse("cuenta:cambiar_clave"), reverse("cuenta:logout"))
                if not (request.path in libres or request.path.startswith("/static/")):
                    return redirect("cuenta:cambiar_clave")
        return self.get_response(request)


class SinCopiaEnElNavegador:
    """
    Las pantallas de una sesión no quedan guardadas en el navegador (DEF-15).

    El protocolo de pruebas en AWS (AWS-02) encontró que, después de cerrar
    sesión, el botón «Atrás» volvía a mostrar el panel con sus datos: el
    navegador lo sacaba de su memoria sin preguntarle al servidor. El
    servidor ya había cerrado la sesión —cualquier acción llevaba al
    ingreso—, pero en un computador compartido la persona siguiente podía
    leer lo que había en pantalla.

    Toda respuesta a una sesión iniciada sale con ``Cache-Control: no-store``,
    salvo las que ya traen su propia regla (la descarga de una evidencia).
    Los archivos estáticos no pasan por aquí: los sirve WhiteNoise antes.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        usuario = getattr(request, "user", None)
        con_sesion = bool(usuario is not None and usuario.is_authenticated)
        respuesta = self.get_response(request)
        if con_sesion and not respuesta.has_header("Cache-Control"):
            add_never_cache_headers(respuesta)
        return respuesta

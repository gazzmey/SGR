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

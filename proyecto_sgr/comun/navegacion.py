"""
De dónde vino la persona, para saber a dónde devolverla.

El botón «Volver» de una ficha tiene un problema que no se nota mientras el
sistema tiene una sola lista. La ficha de un compromiso se abre desde la
agenda, desde las alertas y mañana desde un informe; si «Volver» lleva
siempre a la agenda, quien venía de las alertas termina en otra pantalla,
sin la lista que estaba recorriendo y sin los filtros que había puesto.

La solución es que el enlace diga de dónde viene, con ``?volver=``.

Por qué el parámetro no se usa tal como llega
---------------------------------------------
Porque viene en la dirección, y en la dirección escribe cualquiera. Un
``?volver=https://sitio-ajeno/`` convertiría el botón en una redirección
abierta: basta mandar un correo con un enlace de **este** sistema —dominio
correcto, ruta correcta— para que la persona, al apretar «Volver», aterrice
en una pantalla de contraseña falsa creyendo que sigue adentro.

Por eso solo se aceptan rutas internas, y la comprobación la hace
``url_has_allowed_host_and_scheme``, que es la misma función que usa el
``?next=`` del ``login`` de Django. Se prefiere la de Django antes que una
escrita a mano porque los casos que importan son justamente los raros:
``//otro.sitio`` (sin esquema, el navegador lo toma como absoluto),
``https:/otro.sitio``, ``javascript:``, barras invertidas que Chrome lee como
barras normales. Una validación propia los olvida; esa no.

Por qué no se usa la cabecera ``Referer``
-----------------------------------------
Sería más cómodo —no habría que tocar los enlaces—, pero el navegador no
siempre la manda: las políticas de privacidad la recortan, y al venir de
HTTPS hacia otro origen desaparece. Un «Volver» que funciona a veces es peor
que uno que siempre hace lo mismo, porque nadie sabe qué esperar.
"""

from urllib.parse import urlencode

from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme

#: El nombre del parámetro, en un solo lugar: lo escriben las plantillas y lo
#: leen las vistas, y si alguna vez cambia no puede quedar a medias.
PARAMETRO = "volver"


def _interna(crudo, request):
    """
    ``crudo`` si es una ruta interna de este sistema; si no, ``""``.

    Se exige además que empiece con ``/``. Sin eso, un ``volver=otra-cosa``
    pasaría la validación de Django —no tiene dominio ni esquema— y el
    navegador lo resolvería relativo a la ficha, llevando a una dirección que
    nadie quiso.

    ``allowed_hosts=None`` es lo que deja afuera cualquier dominio: para
    Django equivale a una lista vacía de dominios permitidos, de modo que
    solo pasan las direcciones que no llevan dominio.
    """
    crudo = (crudo or "").strip()
    if not crudo.startswith("/"):
        return ""
    if not url_has_allowed_host_and_scheme(
        crudo, allowed_hosts=None, require_https=request.is_secure()
    ):
        return ""
    return crudo


def _ruta_interna(request):
    """El ``?volver=`` de la dirección de esta petición, ya validado."""
    return _interna(request.GET.get(PARAMETRO), request)


def a_donde_volver(request, por_omision):
    """
    La dirección del botón «Volver».

    ``por_omision`` es el nombre de una ruta: el sitio natural de la ficha,
    el que se usa cuando no viene el parámetro o cuando lo que viene no es
    una ruta interna. Así la pantalla siempre tiene un «Volver» que lleva a
    alguna parte, incluso si alguien la abrió escribiendo la dirección.
    """
    return _ruta_interna(request) or reverse(por_omision)


def con_vuelta(request, ruta, *args):
    """
    La dirección de ``ruta`` conservando el ``?volver=`` que traía esta petición.

    Hace falta para los formularios de la ficha. Al cerrar un compromiso la
    vista redirige a la misma ficha, y sin esto el parámetro se perdería en
    ese salto: la persona vendría de las alertas, cerraría el compromiso y el
    «Volver» la mandaría a la agenda. Justo en el momento en que quiere
    seguir con la alerta siguiente.
    """
    destino_url = reverse(ruta, args=args)
    crudo = _ruta_interna(request)
    if crudo:
        destino_url += "?" + urlencode({PARAMETRO: crudo})
    return destino_url


def consulta_de_vuelta(request):
    """
    El ``?volver=…`` listo para pegar al final de un enlace, o ``""``.

    Lo usan las plantillas de la ficha en el ``action`` de sus formularios.
    Un ``POST`` a una dirección con consulta sigue llegando con esa consulta
    en ``request.GET``, que es lo que permite a la vista conservar el origen
    sin agregar campos ocultos a cada formulario.
    """
    crudo = _ruta_interna(request)
    return "?" + urlencode({PARAMETRO: crudo}) if crudo else ""


def desde_formulario(request, por_omision):
    """
    Lo mismo, cuando el origen viaja como campo oculto de un formulario.

    Lo usa la revisión de alertas, que es un ``POST``: se aprieta «Marcar
    revisada» y la pantalla tiene que volver a la lista de alertas tal como
    estaba, con su período y su filtro.

    Pasa por la misma validación que el parámetro de la dirección, y no es un
    detalle: que el valor venga de un campo oculto no lo vuelve confiable. Un
    campo oculto es parte de la página, y la página la controla el navegador;
    quien quiera cambiarlo solo tiene que abrir las herramientas de
    desarrollo. El CSRF impide que **otro sitio** mande el formulario, no que
    este llegue con el campo alterado.
    """
    return _interna(request.POST.get(PARAMETRO), request) or reverse(por_omision)

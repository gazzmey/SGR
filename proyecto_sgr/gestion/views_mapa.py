"""
La pantalla del mapa de presencia territorial.

Toda la lógica está en ``gestion/mapa.py``; aquí solo se comprueba quién
entra, se leen los filtros y se arma la página. El mapa se dibuja en el
navegador con los mismos datos que la tabla de abajo, que se escribe en el
servidor: si el JavaScript no carga, la tabla sigue diciendo lo mismo.
"""

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import render

from comun.permisos import redirect_al_login
from gestion import mapa as M
from gestion.modelos_actividad import Actividad

#: El orden de la tabla: primero lo que más necesita que alguien vaya.
_GRAVEDAD = {"rojo": 0, "ambar": 1, "verde": 2, "gris": 3}


def _orden(fila):
    dias = fila["dias"]
    return (_GRAVEDAD[fila["semaforo"]], -(dias if dias is not None else 10 ** 6), fila["nombre"])


def mapa(request):
    if not request.user.is_authenticated:
        return redirect_al_login(request)

    modo = M.modo_de(request.user)
    if modo is None:
        messages.error(
            request,
            "No tienes permiso para entrar ahí. Si crees que es un error, "
            "pídele al administrador que revise tu rol.",
        )
        raise PermissionDenied("El mapa de presencia necesita ver el tablero o registrar actividades.")

    delegaciones = M.delegaciones_de(request.user)
    filtros = M.Filtros(request, delegaciones)
    datos = M.calcular(request.user, filtros, modo)
    filas = sorted(datos["territorios"], key=_orden)

    # Lo que viaja al navegador: lo mismo que la tabla, sin nada más.
    para_el_mapa = {
        "modo": modo,
        "presencia": filtros.presencia,
        "presencia_texto": filtros.como_texto(),
        "referencia": filtros.referencia.strftime("%d-%m-%Y"),
        "periodo": filtros.periodo.nombre if filtros.periodo else "",
        "umbral": {"verde": M.VERDE_HASTA, "ambar": M.AMBAR_HASTA},
        "territorios": filas,
    }

    return render(request, "gestion/mapa.html", {
        "menu": "mapa",
        "modo": modo,
        "personal": modo == M.PERSONAL,
        "filtros": filtros,
        "periodo": filtros.periodo,
        "periodos": filtros.periodos,
        "delegaciones": filtros.delegaciones,
        "origenes": Actividad.Origen.choices,
        "tipos": Actividad.Tipo.choices,
        "presencias": list(M.PRESENCIA.items()),
        "filas": filas,
        "olvidados": [f for f in filas if f["semaforo"] == "rojo"][:5],
        "resumen": datos["resumen"],
        "ubicados": datos["ubicados"],
        "sin_ubicar": datos["sin_ubicar"],
        "sin_reconocer": datos["sin_reconocer"],
        "para_el_mapa": para_el_mapa,
        "verde_hasta": M.VERDE_HASTA,
        "ambar_hasta": M.AMBAR_HASTA,
    })

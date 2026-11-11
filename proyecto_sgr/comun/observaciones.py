"""
Qué registros admiten observaciones, y quién puede verlas (HU-24).

«Visible para los participantes autorizados» (criterio 1) se resuelve con
una regla simple: ve y escribe en la conversación de un registro **quien
puede abrir ese registro**. Cada tipo declara aquí esa misma comprobación
que hace su ficha, para que la conversación nunca muestre algo que la ficha
no mostraría.
"""

from django.apps import apps
from django.urls import reverse

from comun import permisos as P


def _visibles(usuario):
    """Los identificadores de delegación que esa persona ve; None es «todas»."""
    perfil = P.perfil_de(usuario)
    if perfil is None:
        return None
    return set(perfil.delegaciones_visibles().values_list("pk", flat=True))


def _en_alcance(usuario, delegacion_id):
    visibles = _visibles(usuario)
    return visibles is None or delegacion_id in visibles


def _puede_compromiso(usuario, obj):
    # La agenda es colectiva: la ficha solo pide haber entrado y que la
    # delegación esté entre las autorizadas.
    return _en_alcance(usuario, obj.delegacion_id)


def _puede_caso(usuario, obj):
    from atencion.views_casos import puede_ver

    return puede_ver(usuario) and _en_alcance(usuario, obj.atencion.delegacion_id)


def _puede_carta(usuario, obj):
    from gestion.views_cartas import puede_ver_cartas

    return puede_ver_cartas(usuario) and _en_alcance(usuario, obj.delegacion_id)


TIPOS = {
    "compromiso": {
        "modelo": "gestion.Compromiso",
        "puede": _puede_compromiso,
        "delegacion": lambda o: o.delegacion_id,
        "url": lambda o: reverse("gestion:compromiso_detalle", args=[o.pk]),
        "texto": lambda o: f"{o.codigo} · {o.solicitante}",
    },
    "caso": {
        "modelo": "atencion.CasoSocial",
        "puede": _puede_caso,
        "delegacion": lambda o: o.atencion.delegacion_id,
        "url": lambda o: reverse("atencion:caso", args=[o.pk]),
        "texto": lambda o: f"{o.codigo} · {o.atencion.subatencion.nombre}",
    },
    "carta": {
        "modelo": "gestion.Carta",
        "puede": _puede_carta,
        "delegacion": lambda o: o.delegacion_id,
        "url": lambda o: reverse("gestion:carta_detalle", args=[o.pk]),
        "texto": lambda o: f"{o.codigo} · {o.remitente}",
    },
}


def registro(tipo, objeto_id):
    """El registro al que apunta una observación, o None si ya no existe."""
    definicion = TIPOS.get(tipo)
    if definicion is None:
        return None
    return apps.get_model(definicion["modelo"]).objects.filter(pk=objeto_id).first()


def puede(usuario, tipo, obj):
    definicion = TIPOS.get(tipo)
    if definicion is None or obj is None or not getattr(usuario, "is_authenticated", False):
        return False
    return definicion["puede"](usuario, obj)


def url_de(tipo, obj):
    return TIPOS[tipo]["url"](obj)


def hilo(request, tipo, obj):
    """Lo que necesita la plantilla para dibujar la conversación de un registro."""
    from comun.models import Observacion

    return {
        "tipo": tipo,
        "objeto": obj.pk,
        "lista": list(
            Observacion.objects.filter(tipo=tipo, objeto_id=obj.pk).select_related("autor")
        ),
        "puede_escribir": puede(request.user, tipo, obj),
        "volver": url_de(tipo, obj),
    }

"""
Cómo se escribe en la auditoría.

Una sola función, ``registrar``, que las vistas llaman cuando ocurre algo que
vale la pena poder reconstruir después. Está aparte del modelo para que
llamarla sea una línea y para que la decisión de qué se audita quede a la
vista en la vista que lo hace, no escondida en una señal.

Por qué no se usan señales de Django
------------------------------------
``post_save`` registraría todo automáticamente, lo que suena cómodo y es
peor: no sabe quién hizo el cambio —el modelo no conoce la petición—, no
distingue un cambio de negocio de una corrección de formato, y llena la
auditoría de ruido hasta que nadie la lee. El caso INT-03 pide poder
reconstruir operaciones concretas; para eso hay que elegirlas.

Nunca hace caer la operación
----------------------------
Si registrar falla, la operación que se estaba auditando ya ocurrió y no
tiene sentido deshacerla por no haber podido anotarla. Se traga la excepción
a propósito. Es la única parte del sistema donde eso está bien, y por eso
está escrito aquí y no repetido en cada vista.
"""

from comun.models import EventoAuditoria


def _ip(request):
    """La dirección de origen, mirando primero la cabecera del proxy."""
    if request is None:
        return None
    reenviada = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if reenviada:
        # La primera de la lista es la del cliente; las demás son los saltos.
        return reenviada.split(",")[0].strip() or None
    return request.META.get("REMOTE_ADDR") or None


def _nombre(usuario):
    if usuario is None or not getattr(usuario, "is_authenticated", False):
        return ""
    return usuario.get_full_name() or usuario.get_username()


def registrar(request, accion, *, entidad, objeto=None, objeto_texto="",
              antes="", despues="", detalle="", delegacion=None):
    """
    Deja un evento en la auditoría.

    ``objeto`` puede ser cualquier registro: se le toman el identificador y
    su representación en texto. Esa representación se copia en vez de
    enlazarse, para que el evento siga siendo legible aunque el registro
    cambie de nombre o se dé de baja.
    """
    try:
        usuario = getattr(request, "user", None)
        if usuario is not None and not getattr(usuario, "is_authenticated", False):
            usuario = None

        if delegacion is None and objeto is not None:
            delegacion = getattr(objeto, "delegacion", None)

        return EventoAuditoria.objects.create(
            quien=usuario,
            quien_texto=_nombre(usuario),
            accion=accion,
            entidad=entidad,
            objeto_id=getattr(objeto, "pk", None),
            objeto_texto=(objeto_texto or (str(objeto) if objeto is not None else ""))[:200],
            delegacion=delegacion,
            antes=str(antes or ""),
            despues=str(despues or ""),
            detalle=str(detalle or ""),
            origen=_ip(request),
        )
    except Exception:
        # La operación auditada ya ocurrió: no se deshace por no haber podido
        # anotarla. Ver el encabezado del módulo.
        return None


def retrato(obj, campos):
    """
    Una línea con el estado de un registro, para los campos que importan.

    Sirve para llenar ``antes`` y ``despues`` sin volcar el objeto entero:
    la auditoría tiene que poder leerse, y un volcado completo no se lee.
    """
    partes = []
    for campo in campos:
        mostrar = getattr(obj, f"get_{campo}_display", None)
        valor = mostrar() if callable(mostrar) else getattr(obj, campo, None)
        if valor is None or valor == "":
            valor = "—"
        partes.append(f"{campo}: {valor}")
    return " · ".join(partes)

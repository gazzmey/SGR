"""
Cómo se escribe una versión de un parámetro (HU-25).

Una sola función, ``versionar``, que llaman las vistas cuando un ítem, una
meta o una regla se crea, se edita, se activa o se desactiva. El modelo
versionado declara tres cosas: ``TIPO_VERSION``, ``datos_version()`` —la foto
de sus campos, legible— y ``vigencia_version()``.

Además está ``congelar_regla``, que es lo que hace que cerrar un período deje
fija la regla con que se midió (CU-68).
"""

from datetime import date

from gestion.modelos_versiones import VersionParametro


def _autor(usuario):
    return usuario if getattr(usuario, "is_authenticated", False) else None


def _periodo(obj):
    return getattr(obj, "periodo", None) if getattr(obj, "periodo_id", None) else None


def versionar(obj, autor=None, antes=None, origen=VersionParametro.Origen.PANTALLA):
    """
    Guarda la versión actual del parámetro, si cambió algo.

    ``antes`` es la foto de cómo estaba, tomada antes de guardar. Solo se usa
    si el parámetro todavía no tiene historia: entonces esa foto se guarda
    como versión 1, para que la versión anterior exista.

    Nunca hace caer la operación: si escribir la versión falla, el cambio ya
    ocurrió y no tiene sentido deshacerlo por no haber podido anotarlo.
    """
    try:
        return _versionar(obj, autor, antes, origen)
    except Exception:  # noqa: BLE001 — mismo criterio que la auditoría
        return None


def _versionar(obj, autor, antes, origen):
    tipo = obj.TIPO_VERSION
    datos = obj.datos_version()
    ultima = (VersionParametro.objects
              .filter(tipo=tipo, objeto_id=obj.pk).order_by("-version").first())

    if ultima is None and antes and antes != datos:
        # Lo de un período rige en las fechas del período; lo general regía
        # hasta hoy, desde una fecha que nadie anotó.
        vigencia = (obj.vigencia_version() if _periodo(obj) is not None
                    else f"Hasta el {date.today():%d-%m-%Y}, antes del historial")
        ultima = VersionParametro.objects.create(
            tipo=tipo, objeto_id=obj.pk, version=1, etiqueta=str(obj)[:200],
            periodo=_periodo(obj), vigencia=vigencia[:200],
            datos=antes, cambios=[], origen=VersionParametro.Origen.PREVIO,
        )

    if ultima is not None and ultima.datos == datos:
        return ultima

    previos = ultima.datos if ultima else {}
    cambios = [
        [campo, previos.get(campo, "—"), valor]
        for campo, valor in datos.items()
        if ultima is not None and previos.get(campo) != valor
    ]
    return VersionParametro.objects.create(
        tipo=tipo, objeto_id=obj.pk,
        version=(ultima.version + 1) if ultima else 1,
        etiqueta=str(obj)[:200], periodo=_periodo(obj),
        vigencia=obj.vigencia_version()[:200],
        datos=datos, cambios=cambios, origen=origen, autor=_autor(autor),
    )


def version_de(obj):
    """El número de la versión vigente del parámetro (1 si nunca cambió)."""
    if obj is None or not getattr(obj, "pk", None):
        return None
    ultima = (VersionParametro.objects
              .filter(tipo=obj.TIPO_VERSION, objeto_id=obj.pk)
              .order_by("-version").values_list("version", flat=True).first())
    return ultima or 1


def cuantas_versiones(obj):
    return VersionParametro.objects.filter(tipo=obj.TIPO_VERSION, objeto_id=obj.pk).count()


def congelar_regla(periodo, autor=None):
    """
    Deja al período con una regla propia, copia de la que lo estaba midiendo.

    Mientras un período usa la regla general, editar la general cambiaría su
    resultado. Al cerrarlo se copia la regla vigente como regla del período
    —que ya no se puede editar mientras siga cerrado—, y así el resultado
    cerrado queda calculado siempre con los mismos parámetros (RF-038.3).

    Si el período ya tenía regla propia, solo se deja constancia de su
    versión al cierre.
    """
    from gestion import reglas as R

    propia = R.ReglaCalculo.objects.filter(periodo=periodo, activo=True).first()
    if propia is not None:
        versionar(propia, autor, origen=VersionParametro.Origen.CIERRE)
        return propia

    origen = R.vigente(periodo)
    copia = R.ReglaCalculo(periodo=periodo)
    excluir = {"id", "nombre", "periodo", "creada", "desactivada", "activo", "observacion"}
    for campo in R.ReglaCalculo._meta.concrete_fields:
        if campo.name not in excluir:
            setattr(copia, campo.attname, getattr(origen, campo.attname))

    base = f"{origen.nombre} · {periodo.codigo}"[:80]
    nombre, n = base, 2
    while R.ReglaCalculo.objects.filter(nombre=nombre).exists():
        sufijo = f" ({n})"
        nombre = base[:80 - len(sufijo)] + sufijo
        n += 1
    copia.nombre = nombre
    copia.activo = True
    copia.observacion = (
        f"Copia congelada al cerrar «{periodo.nombre}» el "
        f"{date.today():%d-%m-%Y}, de la regla «{origen.nombre}». Es la regla "
        "con que quedó medido el período."
    )
    copia.save()
    versionar(copia, autor, origen=VersionParametro.Origen.CIERRE)
    return copia

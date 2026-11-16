"""
Relleno inteligente de los formularios.

Un formulario que se relaciona con registros ya creados no debería obligar a
recorrer listas largas buscando lo que el sistema ya sabe. Este módulo deja
en el HTML lo necesario para que ``static/sgr/js/sgr-relleno.js`` complete el
formulario mientras se llena:

* **Datos en cada opción** (``datos_de_opciones``): el territorio de un
  vecino, la delegación de un territorio, a quiénes mide una asignación de
  meta. Viajan como atributos ``data-*`` de cada ``<option>``.
* **Buscador** (``buscador``): un selector largo se convierte en un campo
  donde se escriben unas letras del nombre, el RUT o el código.
* **Filtro** (``filtra``): las opciones se limitan a las que corresponden a
  lo elegido en otro campo. Si queda una sola, se elige sola.
* **Relleno** (``rellena``): al elegir una opción se completan otros campos
  con sus datos, por ejemplo el territorio al elegir al vecino.
* **Mostrar según** (``muestra_si``): un campo se muestra solo cuando otro
  tiene cierto valor.
* **Sugerencias** (``sugerencias``): un campo de texto libre propone valores
  ya registrados, como los nombres de las juntas de vecinos.

Lo que el navegador completa es solo una propuesta: la persona puede
cambiarlo, lo que eligió a mano no se pisa, y el servidor valida exactamente
igual que antes. Sin JavaScript el formulario funciona como siempre.

Además, ``CrearMantenedor`` acepta valores iniciales por la dirección
(``?solicitante=5``), para abrir un formulario desde la ficha de un registro
con la relación ya puesta. Ver ``prellenables`` en ``comun/mantenedor.py``.
"""

import json
from collections import defaultdict

from django.utils import timezone


def _texto(valor):
    if isinstance(valor, (list, tuple, set)):
        return " ".join(str(v) for v in sorted(valor, key=str))
    if valor is True:
        return "1"
    return str(valor)


def datos_de_opciones(campo, funcion):
    """
    Agrega atributos ``data-*`` a cada opción de un ``ModelChoiceField``.

    ``funcion`` recibe el registro de la opción y devuelve un diccionario
    ``{"territorio": 4, "detalle": "…"}``. Los valores vacíos no se escriben.
    Se puede llamar varias veces sobre el mismo campo: los datos se suman.
    """
    widget = campo.widget
    crear = widget.create_option

    def create_option(name, value, label, selected, index, subindex=None, attrs=None):
        opcion = crear(name, value, label, selected, index, subindex=subindex, attrs=attrs)
        instancia = getattr(value, "instance", None)
        if instancia is not None:
            for clave, dato in funcion(instancia).items():
                if dato in (None, "", False) or dato == [] or dato == set():
                    continue
                opcion["attrs"][f"data-{clave}"] = _texto(dato)
        return opcion

    widget.create_option = create_option


def buscador(campo, ayuda="Escribe parte del nombre, el RUT o el código"):
    """El selector se usa escribiendo, con las coincidencias a la vista."""
    campo.widget.attrs["data-buscador"] = ayuda


def filtra(campo, segun, *, dato=None, de=None, lista=False, autoelige=False, aviso="", vacio=""):
    """
    Limita las opciones a las que corresponden con el campo ``segun``.

    Se compara el ``data-<dato>`` de cada opción con el valor elegido en
    ``segun`` o, si se indica ``de``, con el ``data-<de>`` de la opción elegida
    allí. Con ``lista``, el dato de la opción es una lista separada por
    espacios y basta con que contenga el valor. Con ``autoelige``, si queda
    una sola opción se elige sola. La opción ya elegida nunca se esconde.
    ``aviso`` explica el filtro bajo el campo; ``vacio``, por qué no quedó
    ninguna opción.
    """
    campo.widget.attrs["data-filtra"] = json.dumps({
        "segun": segun, "dato": dato or segun, "de": de or "",
        "lista": lista, "autoelige": autoelige, "aviso": aviso, "vacio": vacio,
    })


def rellena(campo, destinos, motivo):
    """
    Al elegir una opción, completa otros campos con sus datos.

    ``destinos`` es ``{"campo_destino": "dato_de_la_opcion"}``. ``motivo``
    es el texto que se muestra junto al campo completado, por ejemplo
    «según el vecino».
    """
    campo.widget.attrs["data-rellena"] = json.dumps(destinos)
    campo.widget.attrs["data-motivo"] = motivo


def muestra_si(campo, segun, valor):
    """El campo se muestra solo si ``segun`` vale ``valor``."""
    campo.widget.attrs["data-muestra-si"] = json.dumps({"segun": segun, "valor": valor})


def elige_si_unica(campo):
    """Si el selector tiene una sola opción posible, se elige sola."""
    campo.widget.attrs["data-autoelige"] = "1"


def sugerencias(campo, valores, *, rellena_con=None, motivo=""):
    """
    Un campo de texto libre que propone valores ya registrados.

    ``valores`` es una lista de diccionarios ``{"valor": …, "detalle": …}``
    con, opcionalmente, más datos que ``rellena_con`` usa para completar
    otros campos: ``{"territorio": "territorio"}``.
    """
    campo.widget.attrs["data-sugerencias"] = json.dumps(valores, ensure_ascii=False)
    campo.widget.attrs["autocomplete"] = "off"
    if rellena_con:
        campo.widget.attrs["data-rellena"] = json.dumps(rellena_con)
        campo.widget.attrs["data-motivo"] = motivo


# -------------------------------------------------------------------------
# Datos que se repiten en varios formularios
# -------------------------------------------------------------------------


def rut_legible(rut):
    from comun.rut import limpiar_rut

    limpio = limpiar_rut(rut or "").replace("-", "")
    cuerpo, dv = limpio[:-1], limpio[-1:]
    if not cuerpo.isdigit() or not dv:
        return rut or ""
    return f"{int(cuerpo):,}".replace(",", ".") + f"-{dv}"


def datos_vecino(vecino):
    territorio = vecino.territorio if vecino.territorio_id else None
    return {
        "nombre": vecino.nombre,
        "territorio": vecino.territorio_id,
        "delegacion": territorio.delegacion_id if territorio else None,
        "detalle": " · ".join(filter(None, [
            rut_legible(vecino.rut), territorio.nombre if territorio else "sin territorio"])),
        "busca": vecino.rut,
    }


def datos_territorio(territorio):
    return {"delegacion": territorio.delegacion_id, "detalle": territorio.delegacion.nombre}


def datos_persona(usuario):
    perfil = getattr(usuario, "perfil", None)
    if perfil is None:
        return {}
    cargo = perfil.cargo_asignado if perfil.cargo_asignado_id else None
    return {
        "delegacion": perfil.delegacion_id,
        "cargo": perfil.cargo_asignado_id,
        "detalle": " · ".join(filter(None, [
            cargo.nombre if cargo else "", perfil.delegacion.nombre if perfil.delegacion_id else ""])),
        "busca": usuario.email,
    }


def quienes_mide(asignaciones):
    """
    ``{pk de asignación: {pk de usuario, …}}``: a quiénes mide cada una.

    Una asignación personal mide a esa persona. Una del cargo mide a todos
    los que tienen ese cargo, salvo en la meta donde alguien tiene una
    asignación personal en el mismo trimestre: ahí manda la suya. Es la misma
    regla que ``gestion.calculo.metas_de``.
    """
    from gestion.models import MetaPeriodo
    from organizacion.models import PerfilUsuario

    asignaciones = list(asignaciones)
    if not asignaciones:
        return {}
    por_cargo = defaultdict(set)
    for usuario_id, cargo_id in (PerfilUsuario.objects
                                 .filter(activo=True, cargo_asignado__isnull=False)
                                 .values_list("usuario_id", "cargo_asignado_id")):
        por_cargo[cargo_id].add(usuario_id)
    periodos = {a.periodo_id for a in asignaciones}
    personales = set(MetaPeriodo.objects
                     .filter(activo=True, funcionario__isnull=False, periodo_id__in=periodos)
                     .values_list("periodo_id", "item_id", "funcionario_id"))
    resultado = {}
    for a in asignaciones:
        if a.funcionario_id:
            resultado[a.pk] = {a.funcionario_id}
        else:
            resultado[a.pk] = {u for u in por_cargo.get(a.cargo_id, ())
                               if (a.periodo_id, a.item_id, u) not in personales}
    return resultado


def hoy():
    return timezone.localdate()


def _primeros_distintos(valores, cuantos):
    vistos = []
    for valor in valores:
        if valor and valor not in vistos:
            vistos.append(valor)
            if len(vistos) == cuantos:
                break
    return set(vistos)


def vecinos_recientes(usuario, cuantos=5):
    """Los vecinos con que esa persona registró algo hace poco."""
    from atencion.models import CasoSocial
    from gestion.modelos_actividad import Actividad

    if not getattr(usuario, "is_authenticated", False):
        return set()
    desde_actividades = (Actividad.objects.filter(funcionario=usuario, solicitante__isnull=False)
                         .order_by("-registrada").values_list("solicitante_id", flat=True)[:40])
    desde_casos = (CasoSocial.objects.filter(responsable=usuario)
                   .order_by("-ingreso").values_list("atencion__solicitante_id", flat=True)[:40])
    return _primeros_distintos(list(desde_actividades) + list(desde_casos), cuantos)


def asignaciones_recientes(usuario, cuantos=3):
    """Las asignaciones a las que esa persona sumó actividades hace poco."""
    from gestion.modelos_actividad import Actividad

    if not getattr(usuario, "is_authenticated", False):
        return set()
    usadas = (Actividad.objects.filter(funcionario=usuario, asignacion__isnull=False)
              .order_by("-registrada").values_list("asignacion_id", flat=True)[:40])
    return _primeros_distintos(usadas, cuantos)


def sugerencias_comunidad(delegacion, *, cuantos=300):
    """
    Juntas de vecinos y vecinos de una delegación, para proponer en un campo
    de texto libre («quién lo pidió», «con quién se coordinó»). Cada uno
    lleva el nombre de su territorio, para completarlo, y el origen
    «externo» de la agenda: lo pidió la comunidad.
    """
    from atencion.models import JuntaVecinos, Solicitante

    if delegacion is None:
        return []
    valores = []
    for junta in (JuntaVecinos.objects.filter(activo=True, delegacion=delegacion)
                  .select_related("territorio").order_by("nombre")):
        valores.append({"valor": junta.nombre, "detalle": f"Junta de vecinos · {junta.territorio.nombre}",
                        "territorio": junta.territorio.nombre, "origen": "externo"})
    for vecino in (Solicitante.objects.filter(activo=True, territorio__delegacion=delegacion)
                   .select_related("territorio").order_by("apellidos", "nombres")[:cuantos]):
        valores.append({"valor": vecino.nombre,
                        "detalle": f"Vecino · {rut_legible(vecino.rut)} · {vecino.territorio.nombre}",
                        "territorio": vecino.territorio.nombre, "busca": vecino.rut,
                        "origen": "externo"})
    return valores


def sugerencias_territorios(delegacion):
    from organizacion.models import Territorio

    if delegacion is None:
        return []
    return [{"valor": t.nombre, "detalle": t.descripcion[:70] if t.descripcion else ""}
            for t in Territorio.objects.filter(activo=True, delegacion=delegacion).order_by("nombre")]

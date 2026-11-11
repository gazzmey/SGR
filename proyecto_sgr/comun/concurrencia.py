"""
Ediciones simultáneas: que nadie pise el cambio de otro sin saberlo (HU-23).

El problema
-----------
Dos personas abren la misma ficha. La primera guarda. La segunda, que todavía
tiene en pantalla los datos de antes, guarda después y pisa el cambio de la
primera sin que ninguna de las dos se entere. Es la «sobrescritura
silenciosa» que prohíbe el RF-034.2.

La solución: control optimista
------------------------------
Al abrir el formulario se calcula una **huella** del registro tal como está
guardado —un resumen de todos sus campos— y viaja oculta en el formulario.
Al guardar se vuelve a calcular con lo que hay en la base en ese momento:

    · si coincide, nadie tocó el registro entretanto y se guarda;
    · si no coincide, alguien lo cambió. No se guarda: se muestra lo que
      está guardado ahora junto a lo que la persona escribió, y la huella
      se actualiza. Si después de revisarlo vuelve a guardar, lo hace
      sabiendo lo que pisa: deja de ser silencioso (CU-67).

Se prefirió esto a bloquear el registro mientras alguien lo edita
(control pesimista) porque un bloqueo que nadie libera —una pestaña que se
cierra, un corte de luz en la delegación— deja el registro tomado sin que
nadie sepa por qué. Con la huella no hay nada que liberar.

Por qué una huella y no un número de versión
--------------------------------------------
Un campo ``version`` en cada tabla obliga a migrar todas y a acordarse de
incrementarlo en cada guardado, incluidos el administrador de Django y los
comandos. La huella se calcula de los datos mismos: cualquier cambio, venga
de donde venga, la mueve.
"""

import hashlib
import json

from django import forms
from django.db import models

#: El nombre del campo oculto. Va en un solo lugar porque lo escriben las
#: plantillas y lo leen las vistas.
CAMPO = "_huella"


def huella(obj):
    """Un resumen corto de todos los campos guardados del registro."""
    valores = [
        (campo.attname, str(campo.value_from_object(obj)))
        for campo in obj._meta.concrete_fields
    ]
    return hashlib.sha256(
        json.dumps(valores, ensure_ascii=False).encode("utf-8")
    ).hexdigest()[:24]


def hay_conflicto(request, obj):
    """
    True si el formulario se abrió sobre una versión que ya no es la guardada.

    Un envío sin huella —un formulario abierto antes de esta versión del
    sistema, o una herramienta externa— no se bloquea: no hay contra qué
    comparar, y rechazarlo sería romper algo que antes funcionaba.
    """
    enviada = (request.POST.get(CAMPO) or "").strip()
    return bool(enviada) and enviada != huella(obj)


def _legible(campo_form, valor):
    """El valor como lo vería una persona: la etiqueta del selector, «Sí»…"""
    if valor in (None, "", []):
        return "—"
    if isinstance(valor, bool):
        return "Sí" if valor else "No"
    if isinstance(valor, (list, tuple)):
        return ", ".join(_legible(campo_form, v) for v in valor) or "—"
    if isinstance(valor, models.Model):
        return str(valor)
    opciones = getattr(campo_form, "choices", None)
    if opciones is not None:
        for clave, etiqueta in opciones:
            clave = getattr(clave, "value", clave)
            if str(clave) == str(valor):
                return str(etiqueta)
    if hasattr(valor, "strftime"):
        return valor.strftime("%d-%m-%Y")
    return str(valor)


def diferencias(form):
    """
    Los campos donde lo guardado ahora y lo escrito por la persona difieren.

    ``form`` tiene que estar ligado a los datos enviados y construido sobre
    el registro recién leído de la base: su ``initial`` es entonces lo que
    está guardado, y su ``data`` lo que la persona escribió.
    """
    salida = []
    for nombre, campo in form.fields.items():
        if nombre.startswith("_"):
            continue
        # Lo que nunca se repite en pantalla: una contraseña o un archivo.
        if isinstance(campo.widget, (forms.PasswordInput, forms.FileInput)):
            continue
        guardado = form.initial.get(nombre, campo.initial)
        bruto = form[nombre].value()
        try:
            escrito = campo.clean(bruto)
        except Exception:  # noqa: BLE001 — un valor inválido se muestra tal cual
            escrito = bruto
        if isinstance(guardado, models.Model):
            guardado_cmp = guardado.pk
        else:
            guardado_cmp = guardado
        escrito_cmp = escrito.pk if isinstance(escrito, models.Model) else escrito
        if str(guardado_cmp if guardado_cmp is not None else "") == str(
                escrito_cmp if escrito_cmp is not None else ""):
            continue
        if isinstance(guardado, (int, str)) and hasattr(campo, "queryset"):
            guardado = campo.queryset.filter(pk=guardado).first() or guardado
        salida.append({
            "campo": str(campo.label or nombre),
            "guardado": _legible(campo, guardado),
            "escrito": _legible(campo, escrito),
        })
    return salida

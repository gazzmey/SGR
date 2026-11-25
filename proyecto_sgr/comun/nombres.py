"""
Nombres que no se pueden repetir, aunque se escriban distinto (DEF-03).

La base de datos exige nombres únicos en delegaciones, roles, cargos, ítems,
tipos y subtipos de atención, pero compara letra por letra: «Las Compañías»
y «LAS COMPAÑIAS» le parecían dos nombres distintos. La búsqueda del sistema,
en cambio, ya los trata como iguales, así que el catálogo terminaba con dos
entradas que la gente no distingue y que dividían los conteos.

Aquí se comparan como los compara una persona: sin distinguir mayúsculas,
tildes ni espacios repetidos.
"""

import re
import unicodedata

from django import forms


def normalizar(texto):
    """«  Las  COMPAÑÍAS » → «las companias»."""
    plano = unicodedata.normalize("NFKD", texto or "")
    plano = "".join(ch for ch in plano if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", plano).strip().casefold()


def repetido(modelo, nombre, excluir_pk=None, campo="nombre"):
    """El registro que ya tiene ese nombre escrito de cualquier forma, o None."""
    buscado = normalizar(nombre)
    if not buscado:
        return None
    otros = modelo._default_manager.all()
    if excluir_pk:
        otros = otros.exclude(pk=excluir_pk)
    # Los catálogos son cortos (decenas de filas): se comparan en Python para
    # que la regla sea la misma en SQLite y en MariaDB, sin depender de la
    # colación de cada motor.
    for otro in otros.only("pk", campo, *(["codigo"] if hasattr(modelo, "codigo") else [])):
        if normalizar(getattr(otro, campo)) == buscado:
            return otro
    return None


class NombreSinRepetir:
    """
    Mezcla para los formularios de catálogo: rechaza un nombre que ya existe
    escrito de otra forma. Solo actúa si el campo ``nombre`` del modelo es
    único; en los demás modelos no hace nada.
    """

    def clean_nombre(self):
        nombre = re.sub(r"\s+", " ", (self.cleaned_data.get("nombre") or "")).strip()
        modelo = self._meta.model
        try:
            unico = modelo._meta.get_field("nombre").unique
        except Exception:
            unico = False
        if unico:
            otro = repetido(modelo, nombre, excluir_pk=self.instance.pk)
            if otro is not None:
                igual = getattr(otro, "nombre", "") == nombre
                raise forms.ValidationError(
                    f"Ya existe «{otro}»"
                    + ("." if igual else ", que es el mismo nombre escrito con otras mayúsculas, tildes o espacios.")
                    + " Usa ese registro o elige un nombre distinto."
                )
        return nombre

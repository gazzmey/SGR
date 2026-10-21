"""
Etiquetas de plantilla del SGR.

Son pocas a propósito: todo lo que se puede resolver en la vista se resuelve
en la vista. Estas tres existen porque dependen de la dirección actual, que
solo la plantilla conoce del todo.
"""

from urllib.parse import urlencode

from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def cola(context, **cambios):
    """
    La dirección actual con algunos parámetros cambiados.

    Es lo que mantiene los filtros al paginar: el enlace a la página 2 lleva
    la búsqueda y los filtros que ya estaban puestos. Un parámetro en vacío
    se quita.

        <a href="?{% cola p=2 %}">Siguiente</a>
    """
    peticion = context["request"]
    datos = {
        clave: valor
        for clave, valor in peticion.GET.items()
        if valor and clave != "export"
    }
    for clave, valor in cambios.items():
        if valor in (None, ""):
            datos.pop(clave, None)
        else:
            datos[clave] = valor
    return urlencode(datos)


@register.filter
def campo_clase(campo, clases):
    """Agrega clases al widget de un campo de formulario desde la plantilla."""
    existentes = campo.field.widget.attrs.get("class", "")
    campo.field.widget.attrs["class"] = f"{existentes} {clases}".strip()
    return campo


@register.filter
def iniciales(texto):
    """Las dos primeras iniciales de un nombre, para el avatar."""
    partes = [p for p in str(texto or "").split() if p]
    return "".join(p[0] for p in partes[:2]).upper() or "SG"

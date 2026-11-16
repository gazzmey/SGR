"""
RUT chileno: limpieza y dígito verificador.

Vive en ``comun`` porque lo usan dos entidades de apps distintas: el vecino
(``atencion.Solicitante``) y el funcionario (``organizacion.PerfilUsuario``).
``atencion.models`` lo reexporta con los mismos nombres, porque sus
migraciones antiguas apuntan a ``atencion.models.validar_rut``.

Todos los RUT del sistema son ficticios: números con dígito verificador
correcto que no corresponden a nadie.
"""

import re

from django.core.exceptions import ValidationError


def limpiar_rut(valor):
    """Deja el RUT en formato 12345678-5, sin puntos ni espacios."""
    return re.sub(r"[.\s]", "", str(valor or "")).upper()


def digito_verificador(cuerpo):
    """El dígito verificador de un cuerpo de RUT, con el módulo 11."""
    suma = 0
    factor = 2
    for digito in reversed(str(cuerpo)):
        suma += int(digito) * factor
        factor = 2 if factor == 7 else factor + 1
    resto = 11 - (suma % 11)
    return "0" if resto == 11 else "K" if resto == 10 else str(resto)


def rut_valido(valor):
    """
    Comprueba el formato y el dígito verificador.

    Se valida en el servidor a propósito: el navegador puede saltarse, el
    servidor no.
    """
    limpio = limpiar_rut(valor)
    if not re.fullmatch(r"\d{7,8}-[\dK]", limpio):
        return False
    cuerpo, dv = limpio.split("-")
    return dv == digito_verificador(cuerpo)


def validar_rut(valor):
    """Validador de modelo: lanza ValidationError si el RUT no cuadra."""
    if not rut_valido(valor):
        raise ValidationError(
            "Ese RUT no es válido: revisa el número y el dígito verificador."
        )

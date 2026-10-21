"""
Atención ciudadana: quién consulta y qué se le resolvió.

El documento de la segunda entrega pide registrar la atención sin exigir un
mantenedor de vecinos. Por eso ``Solicitante`` existe como entidad —hace
falta para no repetir los datos de la persona en cada atención— pero no tiene
pantalla propia: se crea o se reutiliza desde el mismo formulario de ingreso.

Las dos relaciones que importan usan ``PROTECT``: una atención conserva a
quién se atendió y qué subatención se usó, aunque después esa subatención se
desactive.
"""

import re

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


def limpiar_rut(valor):
    """Deja el RUT en formato 12345678-5, sin puntos ni espacios."""
    return re.sub(r"[.\s]", "", str(valor or "")).upper()


def rut_valido(valor):
    """
    Comprueba el dígito verificador con el módulo 11.

    Se valida en el servidor a propósito: el navegador puede saltarse, el
    servidor no. La misma comprobación está en el formulario para avisar
    antes de enviar, pero la que manda es esta.
    """
    limpio = limpiar_rut(valor)
    if not re.fullmatch(r"\d{7,8}-[\dK]", limpio):
        return False

    cuerpo, dv = limpio.split("-")
    suma = 0
    factor = 2
    for digito in reversed(cuerpo):
        suma += int(digito) * factor
        factor = 2 if factor == 7 else factor + 1

    resto = 11 - (suma % 11)
    esperado = "0" if resto == 11 else "K" if resto == 10 else str(resto)
    return dv == esperado


def validar_rut(valor):
    """Validador de modelo: lanza ValidationError si el RUT no cuadra."""
    if not rut_valido(valor):
        raise ValidationError(
            "Ese RUT no es válido: revisa el número y el dígito verificador."
        )


class Solicitante(models.Model):
    """Persona que acude a la delegación."""

    rut = models.CharField(
        "RUT", max_length=12, unique=True, validators=[validar_rut],
        help_text="Con dígito verificador, por ejemplo 11111111-1.",
    )
    nombre = models.CharField(max_length=120)
    telefono = models.CharField("teléfono", max_length=20, blank=True)
    territorio = models.CharField(
        max_length=80, blank=True,
        help_text="Unidad vecinal o sector al que pertenece.",
    )
    creada = models.DateField("registrado el", auto_now_add=True)

    class Meta:
        verbose_name = "solicitante"
        verbose_name_plural = "solicitantes"
        ordering = ["nombre"]

    def __str__(self):
        return f"{self.rut} — {self.nombre}"

    def save(self, *args, **kwargs):
        self.rut = limpiar_rut(self.rut)
        super().save(*args, **kwargs)


class Atencion(models.Model):
    """Una atención entregada en la delegación."""

    solicitante = models.ForeignKey(
        Solicitante,
        on_delete=models.PROTECT,
        related_name="atenciones",
        verbose_name="solicitante",
    )
    subatencion = models.ForeignKey(
        "catalogos.SubAtencion",
        on_delete=models.PROTECT,
        related_name="atenciones",
        verbose_name="subatención",
    )
    delegacion = models.ForeignKey(
        "organizacion.Delegacion",
        on_delete=models.PROTECT,
        related_name="atenciones",
        verbose_name="delegación",
        help_text="La delegación activa de quien registró la atención.",
    )
    funcionario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="atenciones",
        verbose_name="funcionario",
    )
    detalle = models.TextField(
        help_text="Qué pidió la persona y qué se le respondió.",
    )
    documento = models.CharField(
        "documento de respaldo", max_length=120, blank=True,
        help_text="Obligatorio cuando la subatención lo exige.",
    )
    registrada = models.DateTimeField("registrada el", auto_now_add=True)

    class Meta:
        verbose_name = "atención"
        verbose_name_plural = "atenciones"
        ordering = ["-registrada"]

    def __str__(self):
        return f"{self.solicitante.nombre} — {self.subatencion.nombre}"

    def clean(self):
        """
        La regla del documento obligatorio vive aquí, no solo en el formulario.

        Así se cumple aunque la atención se cree desde el administrador o
        desde un script, y no únicamente desde la pantalla de ingreso.
        """
        super().clean()
        if self.subatencion_id and self.subatencion.documento and not self.documento.strip():
            raise ValidationError({
                "documento": (
                    f"«{self.subatencion.nombre}» exige documento de respaldo: "
                    "indica cuál es."
                )
            })

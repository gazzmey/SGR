"""
El tubo de cartas: lo que llega a la delegación por oficina de partes.

Es la hoja «TUBO CARTAS» de la matriz SGR, y la función 8 del Apoyo
Administrativo en el descriptor de cargos: «retroalimentar para la gestión
del delegado las solicitudes ingresadas por la comunidad (correos al alias,
solicitudes por carta, en oficina y/o oficina de partes)».

Una carta no es un compromiso. Muchas llegan «solo para conocimiento» y no
piden nada; otras piden algo que decide otra unidad —patentes, tránsito— y
la delegación solo hace el seguimiento. Por eso tiene su propio registro y
sus propios estados, los de la matriz: en proceso, aprobada, finalizada y no
aplica. Si de una carta nace algo que la delegación tiene que hacer, eso se
ingresa en la agenda.

La matriz anota el teléfono de quien remite. Aquí no: el remitente basta para
ubicar la carta en oficina de partes, que es donde está el original.
"""

from datetime import date

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class Carta(models.Model):
    """Una carta recibida por oficina de partes, con su seguimiento."""

    class Estado(models.TextChoices):
        EN_PROCESO = "en_proceso", "En proceso"
        APROBADA = "aprobada", "Aprobada"
        FINALIZADA = "finalizada", "Finalizada"
        NO_APLICA = "no_aplica", "No aplica"

    #: Los estados que ya no esperan nada de la delegación.
    CERRADOS = [Estado.APROBADA, Estado.FINALIZADA, Estado.NO_APLICA]

    codigo = models.CharField(
        "código", max_length=12, unique=True,
        help_text="Se asigna solo: CTA-001.",
    )
    delegacion = models.ForeignKey(
        "organizacion.Delegacion", on_delete=models.PROTECT,
        related_name="cartas", verbose_name="delegación",
    )
    fecha = models.DateField(
        "fecha de recepción",
        help_text="Cuándo llegó la carta a la delegación.",
    )
    numero = models.CharField(
        "N° de oficina de partes", max_length=30, blank=True,
        help_text="El número con que quedó ingresada, para ubicar el original.",
    )
    dirigida_a = models.CharField(
        "dirigida a", max_length=120,
        help_text="A quién va la carta: la alcaldesa, el delegado, una dirección.",
    )
    remitente = models.CharField(
        "remite", max_length=120,
        help_text="Persona u organización que la firma. Sin RUT ni teléfono.",
    )
    tema = models.TextField(
        "actividad o tema",
        help_text="Qué pide o informa la carta, en pocas líneas.",
    )
    fecha_actividad = models.DateField(
        "fecha de la actividad", null=True, blank=True,
        help_text="Si la carta pide algo para un día determinado.",
    )
    responsable = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="cartas", verbose_name="encargado de seguimiento",
        help_text="Quién de la delegación sigue la carta hasta cerrarla.",
    )
    estado = models.CharField(
        max_length=12, choices=Estado.choices, default=Estado.EN_PROCESO,
    )
    derivada_a = models.CharField(
        "derivada a", max_length=120, blank=True,
        help_text="La unidad municipal que decide, si no es la delegación.",
    )
    pronunciamiento = models.TextField(
        blank=True,
        help_text=(
            "Qué se respondió o resolvió. Obligatorio para aprobarla o "
            "finalizarla."
        ),
    )
    observacion = models.TextField("observación", blank=True)
    registrada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="cartas_registradas", verbose_name="registrada por",
        null=True, blank=True,
    )
    activo = models.BooleanField(default=True)
    creada = models.DateField("registrada el", auto_now_add=True)
    desactivada = models.DateField("desactivada el", null=True, blank=True)

    class Meta:
        verbose_name = "carta"
        verbose_name_plural = "cartas"
        ordering = ["-fecha", "-codigo"]

    def __str__(self):
        return f"{self.codigo} — {self.remitente}"

    @property
    def nombre(self):
        """Para el enlace del listado."""
        return self.remitente

    @property
    def cerrada(self):
        return self.estado in self.CERRADOS

    @property
    def dias_desde_recepcion(self):
        if not self.fecha:
            return None
        return max(0, (date.today() - self.fecha).days)

    def clean(self):
        super().clean()
        errores = {}
        if self.fecha and self.fecha > date.today():
            errores["fecha"] = "La fecha de recepción no puede ser futura."
        if (self.estado in (self.Estado.APROBADA, self.Estado.FINALIZADA)
                and not (self.pronunciamiento or "").strip()):
            errores["pronunciamiento"] = (
                "Para dejarla %s, escribe qué se respondió o resolvió: es lo "
                "que se consulta cuando el remitente pregunta."
                % self.get_estado_display().lower()
            )
        if (self.responsable_id and self.delegacion_id
                and hasattr(self.responsable, "perfil")
                and self.responsable.perfil.delegacion_id != self.delegacion_id):
            errores["responsable"] = "El encargado tiene que ser de la delegación."
        if errores:
            raise ValidationError(errores)

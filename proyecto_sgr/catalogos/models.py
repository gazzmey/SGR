"""
Catálogos del SGR: ítems medibles y clasificación de las atenciones.

Los tipos de atención se abren en subatenciones para registrar con detalle
qué se resolvió en cada gestión. La relación es de uno a muchos: un tipo
agrupa varias subatenciones.

Sobre esta entrega
------------------
A los tres modelos de la Unidad 2 se les agregan los campos que la segunda
entrega del Proyecto Integrado necesita para sus mantenedores: el área y la
unidad de medida del ítem con su meta y ponderador, la descripción del tipo
de atención, y si una subatención exige documento de respaldo.
"""

from django.core.validators import MinValueValidator
from django.db import models


class Area(models.TextChoices):
    """Agrupación usada en los informes. La comparten ítems y tipos."""

    TERRITORIAL = "Territorial", "Territorial"
    INSPECCION = "Inspección", "Inspección"
    SOCIAL = "Social", "Social"
    TRANSVERSAL = "Transversal", "Transversal"


class Item(models.Model):
    """Elemento medible sobre el que se evalúa la gestión."""

    class Unidad(models.TextChoices):
        CANTIDAD = "Cantidad", "Cantidad"
        PORCENTAJE = "Porcentaje", "Porcentaje"
        HORAS = "Horas", "Horas"

    codigo = models.CharField(
        "código", max_length=10, unique=True,
        help_text="Identificador corto e irrepetible, por ejemplo ITM-01.",
    )
    nombre = models.CharField(max_length=120, unique=True)
    descripcion = models.TextField(
        "descripción", blank=True,
        help_text="Qué cuenta como registro válido. Es lo que evita discusiones al cerrar el período.",
    )
    area = models.CharField(
        "área", max_length=12, choices=Area.choices, default=Area.TRANSVERSAL,
    )
    unidad = models.CharField(
        "unidad de medida", max_length=12,
        choices=Unidad.choices, default=Unidad.CANTIDAD,
    )
    meta = models.PositiveIntegerField(
        "meta del período", default=1,
        validators=[MinValueValidator(1)],
        help_text=(
            "En la unidad de medida elegida. Tiene que ser mayor que cero: "
            "con meta cero el cumplimiento sería una división por cero, y "
            "cualquier avance daría 100 % o infinito según cómo se calcule."
        ),
    )
    ponderador = models.PositiveSmallIntegerField(
        default=0,
        help_text="Porcentaje del resultado total. Entre todos los activos deben sumar 100 %.",
    )
    activo = models.BooleanField(default=True)
    creada = models.DateField("creado el", auto_now_add=True)
    desactivada = models.DateField("desactivado el", null=True, blank=True)

    class Meta:
        verbose_name = "ítem"
        verbose_name_plural = "ítems"
        ordering = ["codigo"]

    def __str__(self):
        return f"{self.codigo} — {self.nombre}"

    def motivo_bloqueo(self):
        """
        Un ítem con registros en el período abierto no se desactiva.

        En esta entrega no existe todavía el modelo de actividades, así que
        no hay nada que contar: el método queda escrito y devuelve vacío.
        Cuando el módulo de actividades entre, basta con contar aquí.
        """
        return ""

    @property
    def suma_ponderadores(self):
        """Cuánto suman los ponderadores de los ítems activos."""
        return (
            Item.objects.filter(activo=True)
            .aggregate(total=models.Sum("ponderador"))["total"] or 0
        )


class TipoAtencion(models.Model):
    """Clasificación general de una atención entregada a la comunidad."""

    codigo = models.CharField(
        "código", max_length=10, unique=True,
        help_text="Identificador corto e irrepetible, por ejemplo TAT-01.",
    )
    nombre = models.CharField(max_length=120, unique=True)
    descripcion = models.TextField(
        "descripción", blank=True,
        help_text="Qué requerimientos entran en esta clasificación.",
    )
    area = models.CharField(
        "área", max_length=12, choices=Area.choices, default=Area.TRANSVERSAL,
    )
    activo = models.BooleanField(default=True)
    creada = models.DateField("creado el", auto_now_add=True)
    desactivada = models.DateField("desactivado el", null=True, blank=True)

    class Meta:
        verbose_name = "tipo de atención"
        verbose_name_plural = "tipos de atención"
        ordering = ["codigo"]

    def __str__(self):
        return f"{self.codigo} — {self.nombre}"

    def motivo_bloqueo(self):
        cuantas = self.subatenciones.filter(activo=True).count()
        if cuantas:
            return (
                f"Tiene {cuantas} "
                f"{'subatención activa' if cuantas == 1 else 'subatenciones activas'} colgando. "
                "Desactívalas primero, o quedarían disponibles sin su tipo."
            )
        return ""


class SubAtencion(models.Model):
    """Detalle de un tipo de atención."""

    tipo_atencion = models.ForeignKey(
        TipoAtencion,
        on_delete=models.PROTECT,
        related_name="subatenciones",
        verbose_name="tipo de atención",
    )
    codigo = models.CharField(
        "código", max_length=10, unique=True,
        help_text="Identificador corto e irrepetible, por ejemplo SAT-01.",
    )
    nombre = models.CharField(max_length=120, unique=True)
    descripcion = models.TextField(
        "descripción", blank=True,
        help_text="Qué incluye, qué requisitos tiene y cómo se resuelve.",
    )
    documento = models.BooleanField(
        "exige documento de respaldo", default=False,
        help_text="Si está marcado, el ingreso de atención no deja guardar sin adjuntarlo.",
    )
    activo = models.BooleanField(default=True)
    creada = models.DateField("creada el", auto_now_add=True)
    desactivada = models.DateField("desactivada el", null=True, blank=True)

    class Meta:
        verbose_name = "subatención"
        verbose_name_plural = "subatenciones"
        ordering = ["tipo_atencion__codigo", "codigo"]

    def __str__(self):
        return f"{self.codigo} — {self.nombre}"

    def motivo_bloqueo(self):
        cuantas = self.atenciones.count()
        if cuantas:
            return (
                f"Tiene {cuantas} "
                f"{'atención registrada' if cuantas == 1 else 'atenciones registradas'}. "
                "Podrás desactivarla cuando el período se cierre; las atenciones "
                "anteriores la seguirán mostrando."
            )
        return ""

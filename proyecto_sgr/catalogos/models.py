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
from django.core.exceptions import ValidationError
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

    class Medicion(models.TextChoices):
        """
        De dónde sale el avance del ítem.

        La matriz SGR de las delegaciones tiene tres clases de ítem, y las
        tres aparecen en todas las hojas de cargo:

        · los que se cuentan contra una meta —«Atención de usuario: 240»—;
        · «Soluciones de ingresos al tubo», que es el porcentaje de
          compromisos que la persona tiene realizados, contra una meta de
          80 %;
        · «Emergencia», que no tiene meta fija: la matriz pone como meta lo
          mismo que se hizo, así que se cumple entero con una sola atención y
          queda en cero si no hubo ninguna.
        """

        ACTIVIDADES = "actividades", "Actividades aprobadas contra la meta"
        AGENDA = "agenda", "Porcentaje de compromisos realizados (tubo)"
        PRESENCIA = "presencia", "Cumplido con al menos una actividad aprobada"

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
    medicion = models.CharField(
        "cómo se mide", max_length=12,
        choices=Medicion.choices, default=Medicion.ACTIVIDADES,
        help_text=(
            "Contando actividades contra la meta; como porcentaje de "
            "compromisos realizados, con la meta en %; o cumplido con una "
            "sola actividad, para ítems sin meta fija como Emergencia."
        ),
    )
    # La meta y el ponderador del ítem son los que se proponen al asignarlo a
    # un cargo. Los que usa el cálculo están en gestion.MetaPeriodo, por
    # período y cargo: un inspector y una asistente social no se miden con
    # la misma vara, y el año que viene puede pesar distinto que este.
    meta = models.PositiveIntegerField(
        "meta sugerida", default=1,
        validators=[MinValueValidator(1)],
        help_text=(
            "La que se propone al asignar el ítem a un cargo, en la unidad "
            "elegida. Tiene que ser mayor que cero: es el denominador del "
            "cumplimiento."
        ),
    )
    ponderador = models.PositiveSmallIntegerField(
        "ponderador sugerido", default=0,
        help_text=(
            "El que se propone al asignar el ítem a un cargo. El peso real se "
            "define por período y cargo, en Metas y ponderadores."
        ),
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

    # --- versiones (HU-25) ------------------------------------------------

    TIPO_VERSION = "item"

    def datos_version(self):
        return {
            "Código": self.codigo,
            "Nombre": self.nombre,
            "Área": self.get_area_display(),
            "Cómo se mide": self.get_medicion_display(),
            "Unidad": self.get_unidad_display(),
            "Meta sugerida": str(self.meta),
            "Ponderador sugerido": f"{self.ponderador} %",
            "Estado": "Activo" if self.activo else "Inactivo",
        }

    def vigencia_version(self):
        from datetime import date

        return (f"Desde el {date.today():%d-%m-%Y}, en las metas de los "
                "períodos que no están cerrados")

    def clean(self):
        """El ítem medido por la agenda es un porcentaje, y su meta también."""
        super().clean()
        # Cambiar cómo se mide un ítem cambiaría el resultado de los períodos
        # cerrados que lo usaron (RF-038.3). Para medir distinto se crea otro.
        if self.pk:
            previo = Item.objects.filter(pk=self.pk).values_list("medicion", flat=True).first()
            if (previo and previo != self.medicion
                    and self.metas.filter(periodo__estado="cerrado").exists()):
                raise ValidationError({
                    "medicion": (
                        "Este ítem se usó en un período cerrado: cambiar cómo "
                        "se mide alteraría ese resultado. Crea un ítem nuevo "
                        "con la medición que necesitas."
                    ),
                })
        if self.medicion == self.Medicion.AGENDA:
            errores = {}
            if self.unidad != self.Unidad.PORCENTAJE:
                errores["unidad"] = (
                    "Un ítem medido por la agenda se expresa en porcentaje: "
                    "es la parte de los compromisos que quedó realizada."
                )
            if self.meta is not None and self.meta > 100:
                errores["meta"] = (
                    "Es un porcentaje de compromisos realizados: no puede "
                    "pasar de 100. La matriz usa 80."
                )
            if errores:
                raise ValidationError(errores)

    @property
    def cuenta_actividades(self):
        """True si el avance del ítem sale de actividades aprobadas."""
        return self.medicion != self.Medicion.AGENDA

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

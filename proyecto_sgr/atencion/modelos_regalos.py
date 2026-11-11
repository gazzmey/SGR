"""
Regalos para niños: campañas e inscripciones, sin duplicados entre delegaciones.

Es la hoja «REGALOS NIÑOS» de la matriz SGR. Casi no tiene datos: lo que deja
escrito es la regla. Cada niño se inscribe por su **RUT** en una campaña
—Navidad, Día del Niño o Aniversario— y, una vez ingresado, la planilla
debía avisar «RUT ya ingresado por delegación XX». Es lo que evita que un
mismo niño reciba dos regalos por inscribirse en dos delegaciones.

Lo que se guarda, y lo que no
-----------------------------
Del niño se guarda solo lo que el proceso necesita: el **RUT**, para
detectar el duplicado, y el **tramo de edad**, para saber qué regalo
comprar. No se guarda su nombre ni su fecha de nacimiento. El adulto que lo
inscribe queda como ``Solicitante``, la misma ficha de atención ciudadana,
porque es a quien se llama para retirar el regalo.

En los listados y en la exportación el RUT del niño se muestra enmascarado;
completo solo en su ficha, que es donde se verifica al entregar.

Por qué el duplicado se revisa en el modelo y no con un índice único
--------------------------------------------------------------------
Una inscripción anulada —desactivada— tiene que liberar el RUT: si se
inscribió por error en una delegación, la correcta debe poder inscribirlo.
Eso exige que la unicidad valga solo entre las activas, y un índice único
condicional es justo lo que MariaDB no soporta (está explicado en
``gestion/reglas.py``). Así que la regla vive en ``clean()``.
"""

from datetime import date

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from atencion.models import Solicitante, limpiar_rut, validar_rut


def enmascarar_rut(rut):
    """«12345678-5» → «••••5678-5». Lo justo para reconocerlo, no para copiarlo."""
    limpio = limpiar_rut(rut)
    if "-" not in limpio:
        return "••••"
    cuerpo, dv = limpio.split("-", 1)
    return "••••%s-%s" % (cuerpo[-4:], dv)


class CampanaRegalos(models.Model):
    """Una entrega de regalos de la municipalidad, para todas las delegaciones."""

    class Evento(models.TextChoices):
        NAVIDAD = "navidad", "Navidad"
        DIA_NINO = "dia_nino", "Día del Niño"
        ANIVERSARIO = "aniversario", "Aniversario"

    codigo = models.CharField(
        "código", max_length=10, unique=True,
        help_text="Identificador corto, por ejemplo CRG-01.",
    )
    evento = models.CharField(max_length=12, choices=Evento.choices)
    anio = models.PositiveSmallIntegerField(
        "año", validators=[MinValueValidator(2020), MaxValueValidator(2100)],
    )
    inscripcion_hasta = models.DateField(
        "inscripciones hasta", null=True, blank=True,
        help_text="Último día para inscribir. Vacío: abierta mientras la campaña esté activa.",
    )
    fecha_entrega = models.DateField(
        "fecha de entrega", null=True, blank=True,
        help_text="El día en que se entregan los regalos, si ya está definido.",
    )
    edad_maxima = models.PositiveSmallIntegerField(
        "edad máxima", default=12,
        validators=[MinValueValidator(1), MaxValueValidator(17)],
        help_text="Hasta qué edad se inscribe, incluida. Define qué tramos se ofrecen.",
    )
    observacion = models.TextField("observación", blank=True)
    activo = models.BooleanField(default=True)
    creada = models.DateField("creada el", auto_now_add=True)
    desactivada = models.DateField("desactivada el", null=True, blank=True)

    class Meta:
        verbose_name = "campaña de regalos"
        verbose_name_plural = "campañas de regalos"
        ordering = ["-anio", "evento"]
        constraints = [
            models.UniqueConstraint(fields=["evento", "anio"], name="una_campana_por_evento_y_anio"),
        ]

    def __str__(self):
        return f"{self.codigo} — {self.nombre}"

    @property
    def nombre(self):
        return f"{self.get_evento_display()} {self.anio}"

    def abierta(self, hoy=None):
        """¿Se puede inscribir hoy?"""
        hoy = hoy or date.today()
        return self.activo and (self.inscripcion_hasta is None or hoy <= self.inscripcion_hasta)

    def clean(self):
        super().clean()
        if (self.inscripcion_hasta and self.fecha_entrega
                and self.fecha_entrega < self.inscripcion_hasta):
            raise ValidationError({
                "fecha_entrega": "La entrega no puede ser antes del cierre de las inscripciones.",
            })

    def motivo_bloqueo(self):
        return ""


class InscripcionRegalo(models.Model):
    """Un niño inscrito en una campaña, por una delegación."""

    class Tramo(models.TextChoices):
        T0_2 = "0-2", "0 a 2 años"
        T3_5 = "3-5", "3 a 5 años"
        T6_8 = "6-8", "6 a 8 años"
        T9_11 = "9-11", "9 a 11 años"
        T12_14 = "12-14", "12 a 14 años"
        T15_17 = "15-17", "15 a 17 años"

    #: La edad con que empieza cada tramo: decide cuáles se ofrecen según la
    #: edad máxima de la campaña.
    DESDE = {"0-2": 0, "3-5": 3, "6-8": 6, "9-11": 9, "12-14": 12, "15-17": 15}

    codigo = models.CharField("código", max_length=12, unique=True)
    campana = models.ForeignKey(
        CampanaRegalos, on_delete=models.PROTECT, related_name="inscripciones",
        verbose_name="campaña",
    )
    delegacion = models.ForeignKey(
        "organizacion.Delegacion", on_delete=models.PROTECT,
        related_name="regalos", verbose_name="delegación",
    )
    rut_menor = models.CharField(
        "RUT del niño o niña", max_length=12, validators=[validar_rut],
        help_text="Con dígito verificador. Es lo que impide inscribirlo dos veces.",
    )
    tramo_edad = models.CharField("tramo de edad", max_length=5, choices=Tramo.choices)
    apoderado = models.ForeignKey(
        Solicitante, on_delete=models.PROTECT, related_name="regalos_inscritos",
        verbose_name="adulto que lo inscribe",
    )
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="regalos_inscritos", verbose_name="inscrito por",
    )
    registrada = models.DateTimeField("inscrito el", auto_now_add=True)
    entregado_el = models.DateField("entregado el", null=True, blank=True)
    entregado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="regalos_entregados", verbose_name="entregado por",
        null=True, blank=True,
    )
    activo = models.BooleanField(
        default=True,
        help_text="Desactivar anula la inscripción y libera el RUT para otra delegación.",
    )
    desactivada = models.DateField("anulada el", null=True, blank=True)

    class Meta:
        verbose_name = "inscripción de regalo"
        verbose_name_plural = "inscripciones de regalos"
        ordering = ["-registrada"]

    def __str__(self):
        return f"{self.codigo} — {self.rut_enmascarado}"

    def save(self, *args, **kwargs):
        self.rut_menor = limpiar_rut(self.rut_menor)
        super().save(*args, **kwargs)

    @property
    def rut_enmascarado(self):
        return enmascarar_rut(self.rut_menor)

    @property
    def nombre(self):
        """Lo que muestra el listado como enlace: el RUT enmascarado."""
        return f"RUT {self.rut_enmascarado}"

    @property
    def entregado(self):
        return self.entregado_el is not None

    def duplicada(self):
        """La otra inscripción activa del mismo RUT en la campaña, si la hay."""
        if not self.campana_id or not self.rut_menor:
            return None
        return (
            InscripcionRegalo.objects
            .filter(campana_id=self.campana_id, rut_menor=limpiar_rut(self.rut_menor),
                    activo=True)
            .exclude(pk=self.pk)
            .select_related("delegacion")
            .first()
        )

    def clean(self):
        super().clean()
        errores = {}
        if self.activo:
            otra = self.duplicada()
            if otra is not None:
                errores["rut_menor"] = (
                    "RUT ya ingresado por la delegación %s el %s (%s). Un niño o "
                    "niña recibe un solo regalo por campaña."
                    % (otra.delegacion.nombre,
                       otra.registrada.strftime("%d-%m-%Y") if otra.registrada else "—",
                       otra.codigo)
                )
        if (self.campana_id and self.tramo_edad
                and self.DESDE.get(self.tramo_edad, 0) > self.campana.edad_maxima):
            errores["tramo_edad"] = (
                "Esta campaña llega hasta los %d años." % self.campana.edad_maxima
            )
        if self.apoderado_id and limpiar_rut(self.rut_menor) == self.apoderado.rut:
            errores["rut_menor"] = "Es el mismo RUT del adulto que lo inscribe."
        if errores:
            raise ValidationError(errores)

    def motivo_bloqueo(self):
        if self.entregado:
            return (
                "El regalo ya se entregó el %s. Anularla dejaría la entrega sin "
                "registro." % self.entregado_el.strftime("%d-%m-%Y")
            )
        return ""

    def motivo_bloqueo_activar(self):
        otra = self.duplicada()
        if otra is not None:
            return (
                "Ese RUT ya está inscrito otra vez en la campaña, por %s (%s)."
                % (otra.delegacion.nombre, otra.codigo)
            )
        return ""

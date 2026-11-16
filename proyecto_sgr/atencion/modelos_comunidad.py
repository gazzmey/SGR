"""
Juntas de vecinos y la participación de cada vecino en ellas.

La membresía no se guarda como texto en la ficha del vecino: es un registro
propio, ``ParticipacionJunta``, con su fecha de incorporación, su condición
de dirigente y su estado. Así una persona puede haber sido socia de una
junta, dejarlo, y volver años después sin perder el historial.

Las reglas de coherencia viven en ``clean()`` del modelo y no solo en el
formulario, para que valgan también desde Django Admin:

* la junta pertenece a un territorio de su misma delegación;
* el vecino vive en el territorio de la junta (Ley 19.418: la junta agrupa a
  quienes residen en la unidad vecinal);
* nadie tiene dos participaciones activas en la misma junta;
* cada cargo de la directiva lo ocupa una sola persona a la vez;
* la incorporación no es anterior a la constitución de la junta ni futura.
"""

from datetime import date

from django.core.exceptions import ValidationError
from django.db import models


class JuntaVecinos(models.Model):
    """Organización comunitaria de una unidad vecinal."""

    codigo = models.CharField(
        "código", max_length=10, unique=True,
        help_text="Identificador corto e irrepetible, por ejemplo JV-01.",
    )
    nombre = models.CharField(max_length=120, unique=True)
    direccion = models.CharField(
        "dirección", max_length=160,
        help_text="Dónde funciona la sede o dónde se reúne.",
    )
    delegacion = models.ForeignKey(
        "organizacion.Delegacion", on_delete=models.PROTECT,
        related_name="juntas", verbose_name="delegación",
    )
    territorio = models.ForeignKey(
        "organizacion.Territorio", on_delete=models.PROTECT,
        related_name="juntas", verbose_name="territorio",
        help_text="Tiene que ser un territorio de la delegación elegida.",
    )
    fecha_constitucion = models.DateField(
        "fecha de constitución",
        help_text="Cuándo se constituyó legalmente. No puede ser futura.",
    )
    activo = models.BooleanField("activa", default=True)
    creada = models.DateField("creada el", auto_now_add=True)
    desactivada = models.DateField("desactivada el", null=True, blank=True)

    class Meta:
        verbose_name = "junta de vecinos"
        verbose_name_plural = "juntas de vecinos"
        ordering = ["codigo"]

    def __str__(self):
        return f"{self.codigo} — {self.nombre}"

    def clean(self):
        super().clean()
        errores = {}
        if self.fecha_constitucion and self.fecha_constitucion > date.today():
            errores["fecha_constitucion"] = "La fecha de constitución no puede ser futura."
        if (self.territorio_id and self.delegacion_id
                and self.territorio.delegacion_id != self.delegacion_id):
            errores["territorio"] = (
                "«%s» pertenece a %s, no a %s. Elige un territorio de la "
                "misma delegación." % (self.territorio.nombre,
                                       self.territorio.delegacion.nombre,
                                       self.delegacion.nombre)
            )
        if self.territorio_id and not self.pk and not self.territorio.activo:
            errores["territorio"] = "Ese territorio está inactivo."
        if errores:
            raise ValidationError(errores)

    def motivo_bloqueo(self):
        cuantas = self.participaciones.filter(activo=True).count()
        if cuantas:
            return (
                f"Tiene {cuantas} "
                f"{'participante activo' if cuantas == 1 else 'participantes activos'}. "
                "Termina esas participaciones antes de desactivarla."
            )
        return ""

    def motivo_bloqueo_activar(self):
        if not self.territorio.activo:
            return "Su territorio está inactivo. Actívalo primero."
        return ""


class ParticipacionJunta(models.Model):
    """La pertenencia de un vecino a una junta, con su cargo si es dirigente."""

    class Cargo(models.TextChoices):
        SOCIO = "socio", "Socio o socia"
        PRESIDENTE = "presidente", "Presidencia"
        VICEPRESIDENTE = "vicepresidente", "Vicepresidencia"
        SECRETARIO = "secretario", "Secretaría"
        TESORERO = "tesorero", "Tesorería"
        DIRECTOR = "director", "Director o directora"

    #: Los cargos que ocupa una sola persona a la vez en cada junta.
    UNICOS = [Cargo.PRESIDENTE, Cargo.VICEPRESIDENTE, Cargo.SECRETARIO, Cargo.TESORERO]

    codigo = models.CharField(
        "código", max_length=10, unique=True,
        help_text="Identificador corto e irrepetible, por ejemplo PJ-01.",
    )
    vecino = models.ForeignKey(
        "atencion.Solicitante", on_delete=models.PROTECT,
        related_name="participaciones", verbose_name="vecino",
    )
    junta = models.ForeignKey(
        JuntaVecinos, on_delete=models.PROTECT,
        related_name="participaciones", verbose_name="junta de vecinos",
    )
    dirigente = models.BooleanField(
        "es dirigente", default=False,
        help_text="Marca si integra la directiva. Un socio sin cargo no es dirigente.",
    )
    cargo = models.CharField(
        max_length=16, choices=Cargo.choices, default=Cargo.SOCIO,
        help_text="Los dirigentes tienen un cargo de la directiva; el resto, «Socio o socia».",
    )
    fecha_incorporacion = models.DateField(
        "fecha de incorporación",
        help_text="No puede ser anterior a la constitución de la junta ni futura.",
    )
    activo = models.BooleanField("vigente", default=True)
    creada = models.DateField("registrada el", auto_now_add=True)
    desactivada = models.DateField("terminada el", null=True, blank=True)

    class Meta:
        verbose_name = "participación en junta"
        verbose_name_plural = "participaciones en juntas"
        ordering = ["junta", "-dirigente", "vecino"]

    def __str__(self):
        return f"{self.vecino.nombre} en {self.junta.nombre}"

    @property
    def nombre(self):
        return f"{self.vecino.nombre} · {self.junta.nombre}"

    def clean(self):
        super().clean()
        errores = {}
        hoy = date.today()

        if self.fecha_incorporacion:
            if self.fecha_incorporacion > hoy:
                errores["fecha_incorporacion"] = "La fecha de incorporación no puede ser futura."
            elif (self.junta_id and self.junta.fecha_constitucion
                  and self.fecha_incorporacion < self.junta.fecha_constitucion):
                errores["fecha_incorporacion"] = (
                    "La junta se constituyó el %s: nadie se incorpora antes."
                    % self.junta.fecha_constitucion.strftime("%d-%m-%Y")
                )

        if self.dirigente and self.cargo == self.Cargo.SOCIO:
            errores["cargo"] = "Un dirigente ocupa un cargo de la directiva: elige cuál."
        if not self.dirigente and self.cargo != self.Cargo.SOCIO:
            errores["dirigente"] = (
                "«%s» es un cargo de la directiva: marca que es dirigente o "
                "déjalo como socio." % self.get_cargo_display()
            )

        if self.vecino_id and self.junta_id:
            if (self.vecino.territorio_id and self.junta.territorio_id
                    and self.vecino.territorio_id != self.junta.territorio_id):
                errores["vecino"] = (
                    "%s vive en «%s» y la junta es de «%s». Una junta agrupa a "
                    "quienes residen en su unidad vecinal." % (
                        self.vecino.nombre, self.vecino.territorio.nombre,
                        self.junta.territorio.nombre)
                )
            if self.activo:
                otra = (ParticipacionJunta.objects
                        .filter(vecino_id=self.vecino_id, junta_id=self.junta_id, activo=True)
                        .exclude(pk=self.pk).exists())
                if otra:
                    errores["vecino"] = (
                        "%s ya participa en esta junta. Edita esa participación "
                        "en vez de crear otra." % self.vecino.nombre
                    )

        if self.junta_id and self.activo and self.cargo in self.UNICOS:
            ocupado = (ParticipacionJunta.objects
                       .filter(junta_id=self.junta_id, cargo=self.cargo, activo=True)
                       .exclude(pk=self.pk).select_related("vecino").first())
            if ocupado:
                errores["cargo"] = (
                    "%s ya ocupa %s en esta junta. Termina esa participación o "
                    "cámbiale el cargo primero." % (ocupado.vecino.nombre,
                                                     ocupado.get_cargo_display().lower())
                )

        if not self.pk:
            if self.vecino_id and not self.vecino.activo:
                errores["vecino"] = "Ese vecino está inactivo."
            if self.junta_id and not self.junta.activo:
                errores["junta"] = "Esa junta está inactiva."
        if errores:
            raise ValidationError(errores)

    def motivo_bloqueo_activar(self):
        if not self.vecino.activo:
            return "El vecino está inactivo. Actívalo primero."
        if not self.junta.activo:
            return "La junta está inactiva. Actívala primero."
        return ""

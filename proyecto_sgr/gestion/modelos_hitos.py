"""
Hitos: los acontecimientos planificados de una delegación.

Un hito es algo que se sabe de antemano que va a ocurrir —un operativo
mensual, la feria de servicios de marzo, la Navidad comunal— con su
periodicidad, sus fechas, su territorio y sus responsables. Las actividades
pueden asociarse a un hito (es opcional), y así se ve qué se hizo para cada
uno.

Las reglas de coherencia viven en ``clean()``: el término no es anterior al
inicio, el territorio es de la misma delegación y cada responsable trabaja
en esa delegación o tiene alcance sobre ella.
"""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class Hito(models.Model):
    class Periodicidad(models.TextChoices):
        UNICA = "unica", "Una sola vez"
        SEMANAL = "semanal", "Semanal"
        MENSUAL = "mensual", "Mensual"
        TRIMESTRAL = "trimestral", "Trimestral"
        ANUAL = "anual", "Anual"

    codigo = models.CharField(
        "código", max_length=10, unique=True,
        help_text="Identificador corto e irrepetible, por ejemplo HIT-01.",
    )
    nombre = models.CharField(max_length=120)
    descripcion = models.TextField(
        "descripción", help_text="Qué se hace y para quién.",
    )
    periodicidad = models.CharField(
        max_length=12, choices=Periodicidad.choices, default=Periodicidad.UNICA,
    )
    fecha_inicio = models.DateField("fecha de inicio")
    fecha_termino = models.DateField(
        "fecha de término", help_text="No puede ser anterior al inicio.",
    )
    delegacion = models.ForeignKey(
        "organizacion.Delegacion", on_delete=models.PROTECT,
        related_name="hitos", verbose_name="delegación",
    )
    territorio = models.ForeignKey(
        "organizacion.Territorio", on_delete=models.PROTECT,
        related_name="hitos", null=True, blank=True, verbose_name="territorio",
        help_text="Opcional. Si se indica, tiene que ser de la misma delegación.",
    )
    responsables = models.ManyToManyField(
        settings.AUTH_USER_MODEL, related_name="hitos_a_cargo",
        verbose_name="responsables",
        help_text="Al menos una persona que trabaje en la delegación.",
    )
    activo = models.BooleanField(default=True)
    creada = models.DateField("creado el", auto_now_add=True)
    desactivada = models.DateField("desactivado el", null=True, blank=True)

    class Meta:
        verbose_name = "hito"
        verbose_name_plural = "hitos"
        ordering = ["fecha_inicio", "codigo"]

    def __str__(self):
        return f"{self.codigo} — {self.nombre}"

    def clean(self):
        super().clean()
        errores = {}
        if self.fecha_inicio and self.fecha_termino and self.fecha_termino < self.fecha_inicio:
            errores["fecha_termino"] = "El término no puede ser anterior al inicio."
        if (self.territorio_id and self.delegacion_id
                and self.territorio.delegacion_id != self.delegacion_id):
            errores["territorio"] = (
                "«%s» pertenece a %s, no a %s." % (
                    self.territorio.nombre, self.territorio.delegacion.nombre,
                    self.delegacion.nombre)
            )
        if not self.pk:
            if self.delegacion_id and not self.delegacion.activo:
                errores["delegacion"] = "Esa delegación está inactiva."
            if self.territorio_id and not self.territorio.activo:
                errores["territorio"] = "Ese territorio está inactivo."
        if errores:
            raise ValidationError(errores)

    @staticmethod
    def motivo_responsables(responsables, delegacion):
        """
        Por qué esos responsables no sirven para esa delegación, o cadena vacía.

        Es estático porque los responsables son una relación de muchos a
        muchos: el formulario los conoce antes de que el hito exista.
        """
        if not responsables:
            return "Indica al menos un responsable."
        fuera = []
        for usuario in responsables:
            perfil = getattr(usuario, "perfil", None)
            if (perfil is None or not perfil.activo or not usuario.is_active
                    or not perfil.delegaciones_visibles().filter(pk=delegacion.pk).exists()):
                fuera.append(usuario.get_full_name() or usuario.get_username())
        if fuera:
            return ("%s no %s en %s ni %s alcance sobre ella." % (
                ", ".join(fuera), "trabaja" if len(fuera) == 1 else "trabajan",
                delegacion.nombre, "tiene" if len(fuera) == 1 else "tienen"))
        return ""

    @property
    def nombres_responsables(self):
        return ", ".join(
            u.get_full_name() or u.get_username() for u in self.responsables.all()
        )

    def motivo_bloqueo(self):
        cuantas = self.actividades.exclude(estado="anulada").count()
        if cuantas:
            return (
                f"Tiene {cuantas} "
                f"{'actividad asociada' if cuantas == 1 else 'actividades asociadas'}. "
                "Desactivarlo las dejaría colgando de un hito que ya no se ofrece."
            )
        return ""

    def motivo_bloqueo_activar(self):
        if not self.delegacion.activo:
            return "Su delegación está inactiva. Actívala primero."
        if self.territorio_id and not self.territorio.activo:
            return "Su territorio está inactivo. Actívalo primero."
        return ""

"""
Lo que ajusta el resultado de una persona sin ser una actividad.

La matriz SGR de las delegaciones mide a cada colaborador con sus ítems
ponderados, y después le aplica dos ajustes que no salen de contar
actividades:

**Felicitaciones y reclamos** (hoja RECLAMOS de la matriz). Cada felicitación
suma un 10 % al cumplimiento ponderado, con un máximo de tres; cada reclamo
resta un 20 %. Las dos condiciones que la matriz deja escritas se cumplen
aquí: tienen que constar *por escrito* —correo, WhatsApp o el libro de
observaciones de la oficina— y el reclamo tiene que ser *por mala atención
del funcionario*. Los porcentajes y el máximo no están en el código: viven en
la regla de cálculo, porque la propia matriz no es pareja (la hoja RECLAMOS
dice −20 % y varias hojas de cargo usan −30 %).

**Ausencias** (hoja SEMAFORO). El «objetivo al día de hoy» de cada persona
descuenta sus días de licencia, vacaciones, emergencias y compensatorios. Sin
ese descuento, quien estuvo dos semanas de vacaciones aparece en rojo por no
haber trabajado mientras no estaba. Una ausencia puede ser de una persona o
de toda la delegación: en la matriz, los diez días de emergencia se le
descuentan a todo el equipo por igual.

Lo que no se guarda
-------------------
La matriz anota el RUT, el teléfono y la dirección de quien reclama o
felicita. Aquí no: para que el ajuste se pueda verificar basta saber quién lo
escribió y dónde consta el escrito. Tampoco se guarda el motivo de una
licencia: el tipo y las fechas son todo lo que el cálculo necesita.
"""

from datetime import date, timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class Reconocimiento(models.Model):
    """Una felicitación o un reclamo por escrito sobre la atención de alguien."""

    class Tipo(models.TextChoices):
        FELICITACION = "felicitacion", "Felicitación"
        RECLAMO = "reclamo", "Reclamo"

    class Medio(models.TextChoices):
        CORREO = "correo", "Correo al delegado"
        WHATSAPP = "whatsapp", "WhatsApp al delegado"
        LIBRO = "libro", "Libro de observaciones de la oficina"
        CARTA = "carta", "Carta por oficina de partes"

    codigo = models.CharField(
        "código", max_length=12, unique=True,
        help_text="Se asigna solo: FEL-001 o REC-001.",
    )
    tipo = models.CharField(max_length=12, choices=Tipo.choices)
    funcionario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="reconocimientos", verbose_name="funcionario",
        help_text="A quién se refiere el escrito.",
    )
    delegacion = models.ForeignKey(
        "organizacion.Delegacion", on_delete=models.PROTECT,
        related_name="reconocimientos", verbose_name="delegación",
    )
    periodo = models.ForeignKey(
        "gestion.Periodo", on_delete=models.PROTECT,
        related_name="reconocimientos", verbose_name="período",
        help_text="El período en que se aplica. La fecha tiene que caer dentro.",
    )
    fecha = models.DateField(
        "fecha del escrito",
        help_text="Cuándo llegó el correo, el mensaje o la anotación en el libro.",
    )
    medio = models.CharField(
        "medio escrito", max_length=12, choices=Medio.choices,
        help_text="Solo cuenta lo que consta por escrito.",
    )
    presentado_por = models.CharField(
        "quién lo escribió", max_length=120,
        help_text=(
            "Nombre de la persona u organización. No hace falta RUT ni "
            "teléfono: basta para encontrar el escrito."
        ),
    )
    situacion = models.TextField(
        "situación",
        help_text="Qué se reclama o qué se felicita, en pocas líneas.",
    )
    respaldo = models.CharField(
        "dónde consta", max_length=200,
        help_text=(
            "Asunto y fecha del correo, captura del mensaje o página del libro. "
            "Es lo que se muestra si alguien pregunta de dónde salió."
        ),
    )
    informado_a = models.CharField(
        "informado a", max_length=120, blank=True,
        help_text="A quién se le informó el reclamo, si corresponde.",
    )
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="reconocimientos_registrados",
        verbose_name="registrado por", null=True, blank=True,
    )
    activo = models.BooleanField(
        default=True,
        help_text="Desactivado deja de sumar o restar, pero se conserva.",
    )
    creada = models.DateField("registrado el", auto_now_add=True)
    desactivada = models.DateField("desactivado el", null=True, blank=True)

    class Meta:
        verbose_name = "felicitación o reclamo"
        verbose_name_plural = "felicitaciones y reclamos"
        ordering = ["-fecha", "-codigo"]

    def __str__(self):
        return f"{self.codigo} — {self.get_tipo_display()} a {self.nombre_funcionario}"

    @property
    def nombre_funcionario(self):
        if not self.funcionario_id:
            return "—"
        return self.funcionario.get_full_name() or self.funcionario.get_username()

    @property
    def nombre(self):
        """Para el enlace del listado, que muestra el nombre como vínculo."""
        return self.nombre_funcionario

    @property
    def es_reclamo(self):
        return self.tipo == self.Tipo.RECLAMO

    def clean(self):
        super().clean()
        errores = {}

        if self.periodo_id and self.fecha:
            if not (self.periodo.inicio <= self.fecha <= self.periodo.termino):
                errores["fecha"] = (
                    "La fecha tiene que estar dentro de «%s», que va del %s al %s."
                    % (self.periodo.nombre,
                       self.periodo.inicio.strftime("%d-%m-%Y"),
                       self.periodo.termino.strftime("%d-%m-%Y"))
                )
            elif self.fecha > date.today():
                errores["fecha"] = (
                    "La fecha no puede ser futura: se registra un escrito que "
                    "ya llegó."
                )

        if self.periodo_id and self.periodo.estado == self.periodo.Estado.CERRADO:
            errores["periodo"] = (
                "«%s» está cerrado: su resultado quedó congelado y no admite "
                "ajustes nuevos." % self.periodo.nombre
            )

        if errores:
            raise ValidationError(errores)

    def motivo_bloqueo(self):
        if self.periodo_id and self.periodo.estado == self.periodo.Estado.CERRADO:
            return (
                "Pertenece a un período cerrado: ya forma parte de un resultado "
                "congelado."
            )
        return ""

    def motivo_bloqueo_activar(self):
        return self.motivo_bloqueo()


class Ausencia(models.Model):
    """Días en que una persona —o toda la delegación— no pudo trabajar."""

    class Tipo(models.TextChoices):
        LICENCIA = "licencia", "Licencia"
        VACACIONES = "vacaciones", "Vacaciones"
        EMERGENCIA = "emergencia", "Emergencia"
        COMPENSATORIO = "compensatorio", "Compensatorio o día administrativo"

    codigo = models.CharField(
        "código", max_length=12, unique=True,
        help_text="Se asigna solo: AUS-001.",
    )
    delegacion = models.ForeignKey(
        "organizacion.Delegacion", on_delete=models.PROTECT,
        related_name="ausencias", verbose_name="delegación",
    )
    funcionario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="ausencias", verbose_name="funcionario",
        null=True, blank=True,
        help_text=(
            "Déjalo vacío si afecta a toda la delegación, como una emergencia "
            "que paró el trabajo de todo el equipo."
        ),
    )
    tipo = models.CharField(max_length=14, choices=Tipo.choices)
    desde = models.DateField("desde")
    hasta = models.DateField(
        "hasta", help_text="El último día de ausencia, incluido.",
    )
    observacion = models.CharField(
        "observación", max_length=200, blank=True,
        help_text="Sin diagnósticos ni datos de salud: basta el tipo y las fechas.",
    )
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="ausencias_registradas",
        verbose_name="registrado por", null=True, blank=True,
    )
    activo = models.BooleanField(default=True)
    creada = models.DateField("registrada el", auto_now_add=True)
    desactivada = models.DateField("desactivada el", null=True, blank=True)

    class Meta:
        verbose_name = "ausencia"
        verbose_name_plural = "ausencias"
        ordering = ["-desde", "-codigo"]

    def __str__(self):
        return f"{self.codigo} — {self.get_tipo_display()} de {self.a_quien}"

    @property
    def a_quien(self):
        if not self.funcionario_id:
            return "toda la delegación"
        return self.funcionario.get_full_name() or self.funcionario.get_username()

    @property
    def nombre(self):
        """Para el listado y la ficha, que lo muestran al comienzo de línea."""
        if not self.funcionario_id:
            return "Toda la delegación"
        return self.a_quien

    @property
    def dias_calendario(self):
        if not self.desde or not self.hasta or self.hasta < self.desde:
            return 0
        return (self.hasta - self.desde).days + 1

    def clean(self):
        super().clean()
        errores = {}
        if self.desde and self.hasta and self.hasta < self.desde:
            errores["hasta"] = "El último día no puede ser anterior al primero."
        if self.desde and self.hasta and (self.hasta - self.desde).days > 366:
            errores["hasta"] = (
                "Una ausencia de más de un año no se mide así: desactiva a la "
                "persona o cámbiale el cargo."
            )
        if (self.funcionario_id and self.delegacion_id
                and hasattr(self.funcionario, "perfil")
                and self.funcionario.perfil.delegacion_id != self.delegacion_id):
            errores["funcionario"] = (
                "Esa persona no pertenece a la delegación elegida."
            )
        if errores:
            raise ValidationError(errores)

    def dias(self):
        """Las fechas de la ausencia, una por una."""
        if not self.desde or not self.hasta or self.hasta < self.desde:
            return []
        return [self.desde + timedelta(days=i) for i in range(self.dias_calendario)]

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


class CasoSocial(models.Model):
    """
    El seguimiento de una atención social hasta su cierre, con sus plazos.

    Son las columnas de las hojas G SOC de la matriz SGR: primera, segunda y
    tercera gestión, con la fecha de cada una y la diferencia de días contra
    lo que la matriz deja escrito como tiempo de respuesta —hasta 10 días
    para programar la visita, sin diferencia entre la programada y la real,
    hasta 4 días para el informe, hasta 4 para el beneficio y hasta 20 en
    total—. Los plazos viven en la regla de cálculo.

    El caso no reemplaza a las actividades: la visita, el informe y la
    entrega del beneficio se siguen registrando en *Mis actividades* con su
    evidencia, que es lo que cuenta para la meta. Lo que agrega el caso es el
    reloj: cuánto tardó cada paso y si se pasó del plazo.

    Las devoluciones del informe —«reingreso de informe 1ra vez, 2da vez» en
    la matriz— se registran para que se vean, pero no se descuentan del
    resultado: la matriz las anota sin fórmula.
    """

    atencion = models.OneToOneField(
        Atencion, on_delete=models.PROTECT, related_name="caso",
        verbose_name="atención",
    )
    codigo = models.CharField("código", max_length=12, unique=True)
    responsable = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="casos_sociales", verbose_name="profesional a cargo",
        help_text="Quién lleva el caso hasta cerrarlo.",
    )
    ingreso = models.DateField(
        "fecha de ingreso",
        help_text="Desde aquí corren los plazos. Por omisión, el día de la atención.",
    )
    requiere_visita = models.BooleanField(
        "requiere visita", default=True,
        help_text="Desmárcalo si el caso se resuelve sin visita a terreno.",
    )
    visita_programada = models.DateField("visita programada para", null=True, blank=True)
    visita_realizada = models.DateField("visita realizada el", null=True, blank=True)
    informe_entregado = models.DateField("informe entregado el", null=True, blank=True)
    lleva_beneficio = models.BooleanField(
        "termina en un beneficio", default=True,
        help_text="Desmárcalo si el caso se cierra con el informe.",
    )
    beneficio_entregado = models.DateField("beneficio entregado el", null=True, blank=True)
    devoluciones = models.PositiveSmallIntegerField(
        "devoluciones del informe", default=0,
        help_text="Cuántas veces el informe volvió para corregir antes de aceptarse.",
    )
    observacion = models.TextField("observaciones", blank=True)
    creado = models.DateTimeField("abierto el", auto_now_add=True)
    actualizado = models.DateTimeField("actualizado el", auto_now=True)

    class Meta:
        verbose_name = "caso social"
        verbose_name_plural = "casos sociales"
        ordering = ["-ingreso", "-codigo"]

    def __str__(self):
        return f"{self.codigo} — {self.atencion.solicitante.nombre}"

    # --- validación ------------------------------------------------------

    def clean(self):
        super().clean()
        from datetime import date

        hoy = date.today()
        errores = {}

        def no_antes(campo, fecha, referencia, texto):
            if fecha and referencia and fecha < referencia:
                errores[campo] = texto

        for campo in ("ingreso", "visita_realizada", "informe_entregado",
                      "beneficio_entregado"):
            fecha = getattr(self, campo)
            if fecha and fecha > hoy:
                errores[campo] = "Es algo que ya ocurrió: no puede tener fecha futura."

        no_antes("visita_programada", self.visita_programada, self.ingreso,
                 "La visita no puede programarse antes del ingreso del caso.")
        no_antes("visita_realizada", self.visita_realizada, self.ingreso,
                 "La visita no puede ser anterior al ingreso del caso.")
        inicio_informe = self.visita_realizada if self.requiere_visita else self.ingreso
        no_antes("informe_entregado", self.informe_entregado, inicio_informe,
                 "El informe no puede ser anterior a la visita ni al ingreso.")
        no_antes("beneficio_entregado", self.beneficio_entregado, self.informe_entregado,
                 "El beneficio se entrega después del informe.")

        if not self.requiere_visita and (self.visita_programada or self.visita_realizada):
            errores["requiere_visita"] = (
                "Si el caso no requiere visita, deja vacías sus fechas."
            )
        if self.requiere_visita and self.informe_entregado and not self.visita_realizada:
            errores["visita_realizada"] = (
                "Falta la fecha de la visita: el informe se hace después de ella."
            )
        if self.beneficio_entregado and not self.informe_entregado:
            errores["informe_entregado"] = "Falta la fecha del informe."
        if not self.lleva_beneficio and self.beneficio_entregado:
            errores["lleva_beneficio"] = (
                "Si el caso no termina en un beneficio, deja vacía su fecha."
            )
        if self.devoluciones is not None and self.devoluciones > 9:
            errores["devoluciones"] = "Más de nueve devoluciones no es un dato creíble."
        if errores:
            raise ValidationError(errores)

    # --- lo que la pantalla pregunta -------------------------------------

    @property
    def cierre(self):
        """La fecha en que el caso quedó cerrado, o None si sigue abierto."""
        if self.lleva_beneficio:
            return self.beneficio_entregado
        return self.informe_entregado

    @property
    def cerrado(self):
        return self.cierre is not None

    @property
    def siguiente_paso(self):
        """Lo que falta, en palabras."""
        if self.requiere_visita and not self.visita_programada:
            return "Programar la visita"
        if self.requiere_visita and not self.visita_realizada:
            return "Hacer la visita"
        if not self.informe_entregado:
            return "Entregar el informe"
        if self.lleva_beneficio and not self.beneficio_entregado:
            return "Entregar el beneficio"
        return "Cerrado"

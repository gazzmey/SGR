"""
Atención ciudadana: quién consulta y qué se le resolvió.

``Solicitante`` es el **vecino** de la Evaluación 3: la persona que acude a
la delegación. En la segunda entrega no tenía pantalla propia y se creaba
desde el ingreso de atención; desde esta entrega tiene su propio
mantenedor (Comunidad › Vecinos) y se relaciona con un **territorio** del
catálogo en lugar de un texto libre. El ingreso de atención sigue
creándolo o reutilizándolo por RUT, como antes.

La clase conserva su nombre para no reescribir la tabla ni las
migraciones; en pantalla se llama «vecino».

Las relaciones que importan usan ``PROTECT``: una atención conserva a
quién se atendió y qué subatención se usó, aunque después esa subatención se
desactive. Un vecino no se borra: se desactiva.
"""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


# El RUT se valida en comun/rut.py. Se reexporta con los mismos nombres
# porque las migraciones de esta app apuntan a atencion.models.validar_rut.
from comun.rut import limpiar_rut, rut_valido, validar_rut  # noqa: E402,F401


class Solicitante(models.Model):
    """El vecino: persona que acude a la delegación."""

    rut = models.CharField(
        "RUT", max_length=12, unique=True, validators=[validar_rut],
        help_text="Ficticio, con dígito verificador. Por ejemplo 11111111-1.",
    )
    nombres = models.CharField(max_length=120)
    apellidos = models.CharField(max_length=120, blank=True)
    telefono = models.CharField("teléfono", max_length=20, blank=True)
    correo = models.EmailField("correo", max_length=150, blank=True)
    direccion = models.CharField("dirección", max_length=160, blank=True)
    territorio = models.ForeignKey(
        "organizacion.Territorio", on_delete=models.PROTECT,
        related_name="vecinos", null=True, blank=True,
        verbose_name="territorio",
        help_text="La unidad vecinal donde vive. Define a qué junta puede integrarse.",
    )
    sector = models.CharField(
        "sector registrado antes", max_length=80, blank=True,
        help_text=(
            "El texto libre de la segunda entrega, antes del catálogo de "
            "territorios. Se conserva como referencia histórica."
        ),
    )
    activo = models.BooleanField(default=True)
    creada = models.DateField("registrado el", auto_now_add=True)
    desactivada = models.DateField("desactivado el", null=True, blank=True)

    class Meta:
        verbose_name = "vecino"
        verbose_name_plural = "vecinos"
        ordering = ["apellidos", "nombres"]

    def __str__(self):
        return f"{self.rut} — {self.nombre}"

    @property
    def nombre(self):
        """Nombres y apellidos juntos, como se muestra en pantalla."""
        return " ".join(p for p in (self.nombres, self.apellidos) if p).strip()

    def save(self, *args, **kwargs):
        self.rut = limpiar_rut(self.rut)
        super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        if self.territorio_id and not self.pk and not self.territorio.activo:
            raise ValidationError({"territorio": "Ese territorio está inactivo."})

    def motivo_bloqueo(self):
        """Un vecino que integra una junta no se desactiva sin terminar esa participación."""
        cuantas = self.participaciones.filter(activo=True).count()
        if cuantas:
            return (
                f"Participa en {cuantas} "
                f"{'junta de vecinos' if cuantas == 1 else 'juntas de vecinos'}. "
                "Termina esas participaciones antes de desactivarlo."
            )
        return ""

    def motivo_bloqueo_activar(self):
        if self.territorio_id and not self.territorio.activo:
            return "Su territorio está inactivo. Actívalo primero o cámbiale el territorio."
        return ""


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

    class Estado(models.TextChoices):
        EN_CURSO = "en_curso", "En curso"
        CERRADO = "cerrado", "Cerrado"
        ANULADO = "anulado", "Anulado"

    atencion = models.OneToOneField(
        Atencion, on_delete=models.PROTECT, related_name="caso",
        verbose_name="atención",
    )
    codigo = models.CharField("código", max_length=12, unique=True)
    fecha_atencion = models.DateField(
        "fecha de atención", null=True, blank=True,
        help_text="Cuándo se atendió a la persona. No puede ser posterior al ingreso del caso.",
    )
    asignacion = models.ForeignKey(
        "gestion.MetaPeriodo", on_delete=models.PROTECT,
        related_name="gestiones_sociales", null=True, blank=True,
        verbose_name="asignación de meta",
        help_text="La meta a la que aporta esta gestión. Opcional.",
    )
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
    actuaciones = models.TextField(
        blank=True,
        help_text="Lo que se hizo en el caso: llamados, coordinaciones, trámites.",
    )
    derivacion = models.CharField(
        "derivación", max_length=160, blank=True,
        help_text="A qué institución o programa se derivó, si corresponde.",
    )
    resultado = models.TextField(
        blank=True, help_text="Cómo terminó el caso para la persona.",
    )
    estado = models.CharField(
        max_length=10, choices=Estado.choices, default=Estado.EN_CURSO,
        help_text="Se calcula solo: cerrado cuando se entrega lo último que falta. Anulado no se revierte.",
    )
    motivo_anulacion = models.TextField("motivo de la anulación", blank=True)
    observacion = models.TextField("observaciones", blank=True)
    creado = models.DateTimeField("abierto el", auto_now_add=True)
    actualizado = models.DateTimeField("actualizado el", auto_now=True)

    class Meta:
        verbose_name = "gestión social"
        verbose_name_plural = "gestiones sociales"
        ordering = ["-ingreso", "-codigo"]

    def __str__(self):
        return f"{self.codigo} — {self.atencion.solicitante.nombre}"

    @property
    def nombre(self):
        return f"{self.atencion.solicitante.nombre} · {self.atencion.subatencion.nombre}"

    @property
    def anulado(self):
        return self.estado == self.Estado.ANULADO

    def save(self, *args, **kwargs):
        # El estado sale de las fechas, salvo que el caso esté anulado.
        if self.estado != self.Estado.ANULADO:
            self.estado = self.Estado.CERRADO if self.cierre else self.Estado.EN_CURSO
        campos = kwargs.get("update_fields")
        if campos is not None and "estado" not in campos:
            kwargs["update_fields"] = list(campos) + ["estado"]
        super().save(*args, **kwargs)

    # --- validación ------------------------------------------------------

    def clean(self):
        super().clean()
        from datetime import date

        hoy = date.today()
        errores = {}

        def no_antes(campo, fecha, referencia, texto):
            if fecha and referencia and fecha < referencia:
                errores[campo] = texto

        for campo in ("ingreso", "fecha_atencion", "visita_realizada",
                      "informe_entregado", "beneficio_entregado"):
            fecha = getattr(self, campo)
            if fecha and fecha > hoy:
                errores[campo] = "Es algo que ya ocurrió: no puede tener fecha futura."

        # Cierre semanal: una gestión social nueva no se ingresa en una
        # semana ya cerrada (gestion/semanas.py).
        if (self._state.adding or not self.pk) and "ingreso" not in errores:
            from gestion.semanas import motivo_semana_cerrada

            motivo = motivo_semana_cerrada(self.ingreso)
            if motivo:
                errores["ingreso"] = motivo

        no_antes("ingreso", self.ingreso, self.fecha_atencion,
                 "El caso no puede ingresar antes de que se atendiera a la persona.")
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
        if self.asignacion_id and "asignacion" not in errores:
            motivo = self.asignacion.motivo_no_aplica(self.responsable if self.responsable_id else None,
                                                      fecha=self.ingreso)
            if motivo:
                errores["asignacion"] = motivo
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


# Los regalos para niños van en su propio archivo; se importan aquí para que
# Django los registre en esta aplicación.
from atencion.modelos_regalos import CampanaRegalos, InscripcionRegalo  # noqa: E402,F401
from atencion.modelos_comunidad import JuntaVecinos, ParticipacionJunta  # noqa: E402,F401

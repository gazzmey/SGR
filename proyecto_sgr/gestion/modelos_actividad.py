"""
Actividades y evidencias.

La cadena completa del sistema es esta: una persona **registra una
actividad**, le **adjunta una evidencia**, un verificador la **aprueba**, y
recién entonces esa actividad **suma** a su meta. Mientras la evidencia no
esté aprobada, la actividad existe pero no puntúa.

Esa regla —que lo registrado no vale hasta que alguien lo valida— es la que
sostiene todo el resto del sistema, y por eso vive en el modelo y no en una
vista: da igual por dónde entre el dato, una actividad sin evidencia
aprobada no aporta.

Por qué el código de la evidencia no cambia nunca
-------------------------------------------------
``Evidencia.codigo`` se asigna al crearla y no se vuelve a tocar. Es lo que
permite que una evidencia aprobada en julio siga siendo identificable en
diciembre, aunque la actividad se haya editado en el medio. El caso EVI-01
comprueba exactamente eso.
"""

from datetime import date

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from gestion.evidencias import (
    es_imagen, extension, ruta_evidencia, se_muestra_en_navegador, tamano_texto,
)


class Actividad(models.Model):
    """Algo que una persona hizo y que cuenta para una meta suya."""

    class Estado(models.TextChoices):
        BORRADOR = "borrador", "Sin evidencia"
        PENDIENTE = "pendiente", "Pendiente de validación"
        APROBADA = "aprobada", "Aprobada"
        RECHAZADA = "rechazada", "Rechazada"
        ANULADA = "anulada", "Anulada"

    class Tipo(models.TextChoices):
        TERRENO = "terreno", "Terreno"
        OFICINA = "oficina", "Oficina"
        REUNION = "reunion", "Reunión"
        COORDINACION = "coordinacion", "Coordinación"
        OTRA = "otra", "Otra"

    class Origen(models.TextChoices):
        PLANIFICADA = "planificada", "Planificada por la delegación"
        COMUNIDAD = "comunidad", "Solicitud de la comunidad"
        MUNICIPIO = "municipio", "Encargo del municipio"
        DERIVACION = "derivacion", "Derivación de otra unidad"

    #: Los campos que deciden cuánto suma. Con la actividad aprobada ya no se
    #: cambian: cambiarlos alteraría un puntaje que otra persona validó.
    CAMPOS_DEL_CALCULO = ["funcionario", "asignacion", "fecha", "cantidad"]

    codigo = models.CharField(
        "código", max_length=12, unique=True,
        help_text="Identificador corto e irrepetible, por ejemplo ACT-0001.",
    )
    funcionario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="actividades", verbose_name="funcionario",
    )
    delegacion = models.ForeignKey(
        "organizacion.Delegacion", on_delete=models.PROTECT,
        related_name="actividades", verbose_name="delegación",
        help_text="La delegación activa de quien la registró.",
    )
    periodo = models.ForeignKey(
        "gestion.Periodo", on_delete=models.PROTECT,
        related_name="actividades", verbose_name="período",
    )
    item = models.ForeignKey(
        "catalogos.Item", on_delete=models.PROTECT,
        related_name="actividades", verbose_name="ítem",
        help_text="A qué meta suma esta actividad cuando se apruebe.",
    )
    fecha = models.DateField(
        "fecha de la actividad",
        help_text="Cuándo ocurrió. Tiene que caer dentro del período.",
    )
    cantidad = models.PositiveIntegerField(
        "cuánto acredita", default=1,
        validators=[MinValueValidator(1)],
        help_text=(
            "Cuántas unidades del ítem acredita esta actividad, en la unidad "
            "del ítem. Una mesa territorial donde se atendió a 15 vecinos "
            "acredita 15, no 1."
        ),
    )
    accion = models.CharField(
        "acción realizada", max_length=160,
        help_text="En una línea: qué se hizo.",
    )
    detalle = models.TextField(
        help_text="Qué se hizo, con quién y qué resultó. Es lo que lee el verificador.",
    )
    contacto = models.CharField(
        max_length=120, blank=True,
        help_text="Con quién se coordinó. Opcional.",
    )
    asignacion = models.ForeignKey(
        "gestion.MetaPeriodo", on_delete=models.PROTECT,
        related_name="actividades", null=True, blank=True,
        verbose_name="asignación de meta",
        help_text="La meta a la que suma. Define el ítem y el período.",
    )
    hito = models.ForeignKey(
        "gestion.Hito", on_delete=models.PROTECT,
        related_name="actividades", null=True, blank=True, verbose_name="hito",
        help_text="Opcional: el hito planificado al que corresponde.",
    )
    tipo = models.CharField(
        "tipo de actividad", max_length=14, choices=Tipo.choices, default=Tipo.TERRENO,
    )
    origen = models.CharField(
        max_length=12, choices=Origen.choices, default=Origen.PLANIFICADA,
    )
    solicitante = models.ForeignKey(
        "atencion.Solicitante", on_delete=models.PROTECT,
        related_name="actividades", null=True, blank=True, verbose_name="solicitante",
        help_text="El vecino que la pidió, si vino de la comunidad.",
    )
    territorio = models.ForeignKey(
        "organizacion.Territorio", on_delete=models.PROTECT,
        related_name="actividades", null=True, blank=True, verbose_name="territorio",
        help_text="Dónde ocurrió. Tiene que ser de la misma delegación.",
    )
    responsable = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="actividades_a_cargo", null=True, blank=True,
        verbose_name="responsable",
        help_text="Quién responde por el seguimiento. Por omisión, quien la registra.",
    )
    fecha_compromiso = models.DateField(
        "fecha de compromiso", null=True, blank=True,
        help_text="Hasta cuándo hay plazo para el seguimiento. No puede ser anterior a la fecha de la actividad.",
    )
    apoyo = models.CharField(
        max_length=160, blank=True,
        help_text="Quién o qué apoyó: otra unidad, un vehículo, materiales.",
    )
    avance = models.PositiveSmallIntegerField(
        "avance (%)", default=100,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Cuánto del trabajo está hecho, de 0 a 100.",
    )
    resultado = models.TextField(
        blank=True, help_text="Qué se logró. Opcional.",
    )
    estado = models.CharField(
        max_length=10, choices=Estado.choices, default=Estado.BORRADOR,
    )
    motivo_anulacion = models.TextField(
        "motivo de la anulación", blank=True,
    )
    registrada = models.DateTimeField("registrada el", auto_now_add=True)
    actualizada = models.DateTimeField("actualizada el", auto_now=True)

    class Meta:
        verbose_name = "actividad"
        verbose_name_plural = "actividades"
        ordering = ["-fecha", "-registrada"]

    def __str__(self):
        return f"{self.codigo} — {self.accion}"

    @property
    def nombre(self):
        return self.accion

    @property
    def anulada(self):
        return self.estado == self.Estado.ANULADA

    def save(self, *args, **kwargs):
        # La asignación decide a qué ítem y período suma: si viene, manda.
        # Si no viene —el registro de «Mis actividades» elige el ítem—, se
        # busca la que mide a esa persona: la suya o la de su cargo.
        if self.asignacion_id:
            self.item_id = self.asignacion.item_id
            self.periodo_id = self.asignacion.periodo_id
        elif self.funcionario_id and self.periodo_id and self.item_id:
            from gestion.models import MetaPeriodo

            asignacion = MetaPeriodo.vigente_para(self.funcionario, self.periodo, self.item)
            if asignacion is not None:
                self.asignacion = asignacion
        if not self.responsable_id and self.funcionario_id:
            self.responsable_id = self.funcionario_id
        campos = kwargs.get("update_fields")
        if campos is not None:
            kwargs["update_fields"] = list(set(campos) | {"asignacion", "responsable"})
        super().save(*args, **kwargs)

    # --- validación ------------------------------------------------------

    def clean(self):
        """
        La fecha tiene que caer dentro del período, y el período estar abierto.

        Sin la primera regla, una actividad de marzo podría sumar al período
        de octubre. Sin la segunda, se podría alterar el resultado de un
        período ya cerrado, que es justo lo que el cierre impide.
        """
        super().clean()

        errores = {}
        if self.asignacion_id:
            motivo = self.asignacion.motivo_no_aplica(
                self.funcionario if self.funcionario_id else None)
            if motivo:
                errores["asignacion"] = motivo
            else:
                self.item_id = self.asignacion.item_id
                self.periodo_id = self.asignacion.periodo_id
        if self.fecha and self.fecha_compromiso and self.fecha_compromiso < self.fecha:
            errores["fecha_compromiso"] = (
                "La fecha de compromiso no puede ser anterior a la fecha de la "
                "actividad (%s)." % self.fecha.strftime("%d-%m-%Y")
            )
        if (self.territorio_id and self.delegacion_id
                and self.territorio.delegacion_id != self.delegacion_id):
            errores["territorio"] = "«%s» es de %s, no de %s." % (
                self.territorio.nombre, self.territorio.delegacion.nombre,
                self.delegacion.nombre)
        if self.hito_id and self.delegacion_id and self.hito.delegacion_id != self.delegacion_id:
            errores["hito"] = "El hito «%s» es de %s, no de %s." % (
                self.hito.nombre, self.hito.delegacion.nombre, self.delegacion.nombre)
        if self.avance is not None and self.avance > 100:
            errores["avance"] = "El avance va de 0 a 100."
        if errores:
            raise ValidationError(errores)

        # Cero no es «no hizo nada»: es una actividad que no acredita nada y
        # que solo ensucia el conteo. Si no hubo nada que acreditar, la
        # actividad no se registra.
        if self.cantidad is not None and self.cantidad < 1:
            raise ValidationError({
                "cantidad": "Una actividad acredita al menos una unidad del ítem.",
            })

        if not self.periodo_id or not self.fecha:
            return

        if not (self.periodo.inicio <= self.fecha <= self.periodo.termino):
            raise ValidationError({
                "fecha": (
                    "La fecha tiene que estar dentro de «%s», que va del %s al %s."
                    % (self.periodo.nombre,
                       self.periodo.inicio.strftime("%d-%m-%Y"),
                       self.periodo.termino.strftime("%d-%m-%Y"))
                ),
            })

        # Una actividad es el registro de algo que **ya ocurrió**. Estar
        # dentro del período no basta: un período que termina en diciembre
        # admitiría una actividad fechada en noviembre, y hoy es octubre.
        #
        # No es un detalle cosmético. El tablero mide los días que lleva cada
        # persona sin registrar restando la fecha de su última actividad a la
        # de hoy; con una fecha futura esa resta da negativo y la columna
        # muestra «−21 días sin registrar», que no significa nada. Y en el
        # fondo permitía acreditar avance por trabajo que todavía no se hizo.
        hoy = date.today()
        if self.fecha > hoy:
            raise ValidationError({
                "fecha": (
                    "La fecha no puede ser futura: una actividad se registra "
                    "después de hacerla. Hoy es %s."
                    % hoy.strftime("%d-%m-%Y")
                ),
            })

        from gestion.models import Periodo

        if self.periodo.estado == Periodo.Estado.CERRADO:
            raise ValidationError(
                "«%s» está cerrado: su resultado quedó congelado y no admite "
                "actividades nuevas." % self.periodo.nombre
            )

        # Cierre semanal: lo de una semana se ingresa hasta poco después del
        # domingo. Vale al registrar y al mover la fecha de una existente;
        # completar otros datos de una actividad ya registrada sigue
        # permitido. Ver gestion/semanas.py.
        if self._fecha_nueva():
            from gestion.semanas import motivo_semana_cerrada

            motivo = motivo_semana_cerrada(self.fecha, self.periodo)
            if motivo:
                raise ValidationError({"fecha": motivo})

    def _fecha_nueva(self):
        """True al registrarla o si se le está cambiando la fecha."""
        if self._state.adding or not self.pk:
            return True
        anterior = type(self).objects.filter(pk=self.pk).values_list("fecha", flat=True).first()
        return anterior != self.fecha

    # --- lo que el resto del sistema le pregunta -------------------------

    @property
    def puntua(self):
        """
        ¿Esta actividad suma a la meta?

        Solo si está aprobada. Es la regla que sostiene el cálculo: lo
        registrado no vale hasta que alguien lo valida.
        """
        return self.estado == self.Estado.APROBADA

    @property
    def evidencia_vigente(self):
        """La última evidencia que no fue anulada."""
        return self.evidencias.exclude(anulada=True).order_by("-creada").first()

    def motivo_bloqueo(self):
        if self.estado == self.Estado.APROBADA:
            return (
                "Está aprobada y ya suma a la meta del período. Anúlala con su "
                "motivo en vez de desactivarla: así el historial explica por qué "
                "dejó de contar."
            )
        return ""

    def motivo_no_editable(self, usuario=None):
        """
        Una actividad aprobada ya no se modifica (guía de la evaluación 3).

        Otra persona validó lo que dice; cambiarlo después, aunque sea el
        detalle, haría que lo aprobado y lo guardado dejen de coincidir. Si
        tiene un error se anula con motivo y se registra de nuevo.
        """
        if self.estado == self.Estado.APROBADA:
            return (
                "Está aprobada: un verificador ya la validó y suma a la meta, "
                "así que no se modifica. Si tiene un error, anúlala con su "
                "motivo y regístrala de nuevo."
            )
        if self.estado == self.Estado.ANULADA:
            return "Está anulada: se conserva tal como quedó, con su motivo."
        return ""


class Evidencia(models.Model):
    """
    El respaldo de una actividad, y la decisión del verificador sobre él.

    Desde HU-09 la evidencia lleva el **archivo**: un PDF o una foto que se
    guarda con un nombre que genera el sistema y se entrega solo a quien
    puede verlo (ver ``gestion/evidencias.py``). La referencia queda como dato
    opcional —el número del acta, un folio— y las evidencias registradas
    antes de HU-09 siguen siendo válidas sin archivo.
    """

    class Decision(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente"
        APROBADA = "aprobada", "Aprobada"
        RECHAZADA = "rechazada", "Rechazada"

    class Tipo(models.TextChoices):
        ACTA = "acta", "Acta"
        FOTOGRAFIA = "fotografia", "Fotografía"
        LISTA = "lista", "Lista de asistencia"
        INFORME = "informe", "Informe"
        OFICIO = "oficio", "Oficio o carta"
        OTRO = "otro", "Otro documento"

    codigo = models.CharField(
        "código", max_length=12, unique=True,
        help_text="Se asigna al crearla y no cambia nunca.",
    )
    actividad = models.ForeignKey(
        Actividad, on_delete=models.PROTECT, null=True, blank=True,
        related_name="evidencias", verbose_name="actividad",
    )
    caso = models.ForeignKey(
        "atencion.CasoSocial", on_delete=models.PROTECT, null=True, blank=True,
        related_name="evidencias", verbose_name="gestión social",
        help_text="Si respalda una gestión social en vez de una actividad.",
    )
    tipo = models.CharField(
        max_length=12, choices=Tipo.choices, default=Tipo.ACTA,
    )
    descripcion = models.CharField(
        "qué respalda", max_length=160,
        help_text="Qué es el documento y qué acredita.",
    )
    referencia = models.CharField(
        max_length=120, blank=True,
        help_text="Número del acta, folio u otro dato que identifique el documento.",
    )
    archivo = models.FileField(
        upload_to=ruta_evidencia, max_length=200, blank=True,
        help_text="Se guarda con un nombre que genera el sistema, nunca con el original.",
    )
    nombre_original = models.CharField(
        "nombre original", max_length=160, blank=True,
        help_text="Cómo se llamaba el archivo en el equipo de quien lo subió. Solo se muestra.",
    )
    tamano = models.PositiveIntegerField("tamaño en bytes", null=True, blank=True)
    autor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="evidencias_cargadas", verbose_name="cargada por",
    )
    creada = models.DateTimeField("cargada el", auto_now_add=True)

    decision = models.CharField(
        "decisión", max_length=10,
        choices=Decision.choices, default=Decision.PENDIENTE,
    )
    verificador = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="evidencias_validadas", null=True, blank=True,
        verbose_name="verificador",
    )
    decidida = models.DateTimeField("decidida el", null=True, blank=True)
    motivo = models.TextField(
        "motivo del rechazo", blank=True,
        help_text="Obligatorio al rechazar: es lo que la persona tiene que corregir.",
    )
    observacion = models.TextField(
        "observación", blank=True,
        help_text="Lo que conviene saber al revisarla. Opcional.",
    )
    anulada = models.BooleanField(default=False)
    motivo_anulacion = models.TextField("motivo de la anulación", blank=True)

    class Meta:
        verbose_name = "evidencia"
        verbose_name_plural = "evidencias"
        ordering = ["-creada"]
        constraints = [
            # Cada evidencia respalda exactamente un registro de origen: una
            # actividad o una gestión social, nunca las dos ni ninguna.
            models.CheckConstraint(
                check=(models.Q(actividad__isnull=False, caso__isnull=True)
                       | models.Q(actividad__isnull=True, caso__isnull=False)),
                name="evidencia_de_un_solo_origen",
            ),
        ]

    def __str__(self):
        return f"{self.codigo} — {self.descripcion}"

    @property
    def nombre(self):
        return self.descripcion

    @property
    def origen(self):
        """La actividad o la gestión social que respalda."""
        return self.actividad if self.actividad_id else self.caso

    @property
    def origen_texto(self):
        if self.actividad_id:
            return f"Actividad {self.actividad.codigo} · {self.actividad.accion}"
        if self.caso_id:
            return f"Gestión social {self.caso.codigo} · {self.caso.atencion.solicitante.nombre}"
        return "—"

    @property
    def delegacion_id_origen(self):
        if self.actividad_id:
            return self.actividad.delegacion_id
        if self.caso_id:
            return self.caso.atencion.delegacion_id
        return None

    @property
    def responsable_id_origen(self):
        """Quién hizo el trabajo que la evidencia respalda."""
        if self.actividad_id:
            return self.actividad.funcionario_id
        if self.caso_id:
            return self.caso.responsable_id
        return None

    def clean(self):
        super().clean()
        if bool(self.actividad_id) == bool(self.caso_id):
            raise ValidationError(
                "La evidencia respalda una actividad o una gestión social: "
                "elige exactamente una de las dos."
            )
        if self.decision == self.Decision.RECHAZADA and not self.motivo.strip():
            raise ValidationError({
                "motivo": (
                    "Rechazar sin motivo deja a la persona sin saber qué "
                    "corregir. Explica qué falta."
                ),
            })

    @property
    def pendiente(self):
        return self.decision == self.Decision.PENDIENTE and not self.anulada

    # --- el archivo, para las plantillas ------------------------------------

    @property
    def archivo_nombre(self):
        return self.nombre_original or (self.archivo.name.rsplit("/", 1)[-1] if self.archivo else "")

    @property
    def archivo_formato(self):
        return extension(self.archivo.name).upper() if self.archivo else ""

    @property
    def archivo_tamano(self):
        return tamano_texto(self.tamano)

    @property
    def archivo_es_imagen(self):
        return bool(self.archivo) and es_imagen(self.archivo.name)

    @property
    def archivo_se_abre(self):
        return bool(self.archivo) and se_muestra_en_navegador(self.archivo.name)

    @property
    def verificador_visible(self):
        """
        Quién la decidió, sin suponer que siempre hay alguien.

        ``verificador`` admite nulo, y aunque las vistas lo escriben junto
        con la fecha de la decisión, nada garantiza que una fila escrita por
        otra vía tenga los dos. Resolverlo acá evita que la plantilla tenga
        que encadenar filtros sobre un valor que puede ser ``None``, que es
        justo lo que tumba la página en vez de mostrar un hueco.
        """
        if self.verificador_id:
            return self.verificador.get_full_name() or self.verificador.get_username()
        return "—"

    def motivo_bloqueo(self):
        if self.decision == self.Decision.APROBADA and not self.anulada:
            return (
                "Está aprobada y su actividad ya suma al período. Anúlala con "
                "su motivo si hay que revertirla."
            )
        return ""

    def motivo_no_editable(self, usuario=None):
        """Solo se edita una evidencia pendiente de decisión."""
        if self.anulada:
            return "Está anulada: se conserva tal como quedó, con su motivo."
        if self.decision == self.Decision.APROBADA:
            return (
                "Está aprobada: es el respaldo que validó el verificador, así "
                "que no se modifica. Si hay que revertirla, anúlala con su motivo."
            )
        if self.decision == self.Decision.RECHAZADA:
            return (
                "Está rechazada y su decisión queda registrada. La corrección "
                "se hace adjuntando una evidencia nueva a la actividad."
            )
        return ""

"""
La agenda colectiva: compromisos con la comunidad, su estado y su plazo.

Un compromiso es algo que la delegación se comprometió a hacer: una reparación
de luminaria, una visita, un informe para una junta de vecinos. Nace de una
actividad o se ingresa directo, tiene un responsable y una fecha de
vencimiento, y recorre estados hasta quedar realizado.

Es «colectiva» porque la ve toda la delegación, no solo quien la creó. Esa es
la diferencia con *Mis actividades*: la actividad es el registro personal de
lo que alguien hizo; el compromiso es una deuda de la delegación con alguien
de afuera, y si el responsable se ausenta, otra persona tiene que poder
tomarla. De ahí la reasignación del caso AGE-06.

Las tres reglas que sostienen el módulo
---------------------------------------
**No se salta estados.** Las transiciones permitidas están en ``TRANSICIONES``
y se comprueban en el servidor. Un compromiso no puede pasar de Ingresado a
Realizado: eso sería cerrar algo que nadie trabajó, y el caso AGE-03 pide
expresamente que una transición prohibida se rechace.

**El atraso se guarda, no se recalcula.** Al cerrar se escribe si llegó
tarde. Si el atraso se dedujera comparando fechas cada vez que se consulta,
cambiar la regla de vencimiento reescribiría el pasado. El caso AGE-04 lo pide
con «cierre conserva atraso».

**Realizado no es lo mismo que puntuado.** Un compromiso que exige validación
y no la tiene está realizado pero no aporta a su ítem. Es el «cierre sin
validación requerida no otorga puntaje» de AGE-05.
"""

from datetime import date

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class Compromiso(models.Model):
    """Algo que la delegación se comprometió a hacer, con plazo y responsable."""

    class Estado(models.TextChoices):
        INGRESADO = "ingresado", "Ingresado"
        PENDIENTE = "pendiente", "Pendiente"
        EN_PROCESO = "en_proceso", "En proceso"
        REALIZADO = "realizado", "Realizado"
        ANULADO = "anulado", "Anulado"

    #: La matriz de transiciones permitidas.
    #:
    #: **Es la propuesta del equipo, no una matriz aprobada.** El plan de
    #: pruebas pide en AGE-03 «la matriz de transiciones aprobada» y en la
    #: sección B3 deja «las transiciones de agenda permitidas» entre los
    #: puntos por confirmar. Vive acá, en un solo lugar, para que aprobar otra
    #: sea cambiar este diccionario y nada más.
    #:
    #: El criterio: se avanza de uno en uno, se puede devolver un trabajo en
    #: proceso a pendiente, y se puede anular desde cualquier estado abierto.
    #: Lo que no se puede es saltarse el trabajo —Ingresado o Pendiente
    #: directo a Realizado— ni reabrir algo cerrado.
    TRANSICIONES = {
        Estado.INGRESADO: [Estado.PENDIENTE, Estado.ANULADO],
        Estado.PENDIENTE: [Estado.EN_PROCESO, Estado.ANULADO],
        Estado.EN_PROCESO: [Estado.REALIZADO, Estado.PENDIENTE, Estado.ANULADO],
        Estado.REALIZADO: [],
        Estado.ANULADO: [],
    }

    #: Los estados que cuentan como «no realizado» en el indicador colectivo.
    #: El anulado no está: un compromiso anulado sale del denominador en vez
    #: de contar como incumplido, porque dejó de ser una deuda.
    ABIERTOS = [Estado.INGRESADO, Estado.PENDIENTE, Estado.EN_PROCESO]

    codigo = models.CharField(
        "código", max_length=12, unique=True,
        help_text="Identificador corto e irrepetible, por ejemplo CMP-0001.",
    )
    delegacion = models.ForeignKey(
        "organizacion.Delegacion", on_delete=models.PROTECT,
        related_name="compromisos", verbose_name="delegación",
    )
    periodo = models.ForeignKey(
        "gestion.Periodo", on_delete=models.PROTECT,
        related_name="compromisos", verbose_name="período",
    )
    actividad = models.ForeignKey(
        "gestion.Actividad", on_delete=models.PROTECT,
        related_name="compromisos", null=True, blank=True,
        verbose_name="actividad de origen",
        help_text=(
            "Si el compromiso nació de una actividad registrada, queda "
            "vinculado a ella. Opcional: también se puede ingresar directo."
        ),
    )
    item = models.ForeignKey(
        "catalogos.Item", on_delete=models.PROTECT,
        related_name="compromisos", null=True, blank=True,
        verbose_name="ítem al que alimenta",
        help_text=(
            "Si se elige, el compromiso realizado y validado cuenta para la "
            "meta de este ítem. Déjalo vacío si no alimenta ninguna meta."
        ),
    )

    solicitante = models.CharField(
        max_length=120,
        help_text="Quién lo pidió: una junta de vecinos, una persona, otra unidad.",
    )
    territorio = models.CharField(
        max_length=120,
        help_text="Dónde se cumple. Por ejemplo: Unidad vecinal 3 · San Juan.",
    )
    descripcion = models.TextField(
        "descripción",
        help_text="Qué se comprometió exactamente. Es contra esto que se cierra.",
    )

    responsable = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="compromisos", verbose_name="responsable",
        help_text="Quién responde por cumplirlo. Obligatorio.",
    )
    responsable_original = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="compromisos_originales", null=True, blank=True,
        verbose_name="responsable original",
        help_text=(
            "Se escribe al crear y no cambia nunca. Después de una "
            "reasignación es lo que permite saber de quién venía."
        ),
    )
    apoyo = models.CharField(
        max_length=160, blank=True,
        help_text="Quién más participa. Opcional.",
    )

    vencimiento = models.DateField(
        "fecha de vencimiento",
        help_text="Hasta cuándo hay plazo. Obligatorio: sin plazo no hay atraso.",
    )
    estado = models.CharField(
        max_length=12, choices=Estado.choices, default=Estado.INGRESADO,
    )

    requiere_validacion = models.BooleanField(
        "exige validación para puntuar", default=True,
        help_text=(
            "Si está marcado, cerrarlo no alimenta la meta del ítem hasta que "
            "alguien lo valide. Es la regla del caso AGE-05."
        ),
    )
    validado = models.BooleanField(default=False)
    validado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="compromisos_validados", null=True, blank=True,
        verbose_name="validado por",
    )
    validado_el = models.DateTimeField("validado el", null=True, blank=True)

    cerrado_el = models.DateField("cerrado el", null=True, blank=True)
    cerrado_con_atraso = models.BooleanField(
        "se cerró con atraso", default=False,
        help_text=(
            "Se calcula una sola vez, al cerrar, y queda escrito. Deducirlo "
            "después compararía con la regla de hoy y reescribiría el pasado."
        ),
    )
    dias_de_atraso = models.IntegerField(
        "días de atraso al cerrar", default=0,
        help_text="Cuántos días después del vencimiento se cerró. Cero si llegó a tiempo.",
    )

    observacion = models.TextField(
        "observación", blank=True,
        help_text="Lo último que se anotó. El historial completo está en los cambios.",
    )
    creado = models.DateTimeField("creado el", auto_now_add=True)
    actualizado = models.DateTimeField("actualizado el", auto_now=True)

    class Meta:
        verbose_name = "compromiso"
        verbose_name_plural = "compromisos"
        ordering = ["vencimiento", "codigo"]

    def __str__(self):
        return f"{self.codigo} — {self.solicitante}"

    # --- validación ------------------------------------------------------

    def clean(self):
        """
        Responsable y vencimiento son obligatorios, y el período tiene que
        estar abierto.

        Los dos primeros los exige el caso AGE-02 —«se rechaza e identifica el
        campo; no se crea compromiso incompleto»— y los declara el modelo como
        campos no nulos, así que Django ya los señala. Lo que se agrega acá es
        lo que el modelo no puede expresar solo.
        """
        super().clean()
        errores = {}

        if self.periodo_id and self.periodo.estado == self.periodo.Estado.CERRADO:
            errores["periodo"] = (
                "«%s» está cerrado: su resultado quedó congelado y no admite "
                "compromisos nuevos." % self.periodo.nombre
            )

        if self.item_id and not self.requiere_validacion:
            # No es un error, pero conviene que quede dicho en pantalla.
            pass

        if self.responsable_id and self.delegacion_id:
            perfil = getattr(self.responsable, "perfil", None)
            if perfil is not None and not perfil.activo:
                errores["responsable"] = (
                    "La cuenta de esa persona está inactiva. Elige a alguien "
                    "que pueda hacerse cargo de verdad."
                )

        if errores:
            raise ValidationError(errores)

    # --- plazos y atraso --------------------------------------------------

    @property
    def cerrado(self):
        return self.estado in (self.Estado.REALIZADO, self.Estado.ANULADO)

    @property
    def abierto(self):
        return self.estado in self.ABIERTOS

    def atraso_al_dia(self, al_dia=None):
        """
        Cuántos días de atraso lleva, a una fecha dada.

        Si ya está cerrado devuelve el atraso guardado, no uno nuevo: el caso
        AGE-04 pide que el cierre conserve el atraso con que se cerró.
        """
        if self.cerrado:
            return self.dias_de_atraso
        if not self.vencimiento:
            return 0
        hoy = al_dia or date.today()
        return max(0, (hoy - self.vencimiento).days)

    def esta_atrasado(self, al_dia=None):
        if self.cerrado:
            return self.cerrado_con_atraso
        return self.atraso_al_dia(al_dia) > 0

    def dias_para_vencer(self, al_dia=None):
        """Días que faltan. Negativo si ya venció."""
        if not self.vencimiento:
            return None
        hoy = al_dia or date.today()
        return (self.vencimiento - hoy).days

    # --- puntaje ----------------------------------------------------------

    @property
    def aporta(self):
        """
        ¿Este compromiso alimenta la meta de su ítem?

        Tres condiciones, y las tres hacen falta: que esté realizado, que
        tenga un ítem al que alimentar, y que esté validado si lo exige. La
        tercera es la que distingue «cerrado» de «puntuado», y es lo que
        comprueba AGE-05 con «cierre sin validación requerida no otorga
        puntaje».
        """
        if self.estado != self.Estado.REALIZADO or not self.item_id:
            return False
        return self.validado or not self.requiere_validacion

    @property
    def motivo_sin_puntaje(self):
        """Por qué no aporta, en palabras, para la ficha."""
        if self.estado != self.Estado.REALIZADO:
            return "Todavía no está realizado."
        if not self.item_id:
            return "No alimenta ninguna meta: no se le asignó un ítem."
        if self.requiere_validacion and not self.validado:
            return (
                "Está realizado pero exige validación y nadie lo ha validado "
                "aún. Cerrarlo no otorga puntaje por sí solo."
            )
        return ""

    # --- transiciones -----------------------------------------------------

    def destinos_posibles(self):
        """Los estados a los que puede pasar desde donde está."""
        return list(self.TRANSICIONES.get(self.estado, []))

    def puede_pasar_a(self, destino):
        return destino in self.TRANSICIONES.get(self.estado, [])

    def impedimento(self, destino):
        """
        Por qué no puede pasar a ese estado, o cadena vacía si puede.

        Devolver el motivo en vez de un booleano es deliberado: la pantalla
        necesita decirle a la persona qué pasó, y «transición no permitida» no
        le explica nada a quien está mirando.
        """
        if destino not in self.Estado.values:
            return "«%s» no es un estado del compromiso." % destino
        if destino == self.estado:
            return "Ya está en «%s»." % self.get_estado_display()
        if self.estado == self.Estado.REALIZADO:
            return (
                "Está realizado, y un compromiso cerrado no se reabre. Si hay "
                "que hacer algo más, ingresa un compromiso nuevo que lo cite."
            )
        if self.estado == self.Estado.ANULADO:
            return "Está anulado: su historial quedó cerrado."
        if not self.puede_pasar_a(destino):
            permitidos = ", ".join(
                dict(self.Estado.choices)[e] for e in self.destinos_posibles()
            ) or "ninguno"
            return (
                "No se puede pasar de «%s» a «%s»: saltarse el flujo cerraría "
                "un compromiso que nadie trabajó. Desde acá solo se puede ir "
                "a: %s." % (self.get_estado_display(),
                            dict(self.Estado.choices)[destino], permitidos)
            )
        return ""

    def motivo_bloqueo(self):
        if self.aporta:
            return (
                "Está realizado, validado y ya alimenta la meta de «%s». "
                "Anúlalo con su motivo si hay que revertirlo." % self.item
            )
        return ""


class CambioCompromiso(models.Model):
    """
    El historial de un compromiso: cada cambio de estado o de responsable.

    Guarda el antes y el después, quién lo hizo, cuándo y con qué observación.
    Es lo que piden AGE-03 —«permitidas guardadas con antes/después, autor,
    fecha y observación»— y AGE-06 —«se conserva origen y cambio auditado»—.

    Solo se agregan filas. Un historial que se puede editar no es un historial.
    """

    class Tipo(models.TextChoices):
        CREACION = "creacion", "Se ingresó"
        ESTADO = "estado", "Cambió de estado"
        RESPONSABLE = "responsable", "Se reasignó"
        VALIDACION = "validacion", "Se validó"

    compromiso = models.ForeignKey(
        Compromiso, on_delete=models.PROTECT, related_name="cambios",
        verbose_name="compromiso",
    )
    tipo = models.CharField(max_length=12, choices=Tipo.choices)
    estado_anterior = models.CharField(
        "estado anterior", max_length=12,
        choices=Compromiso.Estado.choices, blank=True,
    )
    estado_nuevo = models.CharField(
        "estado nuevo", max_length=12,
        choices=Compromiso.Estado.choices, blank=True,
    )
    responsable_anterior = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="compromisos_cedidos", null=True, blank=True,
        verbose_name="responsable anterior",
    )
    responsable_nuevo = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="compromisos_recibidos", null=True, blank=True,
        verbose_name="responsable nuevo",
    )
    observacion = models.TextField("observación", blank=True)
    quien = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="cambios_de_compromiso", null=True, blank=True,
        verbose_name="lo hizo",
    )
    cuando = models.DateTimeField("fecha", auto_now_add=True)

    class Meta:
        verbose_name = "cambio del compromiso"
        verbose_name_plural = "cambios de los compromisos"
        ordering = ["-cuando", "-pk"]

    def __str__(self):
        if self.tipo == self.Tipo.ESTADO:
            return "%s: %s → %s" % (
                self.compromiso.codigo,
                dict(Compromiso.Estado.choices).get(self.estado_anterior, "—"),
                dict(Compromiso.Estado.choices).get(self.estado_nuevo, "—"),
            )
        return f"{self.compromiso.codigo}: {self.get_tipo_display().lower()}"

    @property
    def usuario_visible(self):
        """
        Quién lo hizo, o «el sistema» si no fue nadie.

        ``quien`` admite nulo porque hay filas que no las escribe una
        persona: las que deja la carga de datos de demostración, por
        ejemplo. La plantilla **no** puede resolver esto con filtros
        encadenados: ``|default:c.quien.get_username`` obliga a Django a
        evaluar el argumento del filtro, y evaluarlo sobre ``None`` levanta
        ``VariableDoesNotExist`` y tumba la página entera. Un valor que puede
        faltar se resuelve en el modelo, que sí sabe qué hacer cuando falta.
        """
        if self.quien_id:
            return self.quien.get_full_name() or self.quien.get_username()
        return "el sistema"

    @property
    def resumen(self):
        """Una línea para la ficha, con el antes y el después."""
        estados = dict(Compromiso.Estado.choices)
        if self.tipo == self.Tipo.CREACION:
            return "Se ingresó el compromiso."
        if self.tipo == self.Tipo.ESTADO:
            return "De «%s» a «%s»." % (
                estados.get(self.estado_anterior, "—"),
                estados.get(self.estado_nuevo, "—"),
            )
        if self.tipo == self.Tipo.RESPONSABLE:
            def nombre(u):
                if u is None:
                    return "nadie"
                return u.get_full_name() or u.username
            return "De %s a %s." % (
                nombre(self.responsable_anterior),
                nombre(self.responsable_nuevo),
            )
        return "Se validó el cumplimiento."

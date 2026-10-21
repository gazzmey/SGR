"""
El período y lo que se configura dentro de él.

Un período es la ventana de tiempo sobre la que se mide: tiene fecha de
inicio y de término, se abre, se trabaja y se cierra. Todo lo que el sistema
calcula —avance, cumplimiento, resultado— se calcula *dentro de un período*,
y por eso este modelo es la base de los que vienen después.

Por qué las metas no viven en el ítem
-------------------------------------
``Item`` tiene ``meta`` y ``ponderador``, que vienen de la entrega anterior y
sirven como valor por omisión. Pero la meta real depende de dos cosas más: el
**cargo** de la persona —un inspector y una asistente social no se miden con
la misma vara— y el **período**. Por eso existe ``MetaPeriodo``, que cruza
las tres: período, cargo e ítem.

Lo importante de separarlos: cuando un período se cierra, sus metas quedan
congeladas. Cambiar la meta del año siguiente no altera el resultado del
período ya cerrado, que es justo lo que pide el caso PAR-04.

Sobre las fechas
----------------
El plan deja por aprobar la convención de días computables (B3). Aquí se
implementa la propuesta del lote CAL-D —días de calendario, contando inicio y
término— y queda registrada en un parámetro configurable, no escrita en el
código, para que cambiarla no exija tocar una línea.
"""

from datetime import date

from django.core.exceptions import ValidationError
from django.db import models


class Periodo(models.Model):
    """La ventana de tiempo sobre la que se mide la gestión."""

    class Estado(models.TextChoices):
        BORRADOR = "borrador", "En preparación"
        ABIERTO = "abierto", "Abierto"
        CERRADO = "cerrado", "Cerrado"

    codigo = models.CharField(
        "código", max_length=10, unique=True,
        help_text="Identificador corto e irrepetible, por ejemplo PER-01.",
    )
    nombre = models.CharField(
        max_length=80, unique=True,
        help_text="Cómo se le llama en los informes. Por ejemplo: Jul – Sep 2026.",
    )
    inicio = models.DateField("fecha de inicio")
    termino = models.DateField("fecha de término")
    estado = models.CharField(
        max_length=10, choices=Estado.choices, default=Estado.BORRADOR,
        help_text=(
            "En preparación se configura sin que nadie registre; abierto "
            "recibe actividades; cerrado congela metas y resultados."
        ),
    )
    cerrado_el = models.DateField("cerrado el", null=True, blank=True)
    cerrado_por = models.ForeignKey(
        "auth.User", on_delete=models.PROTECT,
        related_name="periodos_cerrados", null=True, blank=True,
        verbose_name="cerrado por",
    )
    observacion = models.TextField(
        "observación", blank=True,
        help_text="Queda en el historial. Útil al reabrir o al cerrar antes de tiempo.",
    )
    activo = models.BooleanField(default=True)
    creada = models.DateField("creado el", auto_now_add=True)
    desactivada = models.DateField("desactivado el", null=True, blank=True)

    class Meta:
        verbose_name = "período"
        verbose_name_plural = "períodos"
        ordering = ["-inicio"]

    def __str__(self):
        return f"{self.codigo} — {self.nombre}"

    # --- validación ------------------------------------------------------

    def clean(self):
        """
        El término no puede ser anterior al inicio, y dos períodos abiertos
        no pueden solaparse.

        Lo segundo importa más de lo que parece: si dos períodos abiertos se
        pisan, una actividad registrada en la zona común no sabría a cuál
        sumar, y el resultado dependería del orden en que se consulten.
        """
        super().clean()
        if self.inicio and self.termino and self.termino < self.inicio:
            raise ValidationError({
                "termino": "El término no puede ser anterior al inicio.",
            })

        if self.inicio and self.termino and self.estado != self.Estado.CERRADO:
            chocan = (
                Periodo.objects
                .filter(activo=True, inicio__lte=self.termino, termino__gte=self.inicio)
                .exclude(pk=self.pk)
                .exclude(estado=self.Estado.CERRADO)
            )
            otro = chocan.first()
            if otro is not None:
                raise ValidationError(
                    "Las fechas se cruzan con «%(otro)s» (%(desde)s al %(hasta)s), "
                    "que no está cerrado. Dos períodos abiertos que se pisan dejan "
                    "las actividades de los días comunes sin saber a cuál sumar." % {
                        "otro": otro.nombre,
                        "desde": otro.inicio.strftime("%d-%m-%Y"),
                        "hasta": otro.termino.strftime("%d-%m-%Y"),
                    }
                )

    # --- días y avance esperado -----------------------------------------

    @property
    def dias_totales(self):
        """
        Cuántos días dura, contando el primero y el último.

        Es la convención del lote CAL-D: del 01-10 al 30-10 son 30 días, no
        29. Está propuesta en el plan y pendiente de aprobación formal.
        """
        if not self.inicio or not self.termino:
            return 0
        return (self.termino - self.inicio).days + 1

    def dias_transcurridos(self, al_dia=None):
        """Días corridos desde el inicio hasta la fecha indicada, con tope."""
        if not self.inicio or not self.termino:
            return 0
        hoy = al_dia or date.today()
        if hoy < self.inicio:
            return 0
        if hoy > self.termino:
            return self.dias_totales
        return (hoy - self.inicio).days + 1

    def avance_esperado(self, al_dia=None):
        """
        Qué porcentaje del período debería llevarse a una fecha dada.

        CAL-D: antes del inicio 0 %; el día 15 de 30, 50 %; después del
        término, 100 %. Se devuelve con decimales y **sin redondear**: el
        semáforo compara contra este valor y redondear antes movería la
        frontera.
        """
        total = self.dias_totales
        if not total:
            return 0.0
        return round(self.dias_transcurridos(al_dia) * 100 / total, 4)

    @property
    def vigente(self):
        return self.estado == self.Estado.ABIERTO and self.activo

    # --- reglas de negocio ----------------------------------------------

    def motivo_bloqueo(self):
        """
        Un período con actividades registradas no se desactiva.

        El ``getattr`` no es timidez: el módulo de actividades llega después
        que este, y así el período funciona igual mientras tanto en vez de
        romperse por una relación que todavía no existe.
        """
        relacion = getattr(self, "actividades", None)
        cuantas = relacion.count() if relacion is not None else 0
        if cuantas:
            return (
                f"Tiene {cuantas} "
                f"{'actividad registrada' if cuantas == 1 else 'actividades registradas'}. "
                "Desactivarlo dejaría esos registros sin período al que sumar. "
                "Ciérralo en vez de desactivarlo."
            )
        return ""

    def suma_ponderadores(self, cargo=None):
        """Cuánto suman los ponderadores configurados, por cargo."""
        consulta = self.metas.filter(activo=True)
        if cargo is not None:
            consulta = consulta.filter(cargo=cargo)
        return consulta.aggregate(total=models.Sum("ponderador"))["total"] or 0


class Cargo(models.Model):
    """
    La función que cumple una persona, y que decide con qué ítems se la mide.

    El perfil de usuario ya tiene un campo ``cargo`` de texto, heredado de la
    entrega anterior, que sirve para mostrarlo en pantalla. Este modelo es
    otra cosa: es la entidad que se asocia a ítems y metas. Se agregan por
    separado para no romper lo que la entrega anterior ya usa.
    """

    codigo = models.CharField(
        "código", max_length=10, unique=True,
        help_text="Identificador corto e irrepetible, por ejemplo CAR-01.",
    )
    nombre = models.CharField(max_length=80, unique=True)
    descripcion = models.TextField(
        "descripción", blank=True,
        help_text="Qué hace quien ocupa el cargo y con qué se le mide.",
    )
    activo = models.BooleanField(default=True)
    creada = models.DateField("creado el", auto_now_add=True)
    desactivada = models.DateField("desactivado el", null=True, blank=True)

    class Meta:
        verbose_name = "cargo"
        verbose_name_plural = "cargos"
        ordering = ["codigo"]

    def __str__(self):
        return f"{self.codigo} — {self.nombre}"

    def motivo_bloqueo(self):
        cuantos = self.perfiles.filter(activo=True).count()
        if cuantos:
            return (
                f"Tiene {cuantos} "
                f"{'usuario activo' if cuantos == 1 else 'usuarios activos'}. "
                "Reasígnalos a otro cargo antes de desactivarlo."
            )
        return ""


class MetaPeriodo(models.Model):
    """
    Cuánto se le exige a un cargo en un ítem, dentro de un período.

    Es el cruce de las tres cosas que definen una meta. Al cerrarse el
    período, estas filas quedan como el registro de con qué reglas se midió:
    por eso el resultado de un período cerrado no cambia aunque después se
    reconfigure el siguiente.
    """

    periodo = models.ForeignKey(
        Periodo, on_delete=models.PROTECT, related_name="metas",
        verbose_name="período",
    )
    cargo = models.ForeignKey(
        Cargo, on_delete=models.PROTECT, related_name="metas",
        verbose_name="cargo",
    )
    item = models.ForeignKey(
        "catalogos.Item", on_delete=models.PROTECT, related_name="metas",
        verbose_name="ítem",
    )
    meta = models.PositiveIntegerField(
        "meta del período",
        help_text="En la unidad de medida del ítem. Tiene que ser mayor que cero.",
    )
    ponderador = models.PositiveSmallIntegerField(
        help_text="Cuánto pesa este ítem en el resultado del cargo. Entre todos suman 100 %.",
    )
    activo = models.BooleanField(default=True)
    creada = models.DateField("creada el", auto_now_add=True)
    desactivada = models.DateField("desactivada el", null=True, blank=True)

    class Meta:
        verbose_name = "meta del período"
        verbose_name_plural = "metas del período"
        ordering = ["periodo", "cargo", "item"]
        constraints = [
            models.UniqueConstraint(
                fields=["periodo", "cargo", "item"],
                name="una_meta_por_periodo_cargo_item",
            ),
        ]

    def __str__(self):
        return f"{self.item} · {self.cargo.nombre} · {self.periodo.nombre}"

    def clean(self):
        """
        Meta mayor que cero y ponderadores que no se pasen de 100.

        Igual que en el mantenedor de ítems, pasarse se rechaza y quedarse
        corto se permite: mientras se configura el período la suma pasa por
        valores intermedios necesariamente.
        """
        super().clean()
        if self.meta is not None and self.meta < 1:
            raise ValidationError({
                "meta": (
                    "La meta tiene que ser mayor que cero: es el denominador "
                    "del cumplimiento."
                ),
            })

        if self.periodo_id and self.cargo_id and self.ponderador is not None:
            otros = (
                MetaPeriodo.objects
                .filter(periodo_id=self.periodo_id, cargo_id=self.cargo_id, activo=True)
                .exclude(pk=self.pk)
                .aggregate(total=models.Sum("ponderador"))["total"] or 0
            )
            if otros + self.ponderador > 100:
                raise ValidationError({
                    "ponderador": (
                        "Los demás ítems de este cargo ya suman %d %%. Con este "
                        "quedarían en %d %%, y el máximo es 100 %%. Puedes usar "
                        "hasta %d %%." % (otros, otros + self.ponderador, 100 - otros)
                    ),
                })

    def motivo_bloqueo(self):
        if self.periodo.estado == Periodo.Estado.CERRADO:
            return (
                "El período está cerrado: sus metas quedaron congeladas como "
                "registro de con qué reglas se midió. Reábrelo si de verdad "
                "hay que cambiarlas."
            )
        return ""


# =========================================================================
# Actividades y evidencias
# =========================================================================
# Viven en su propio archivo porque son otro asunto —lo que la gente hace y
# cómo se valida—, pero se importan aquí para que Django los registre en
# esta misma aplicación y las migraciones queden juntas.

from gestion.modelos_actividad import Actividad, Evidencia  # noqa: E402,F401

# =========================================================================
# Reglas de cálculo
# =========================================================================
# Los parámetros con que se calcula: tope del aporte, umbrales del semáforo y
# convención de días. Están en la base, y no escritos en el código, porque el
# plan los deja pendientes de aprobación y el requisito RNF-015 exige poder
# cambiarlos desde pantalla.

from gestion.reglas import ReglaCalculo  # noqa: E402,F401

# =========================================================================
# Agenda colectiva
# =========================================================================
# Los compromisos con la comunidad, con su plazo y su historial. Van aparte
# porque son otro asunto que las actividades: la actividad es lo que una
# persona hizo, y el compromiso es una deuda de la delegación que cualquiera
# de sus integrantes puede tener que tomar si el responsable se ausenta.

from gestion.modelos_agenda import CambioCompromiso, Compromiso  # noqa: E402,F401

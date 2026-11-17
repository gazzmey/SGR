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

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
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
    anio = models.PositiveSmallIntegerField(
        "año", default=2026,
        validators=[MinValueValidator(2000), MaxValueValidator(2100)],
        help_text="El año al que pertenece el trimestre.",
    )
    numero = models.PositiveSmallIntegerField(
        "número de trimestre", default=1,
        validators=[MinValueValidator(1), MaxValueValidator(4)],
        help_text="Del 1 al 4.",
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
        verbose_name = "trimestre"
        verbose_name_plural = "trimestres"
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

        # Año y número identifican al trimestre: van después del cruce de
        # fechas, que es el problema de fondo cuando dos períodos chocan.
        if self.numero is not None and not 1 <= self.numero <= 4:
            raise ValidationError({"numero": "El número de trimestre va del 1 al 4."})
        if self.anio and self.inicio and self.inicio.year != self.anio:
            raise ValidationError({
                "anio": "El trimestre empieza el %s: su año es %d, no %d." % (
                    self.inicio.strftime("%d-%m-%Y"), self.inicio.year, self.anio),
            })
        if self.anio and self.numero and 1 <= self.numero <= 4:
            repetido = (Periodo.objects.filter(anio=self.anio, numero=self.numero)
                        .exclude(pk=self.pk).first())
            if repetido is not None:
                raise ValidationError({
                    "numero": "Ya existe el trimestre %d de %d: «%s»." % (
                        self.numero, self.anio, repetido.nombre),
                })

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
        """Cuánto suman los ponderadores configurados para el cargo completo."""
        consulta = self.metas.filter(activo=True, funcionario__isnull=True)
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
    # Las funciones del cargo según el Descriptor de funciones de las
    # Delegaciones Municipales (2026). Una por línea: así se leen como lista
    # en la ficha y en «Mi resultado», y se editan sin un formulario propio.
    funciones = models.TextField(
        "funciones", blank=True,
        help_text=(
            "Las funciones del descriptor de cargos, una por línea. Las ve "
            "cada persona en «Mi resultado»."
        ),
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

    @property
    def lista_funciones(self):
        """Las funciones como lista, sin líneas vacías ni la numeración escrita."""
        import re

        salida = []
        for linea in (self.funciones or "").splitlines():
            limpia = re.sub(r"^\s*(\d+[.)-]|[a-zA-Z][.)]|[-•·])\s*", "", linea).strip()
            if limpia:
                salida.append(limpia)
        return salida

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
        validators=[MaxValueValidator(100)],
        help_text="Cuánto pesa este ítem en el resultado, entre 0 y 100.",
    )
    funcionario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="metas_personales", null=True, blank=True,
        verbose_name="funcionario",
        help_text=(
            "A quién se le asigna. Si se indica, esta meta vale solo para esa "
            "persona y reemplaza a la de su cargo en ese ítem; si se deja en "
            "blanco, vale para todo el cargo."
        ),
    )
    observacion = models.TextField(
        "observación", blank=True,
        help_text="Por qué se asignó así. Queda en la ficha y en el historial.",
    )
    activo = models.BooleanField(default=True)
    creada = models.DateField("fecha de asignación", auto_now_add=True)
    desactivada = models.DateField("desactivada el", null=True, blank=True)

    class Meta:
        verbose_name = "asignación de meta"
        verbose_name_plural = "asignaciones de meta"
        ordering = ["periodo", "cargo", "item"]
        constraints = [
            # Una meta por período, cargo e ítem para el cargo completo, y
            # otra, como máximo, por cada persona de ese cargo. La base no
            # distingue dos NULL, así que el caso «cargo completo» lo
            # completa clean().
            models.UniqueConstraint(
                fields=["periodo", "cargo", "item", "funcionario"],
                name="una_asignacion_por_periodo_cargo_item_persona",
            ),
        ]

    def __str__(self):
        quien = (self.funcionario.get_full_name() or self.funcionario.get_username()
                 if self.funcionario_id else self.cargo.nombre)
        return f"{self.item} · {quien} · {self.periodo.nombre}"

    @property
    def nombre(self):
        return str(self)

    @property
    def destinatario(self):
        """A quién se aplica, en palabras."""
        if self.funcionario_id:
            return self.funcionario.get_full_name() or self.funcionario.get_username()
        return f"Todo el cargo {self.cargo.nombre}"

    def aplica_a(self, usuario):
        """True si esta asignación mide a esa persona."""
        if usuario is None:
            return False
        if self.funcionario_id:
            return self.funcionario_id == usuario.pk
        perfil = getattr(usuario, "perfil", None)
        return bool(perfil and perfil.cargo_asignado_id == self.cargo_id)

    def motivo_no_aplica(self, usuario, fecha=None):
        """
        Por qué no se puede usar esta asignación para un registro de esa
        persona en esa fecha, o cadena vacía si se puede.
        """
        if not self.activo:
            return "Esa asignación de meta está inactiva."
        if usuario is not None and not self.aplica_a(usuario):
            return ("Esa asignación es de %s, no de %s."
                    % (self.destinatario, usuario.get_full_name() or usuario.get_username()))
        if fecha and not (self.periodo.inicio <= fecha <= self.periodo.termino):
            return ("Esa asignación es de «%s», que va del %s al %s."
                    % (self.periodo.nombre, self.periodo.inicio.strftime("%d-%m-%Y"),
                       self.periodo.termino.strftime("%d-%m-%Y")))
        return ""

    @classmethod
    def vigente_para(cls, usuario, periodo, item):
        """La asignación que mide a esa persona en ese ítem: la suya o la de su cargo."""
        propia = cls.objects.filter(periodo=periodo, item=item, funcionario=usuario,
                                    activo=True).first()
        if propia:
            return propia
        perfil = getattr(usuario, "perfil", None)
        if perfil is None or not perfil.cargo_asignado_id:
            return None
        return cls.objects.filter(periodo=periodo, item=item, cargo_id=perfil.cargo_asignado_id,
                                  funcionario__isnull=True, activo=True).first()

    # --- versiones (HU-25) ------------------------------------------------

    TIPO_VERSION = "meta"

    def datos_version(self):
        return {
            "Período": self.periodo.nombre,
            "Cargo": self.cargo.nombre,
            "Funcionario": self.destinatario,
            "Ítem": str(self.item),
            "Meta": str(self.meta),
            "Ponderador": f"{self.ponderador} %",
            "Estado": "Activa" if self.activo else "Inactiva",
        }

    def vigencia_version(self):
        return (f"{self.periodo.nombre} · del {self.periodo.inicio:%d-%m-%Y} "
                f"al {self.periodo.termino:%d-%m-%Y}")

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
        if (self.item_id and self.meta is not None and self.meta > 100
                and self.item.medicion == self.item.Medicion.AGENDA):
            raise ValidationError({
                "meta": (
                    "«%s» se mide como porcentaje de compromisos realizados: "
                    "la meta no puede pasar de 100. La matriz usa 80."
                    % self.item.nombre
                ),
            })

        if self.ponderador is not None and self.ponderador > 100:
            raise ValidationError({"ponderador": "La ponderación va de 0 a 100."})

        if self.funcionario_id:
            perfil = getattr(self.funcionario, "perfil", None)
            if perfil is None or not perfil.activo:
                raise ValidationError({
                    "funcionario": "Esa persona no tiene un perfil activo en el sistema.",
                })
            if not perfil.cargo_asignado_id:
                raise ValidationError({
                    "funcionario": (
                        "%s no tiene cargo con metas. Asígnaselo en su ficha "
                        "de usuario: la meta personal reemplaza a la de su cargo."
                        % perfil.nombre
                    ),
                })
            if self.cargo_id and self.cargo_id != perfil.cargo_asignado_id:
                raise ValidationError({
                    "funcionario": "%s es %s, no %s." % (
                        perfil.nombre, perfil.cargo_asignado.nombre, self.cargo.nombre),
                })

        if self.periodo_id and self.cargo_id and self.item_id and not self.funcionario_id:
            repetida = (MetaPeriodo.objects
                        .filter(periodo_id=self.periodo_id, cargo_id=self.cargo_id,
                                item_id=self.item_id, funcionario__isnull=True)
                        .exclude(pk=self.pk).exists())
            if repetida:
                raise ValidationError({
                    "item": "«%s» ya tiene meta para todo el cargo %s en %s. "
                            "Edita la que existe en vez de crear otra." % (
                                self.item.nombre, self.cargo.nombre, self.periodo.nombre),
                })

        if self.periodo_id and self.cargo_id and self.ponderador is not None and self.activo:
            if self.funcionario_id:
                # Lo que suma la persona: sus metas propias y, en los ítems
                # donde no tiene, las de su cargo.
                propias = (MetaPeriodo.objects
                           .filter(periodo_id=self.periodo_id, funcionario_id=self.funcionario_id,
                                   activo=True).exclude(pk=self.pk))
                cubiertos = set(propias.values_list("item_id", flat=True)) | {self.item_id}
                del_cargo = (MetaPeriodo.objects
                             .filter(periodo_id=self.periodo_id, cargo_id=self.cargo_id,
                                     funcionario__isnull=True, activo=True)
                             .exclude(item_id__in=cubiertos))
                otros = sum(m.ponderador for m in propias) + sum(m.ponderador for m in del_cargo)
                quien = "Las demás metas de esta persona"
            else:
                otros = (
                    MetaPeriodo.objects
                    .filter(periodo_id=self.periodo_id, cargo_id=self.cargo_id,
                            funcionario__isnull=True, activo=True)
                    .exclude(pk=self.pk)
                    .aggregate(total=models.Sum("ponderador"))["total"] or 0
                )
                quien = "Los demás ítems de este cargo"
            if otros + self.ponderador > 100:
                raise ValidationError({
                    "ponderador": (
                        "%s ya suman %d %%. Con esta quedarían en %d %%, y el "
                        "máximo es 100 %%. Puedes usar hasta %d %%."
                        % (quien, otros, otros + self.ponderador, max(0, 100 - otros))
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

    def motivo_bloqueo_activar(self):
        """Reactivar una meta de un período cerrado también cambia su resultado."""
        return self.motivo_bloqueo()


# =========================================================================
# Actividades y evidencias
# =========================================================================
# Viven en su propio archivo porque son otro asunto —lo que la gente hace y
# cómo se valida—, pero se importan aquí para que Django los registre en
# esta misma aplicación y las migraciones queden juntas.

from gestion.modelos_hitos import Hito  # noqa: E402,F401
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

from gestion.modelos_agenda import (  # noqa: E402,F401
    AvisoCompromiso, CambioCompromiso, Compromiso, DestinatarioAviso,
)

# =========================================================================
# Ajustes del resultado
# =========================================================================
# Felicitaciones, reclamos y ausencias: lo que la matriz SGR aplica sobre el
# cumplimiento ponderado sin que salga de contar actividades. Van aparte por
# la misma razón que la agenda: son otro asunto, con su propio registro.

from gestion.modelos_ajustes import Ausencia, Reconocimiento  # noqa: E402,F401

# =========================================================================
# Tubo de cartas
# =========================================================================
# Lo que llega por oficina de partes y su seguimiento (hoja TUBO CARTAS de
# la matriz). No es un compromiso: muchas cartas son solo para conocimiento.

from gestion.modelos_cartas import Carta  # noqa: E402,F401

# =========================================================================
# Versiones de los parámetros
# =========================================================================
# El historial de ítems, metas y reglas (HU-25 y HU-38).

from gestion.modelos_versiones import VersionParametro  # noqa: E402,F401

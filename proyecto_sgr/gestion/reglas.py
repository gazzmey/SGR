"""
Las reglas con que el sistema calcula, y por qué viven en la base y no en el
código.

El sistema tiene que responder cuatro preguntas numéricas: cuánto se avanzó,
cuánto se esperaba a esta fecha, cuánto aporta cada ítem al resultado y de
qué color es el semáforo. Las cuatro dependen de decisiones que **no son
técnicas**:

  · ¿puede un ítem aportar más de lo que se le pidió, o se corta en el 100 %?
  · ¿desde qué porcentaje se considera que un ítem quedó realizado?
  · ¿cuánto puede bajar el avance respecto de lo esperado antes de que el
    semáforo deje de ser ámbar y pase a rojo?
  · ¿los días se cuentan por calendario o solo los hábiles?

El plan de pruebas deja las cuatro **pendientes de aprobación formal**
(sección B3), y el requisito RNF-015 exige poder cambiarlas sin editar
código. De ahí este modelo: las reglas son datos, se configuran desde
pantalla, y mientras nadie las apruebe el sistema las muestra rotuladas como
propuesta, no como norma.

Por qué cada período puede tener su propia regla
------------------------------------------------
Un período cerrado tiene que seguir cuadrando con las reglas con que se
midió. Si las reglas fueran una sola fila global, cambiarlas para el período
siguiente alteraría hacia atrás el resultado del anterior, que es justo lo
que el caso PAR-04 prohíbe. Por eso ``periodo`` admite nulo: la fila sin
período es la regla general, y una fila con período la reemplaza para ese
período y solo para ese.
"""

from django.core.exceptions import ValidationError
from django.db import models


class ReglaCalculo(models.Model):
    """El conjunto de parámetros con que se calcula un período."""

    class Dias(models.TextChoices):
        CALENDARIO_INCLUSIVO = "cal_inc", "Calendario, contando inicio y término"
        CALENDARIO_EXCLUSIVO = "cal_exc", "Calendario, sin contar el término"
        HABILES = "habiles", "Solo días hábiles (de lunes a viernes)"

    nombre = models.CharField(
        max_length=80, unique=True,
        help_text="Cómo se le llama a este conjunto de reglas en los informes.",
    )
    periodo = models.ForeignKey(
        "gestion.Periodo", on_delete=models.PROTECT,
        related_name="reglas", null=True, blank=True,
        verbose_name="período",
        help_text=(
            "Déjalo vacío para que sea la regla general del sistema. "
            "Si eliges un período, estas reglas reemplazan a la general "
            "para ese período únicamente."
        ),
    )

    tope_aporte = models.PositiveSmallIntegerField(
        "tope del cumplimiento", default=100,
        help_text=(
            "Hasta cuánto se cuenta el cumplimiento de un ítem. Con 100, "
            "quien hizo el doble de su meta aporta lo mismo que quien la "
            "cumplió justo. Con 150, se le reconoce hasta una vez y media."
        ),
    )
    umbral_realizado = models.PositiveSmallIntegerField(
        "umbral de ítem realizado", default=80,
        help_text=(
            "Desde qué porcentaje de cumplimiento un ítem se cuenta como "
            "realizado. Se alcanza *desde* este valor: con 80, el 80 % "
            "exacto ya cuenta."
        ),
    )
    umbral_ambar = models.PositiveSmallIntegerField(
        "umbral del ámbar", default=60,
        help_text=(
            "Porcentaje del avance esperado por debajo del cual el semáforo "
            "pasa de ámbar a rojo. Con 60 y un esperado de 50 %, el ámbar "
            "llega hasta el 30 % y bajo eso es rojo."
        ),
    )
    convencion_dias = models.CharField(
        "convención de días", max_length=10,
        choices=Dias.choices, default=Dias.CALENDARIO_INCLUSIVO,
        help_text="Cómo se cuentan los días para el avance esperado.",
    )

    # --- umbrales de las alertas -----------------------------------------
    # Vienen de la maqueta aprobada, que los deja escritos en su panel de
    # «reglas vigentes». Viven aquí y no en el código por la misma razón que
    # los del cálculo: la maqueta dice «solo el administrador puede cambiar
    # umbrales y destinatarios, y cada cambio queda en la auditoría».
    #
    # El sexto umbral que la maqueta nombra —«avance bajo el umbral: menos
    # del 60 % de lo esperado»— no se repite acá a propósito: es el mismo
    # ``umbral_ambar`` de arriba. Separarlos permitiría que el semáforo
    # dijera una cosa y la alerta otra sobre la misma persona.

    dias_aviso_vencimiento = models.PositiveSmallIntegerField(
        "aviso previo al vencimiento", default=7,
        help_text=(
            "Cuántos días antes de vencer se avisa de un compromiso abierto. "
            "Con 7, el aviso aparece una semana antes."
        ),
    )
    dias_sin_registrar = models.PositiveSmallIntegerField(
        "días sin registrar que avisan", default=10,
        help_text=(
            "Desde cuántos días sin registrar actividades se avisa. Quien "
            "lleva dos semanas sin registrar no está midiendo mal: está sin "
            "medir."
        ),
    )
    dias_evidencia_espera = models.PositiveSmallIntegerField(
        "días que una evidencia puede esperar", default=5,
        help_text=(
            "Desde cuántos días esperando decisión se avisa al verificador."
        ),
    )

    aprobada = models.BooleanField(
        "aprobada formalmente", default=False,
        help_text=(
            "Márcalo solo cuando la regla esté aprobada por escrito. Mientras "
            "no lo esté, el sistema la aplica igual pero la rotula como "
            "propuesta en todas las pantallas donde se muestra un resultado."
        ),
    )
    aprobada_por = models.CharField(
        "aprobada por", max_length=120, blank=True,
        help_text="Quién la aprobó y en qué documento. Queda en el informe.",
    )
    observacion = models.TextField(
        "observación", blank=True,
        help_text="De dónde sale cada valor. Es lo que se cita al defenderlos.",
    )

    activo = models.BooleanField(default=True)
    creada = models.DateField("creada el", auto_now_add=True)
    desactivada = models.DateField("desactivada el", null=True, blank=True)

    class Meta:
        verbose_name = "regla de cálculo"
        verbose_name_plural = "reglas de cálculo"
        ordering = ["periodo__inicio", "nombre"]

    def __str__(self):
        if self.periodo_id:
            return f"{self.nombre} ({self.periodo.nombre})"
        return f"{self.nombre} (general)"

    # --- validación ------------------------------------------------------

    def clean(self):
        """
        Una sola regla activa por alcance, y los umbrales dentro de rango.

        «Una sola activa» y no «una sola» a secas: cuando un período se
        cierra, su regla se desactiva pero se conserva, porque es el registro
        de con qué parámetros se midió. Borrarla dejaría ese resultado sin
        explicación.

        Esto se comprueba aquí y no con una restricción de la base a
        propósito: una ``UniqueConstraint`` con ``condition`` se traduce en un
        índice parcial, y MariaDB no los soporta —Django la ignora en
        silencio—. Una comprobación que la base de producción ignora es peor
        que ninguna, porque da la impresión de estar protegiendo algo.
        """
        super().clean()

        # Los errores se juntan y se levantan todos de una vez, en vez de
        # cortar en el primero. Quien está configurando tres umbrales mal
        # quiere verlos los tres, no descubrirlos de uno en uno guardando.
        errores = {}

        if self.activo:
            otra = (
                ReglaCalculo.objects
                .filter(periodo_id=self.periodo_id, activo=True)
                .exclude(pk=self.pk)
                .first()
            )
            if otra is not None and self.periodo_id is None:
                errores["periodo"] = (
                    "Ya existe una regla general activa, «%s». Edita esa, o "
                    "elige un período para que esta regla valga solo ahí."
                    % otra.nombre
                )
            elif otra is not None:
                errores["periodo"] = (
                    "«%s» ya tiene una regla activa: «%s». Edítala, o "
                    "desactívala antes de poner otra en su lugar."
                    % (self.periodo.nombre, otra.nombre)
                )

        if self.tope_aporte is not None and self.tope_aporte < 100:
            errores["tope_aporte"] = (
                "Un tope menor que 100 % castigaría a quien cumple su meta "
                "completa. El mínimo razonable es 100."
            )

        for campo in ("umbral_realizado", "umbral_ambar"):
            valor = getattr(self, campo)
            if valor is not None and not (1 <= valor <= 100):
                errores[campo] = (
                    "Es un porcentaje: tiene que estar entre 1 y 100."
                )

        if self.aprobada and not self.aprobada_por.strip():
            errores["aprobada_por"] = (
                "Si la regla está aprobada, anota quién la aprobó y en qué "
                "documento. Un «aprobado» sin respaldo no sirve de nada "
                "cuando alguien pregunte de dónde salió el número."
            )

        if errores:
            raise ValidationError(errores)

    def motivo_bloqueo(self):
        if self.periodo_id and self.periodo.estado == self.periodo.Estado.CERRADO:
            return (
                "Es la regla con la que se midió un período cerrado. "
                "Desactivarla dejaría ese resultado sin explicación."
            )
        return ""

    # --- lo que el motor le pregunta -------------------------------------

    @property
    def es_propuesta(self):
        """True mientras nadie haya aprobado estas reglas por escrito."""
        return not self.aprobada

    @property
    def rotulo(self):
        """El texto que acompaña a todo resultado calculado con esta regla."""
        if self.aprobada:
            return f"Reglas aprobadas: {self.nombre}"
        return (
            f"Propuesta de cálculo «{self.nombre}», pendiente de aprobación "
            "formal (plan de pruebas, sección B3)."
        )

    def resumen(self):
        """Los cuatro parámetros en una línea, para la ficha y el informe."""
        return (
            f"Tope {self.tope_aporte} % · ítem realizado desde "
            f"{self.umbral_realizado} % · ámbar hasta el {self.umbral_ambar} % "
            f"de lo esperado · {self.get_convencion_dias_display().lower()}"
        )


# --- la regla que corresponde aplicar -------------------------------------

#: Los valores que propone el plan de pruebas. Se usan cuando todavía no hay
#: ninguna regla configurada, para que el sistema calcule igual en vez de
#: caerse, y son los mismos que carga ``cargar_datos_demo``.
#:
#: Cada número sale de un lote del plan, y conviene dejar escrito de cuál:
#:
#:   tope_aporte 100     CAL-A mide sin tope —80 % y 50 % no lo tocan—. CAL-B
#:                       lo sube a 150 para comprobar que es configurable.
#:   umbral_realizado 80 CAL-F: «79,99 % no alcanza; 80 % alcanza».
#:   umbral_ambar 60     CAL-E: con esperado 50 %, el 29,99 % es rojo y el
#:                       30 % es ámbar. Esa frontera está en el 60 % de lo
#:                       esperado, no en el 80 %: con 80 el ámbar partiría en
#:                       40 % y el 30 % del lote daría rojo, contradiciendo
#:                       el resultado verificable del plan.
#:   convencion_dias     CAL-D, calendario inclusivo: del 01-10 al 30-10 son
#:                       30 días y no 29.
#:
#: Los tres umbrales de alertas salen de la maqueta aprobada, que los deja
#: escritos: aviso 7 días antes de vencer, 10 días sin registrar, 5 días de
#: espera de una evidencia.
PROPUESTA_DEL_PLAN = {
    "tope_aporte": 100,
    "umbral_realizado": 80,
    "umbral_ambar": 60,
    "convencion_dias": ReglaCalculo.Dias.CALENDARIO_INCLUSIVO,
    "dias_aviso_vencimiento": 7,
    "dias_sin_registrar": 10,
    "dias_evidencia_espera": 5,
    "aprobada": False,
}


def vigente(periodo=None):
    """
    La regla que corresponde aplicar a ese período.

    Busca en tres niveles, de lo particular a lo general: la regla del
    período, la regla general del sistema, y —si no hay ninguna— un objeto
    **sin guardar** con los valores que propone el plan. Lo último es
    deliberado: el sistema tiene que poder calcular el primer día, antes de
    que nadie haya configurado nada, y tiene que decir que esos valores son
    una propuesta.
    """
    if periodo is not None and getattr(periodo, "pk", None):
        propia = ReglaCalculo.objects.filter(periodo=periodo, activo=True).first()
        if propia is not None:
            return propia

    general = ReglaCalculo.objects.filter(periodo__isnull=True, activo=True).first()
    if general is not None:
        return general

    return ReglaCalculo(nombre="Propuesta del plan", **PROPUESTA_DEL_PLAN)

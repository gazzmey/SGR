"""
El motor de cálculo: avance, cumplimiento, aporte ponderado y semáforo.

Este módulo es el que convierte actividades aprobadas en porcentajes. Tiene
tres propiedades que conviene tener presentes al leerlo, porque explican casi
todas las decisiones:

**No escribe nada.** Ninguna función de aquí guarda en la base. El resultado
se calcula cada vez que se pregunta, a partir de las actividades y de las
metas. Guardar el avance en una columna sería más rápido y traería el
problema clásico: un número almacenado que dejó de corresponder a los datos
que lo produjeron. Al recalcular siempre, el caso EVI-03 —aprobar dos veces
no debe sumar dos veces— se cumple por construcción y no por un candado.

**Cuenta actividades, no evidencias.** El conteo se hace sobre
``Actividad``, sin unirse a ``Evidencia``. Si se uniera, una actividad con
dos evidencias aparecería dos veces y el avance saldría inflado: es
exactamente lo que el caso CAL-01 comprueba con «no duplica por evidencia
adicional».

**Los parámetros llegan de afuera.** El tope del aporte, el umbral de ítem
realizado, el umbral del ámbar y la convención de días no están escritos
aquí: se leen de ``ReglaCalculo``. El plan de pruebas los deja pendientes de
aprobación (sección B3) y el requisito RNF-015 exige cambiarlos sin tocar
código.

Las cuatro fórmulas
-------------------
Para cada ítem con meta en el período, y contando solo sus actividades
**aprobadas**::

    cumplimiento bruto = realizado / meta × 100
    cumplimiento computable = mínimo(bruto, tope)
    aporte = computable × ponderador / 100

Y para la persona completa::

    avance = suma de los aportes de sus ítems
    esperado = días transcurridos / días totales × 100

El semáforo compara esas dos últimas cifras **sin redondearlas**: redondear
antes de comparar movería la frontera, y el caso CAL-05 prueba justo los
valores de frontera.
"""

from dataclasses import dataclass
from datetime import date

from django.db.models import Sum

from gestion import reglas as R
from gestion.modelos_actividad import Actividad
from gestion.models import MetaPeriodo


# =========================================================================
# Días, según la convención vigente
# =========================================================================


def _habiles(desde, hasta):
    """Cuántos lunes-a-viernes hay entre dos fechas, contando ambas."""
    if hasta < desde:
        return 0
    dias = (hasta - desde).days + 1
    semanas, resto = divmod(dias, 7)
    cuenta = semanas * 5
    primero = desde.weekday()
    for i in range(resto):
        if (primero + i) % 7 < 5:
            cuenta += 1
    return cuenta


def dias_entre(desde, hasta, convencion):
    """
    Los días que hay entre dos fechas, según la convención elegida.

    Las tres convenciones vienen del lote CAL-D del plan, que deja la
    decisión pendiente de aprobación. La que está por omisión es la
    inclusiva: del 1 al 30 son 30 días, no 29.
    """
    if not desde or not hasta or hasta < desde:
        return 0
    if convencion == R.ReglaCalculo.Dias.HABILES:
        return _habiles(desde, hasta)
    if convencion == R.ReglaCalculo.Dias.CALENDARIO_EXCLUSIVO:
        return (hasta - desde).days
    return (hasta - desde).days + 1


def dias_del_periodo(periodo, regla):
    return dias_entre(periodo.inicio, periodo.termino, regla.convencion_dias)


def dias_corridos(periodo, regla, al_dia=None):
    """Días ya transcurridos del período, con tope en su duración."""
    hoy = al_dia or date.today()
    if not periodo.inicio or not periodo.termino:
        return 0
    if hoy < periodo.inicio:
        return 0
    if hoy >= periodo.termino:
        return dias_del_periodo(periodo, regla)
    return dias_entre(periodo.inicio, hoy, regla.convencion_dias)


def avance_esperado(periodo, regla, al_dia=None):
    """
    Qué porcentaje del período debería llevarse a una fecha dada.

    Antes del inicio, 0 %. Después del término, 100 %. En el medio, la
    proporción de días. Se devuelve sin redondear: lo usa el semáforo.
    """
    total = dias_del_periodo(periodo, regla)
    if not total:
        return None
    return dias_corridos(periodo, regla, al_dia) * 100 / total


# =========================================================================
# El resultado de un ítem
# =========================================================================


# --- el semáforo, en un solo lugar ---------------------------------------
# Lo usan el ítem, la persona y la delegación. Escrito tres veces, las tres
# fronteras se irían separando con el primer cambio de criterio.

CLASES_CHIP = {"verde": "ok", "ambar": "warn", "rojo": "bad", "sin": "line"}
CLASES_BARRA = {"verde": "ok", "ambar": "warn", "rojo": "bad", "sin": "neu"}


def semaforo_de(valor, esperado, regla):
    """
    El par (clase, texto) que corresponde a un valor frente a lo esperado.

    Las fronteras se comparan **sin redondear**: redondear antes movería el
    límite, y el caso CAL-05 prueba justo los valores de frontera. El texto
    acompaña siempre al color, porque un semáforo que solo informa por color
    no informa a quien no distingue colores.
    """
    if valor is None or esperado is None:
        return ("sin", "Sin referencia")
    if valor >= esperado:
        return ("verde", "Al día")
    if valor >= esperado * regla.umbral_ambar / 100:
        return ("ambar", "Atrasado")
    return ("rojo", "Crítico")


def _barra(valor):
    """El ancho de la barra, acotado entre 0 y 100."""
    if valor is None:
        return 0.0
    return max(0.0, min(100.0, valor))


@dataclass(frozen=True)
class ResultadoItem:
    """Lo que logró una persona en un ítem, y cuánto aporta eso al total."""

    item: object
    meta: int
    ponderador: int
    realizado: int
    cumplimiento_bruto: float | None
    cumplimiento: float | None
    aporte: float
    alcanzado: bool
    meta_invalida: bool
    formula_pendiente: bool
    regla: object = None
    esperado: float | None = None

    # --- lo que la pantalla dibuja --------------------------------------

    @property
    def semaforo(self):
        if self.meta_invalida or self.regla is None:
            return ("sin", "Sin referencia")
        return semaforo_de(self.cumplimiento, self.esperado, self.regla)

    @property
    def semaforo_clase(self):
        return self.semaforo[0]

    @property
    def semaforo_texto(self):
        return self.semaforo[1]

    @property
    def clase_barra(self):
        return CLASES_BARRA[self.semaforo_clase]

    @property
    def clase_chip(self):
        return CLASES_CHIP[self.semaforo_clase]

    @property
    def barra(self):
        return _barra(self.cumplimiento)

    @property
    def topado(self):
        """True si el tope recortó el cumplimiento: hizo más de lo contable."""
        if self.cumplimiento_bruto is None or self.cumplimiento is None:
            return False
        return self.cumplimiento_bruto > self.cumplimiento + 1e-9

    @property
    def nota(self):
        """Por qué este ítem no se puede calcular, o qué hay que saber de él."""
        if self.meta_invalida:
            return (
                "Meta inválida: con meta cero el cumplimiento sería una "
                "división por cero. El ítem no entra en el resultado."
            )
        if self.formula_pendiente:
            return (
                "El ítem se mide en %s y su fórmula no está aprobada. "
                "Mientras tanto se cuenta la cantidad de actividades "
                "aprobadas." % self.item.get_unidad_display().lower()
            )
        if self.topado:
            return (
                "Hizo el %.0f %% de su meta; el tope vigente cuenta hasta "
                "el %.0f %%." % (self.cumplimiento_bruto, self.cumplimiento)
            )
        return ""


def resultado_item(meta_periodo, realizado, regla, esperado=None):
    """Aplica las tres fórmulas a un ítem. No consulta la base."""
    from catalogos.models import Item

    meta = meta_periodo.meta or 0
    ponderador = meta_periodo.ponderador or 0
    item = meta_periodo.item
    pendiente = item.unidad != Item.Unidad.CANTIDAD

    # CAL-06: la meta cero no se calcula, se declara inválida. El modelo ya
    # la rechaza al guardar, pero una fila escrita directamente en la base
    # —o una migración antigua— no debe hacer caer una pantalla.
    if meta <= 0:
        return ResultadoItem(
            item=item, meta=meta, ponderador=ponderador, realizado=realizado,
            cumplimiento_bruto=None, cumplimiento=None, aporte=0.0,
            alcanzado=False, meta_invalida=True, formula_pendiente=pendiente,
            regla=regla, esperado=esperado,
        )

    bruto = realizado * 100 / meta
    computable = min(bruto, float(regla.tope_aporte))
    return ResultadoItem(
        item=item, meta=meta, ponderador=ponderador, realizado=realizado,
        cumplimiento_bruto=bruto,
        cumplimiento=computable,
        aporte=computable * ponderador / 100,
        alcanzado=bruto >= regla.umbral_realizado,
        meta_invalida=False,
        formula_pendiente=pendiente,
        regla=regla, esperado=esperado,
    )


# =========================================================================
# El resultado de una persona
# =========================================================================


@dataclass(frozen=True)
class Resultado:
    """El resultado completo de una persona en un período."""

    periodo: object
    cargo: object
    regla: object
    al_dia: date
    items: tuple
    avance: float | None
    esperado: float | None
    dias_totales: int
    dias_transcurridos: int
    motivo_indefinido: str

    # --- totales ---------------------------------------------------------

    @property
    def definido(self):
        return self.avance is not None

    @property
    def no_realizado(self):
        """
        Lo que falta para el 100 %.

        Se recorta en cero: con un tope mayor que 100 el avance puede pasar
        de 100, y un «no realizado» negativo no significa nada.
        """
        if self.avance is None:
            return None
        return max(0.0, 100.0 - self.avance)

    @property
    def items_medidos(self):
        return sum(1 for r in self.items if not r.meta_invalida)

    @property
    def items_alcanzados(self):
        return sum(1 for r in self.items if r.alcanzado)

    @property
    def porcentaje_items_alcanzados(self):
        """Cuántos de sus ítems llegaron al umbral, en porcentaje.

        Cada ítem cuenta una vez, tenga una actividad aprobada o veinte: es
        lo que el caso CAL-03 pide con «no duplica denominador».
        """
        if not self.items_medidos:
            return None
        return self.items_alcanzados * 100 / self.items_medidos

    @property
    def ponderadores(self):
        return sum(r.ponderador for r in self.items if not r.meta_invalida)

    @property
    def ponderadores_incompletos(self):
        return self.definido and self.ponderadores != 100

    # --- semáforo (CAL-05) ----------------------------------------------

    @property
    def semaforo(self):
        return semaforo_de(self.avance, self.esperado, self.regla)

    @property
    def semaforo_clase(self):
        return self.semaforo[0]

    @property
    def semaforo_texto(self):
        return self.semaforo[1]

    @property
    def clase_barra(self):
        return CLASES_BARRA[self.semaforo_clase]

    @property
    def clase_chip(self):
        return CLASES_CHIP[self.semaforo_clase]

    @property
    def brecha(self):
        """Cuánto le falta —o le sobra— respecto de lo esperado hoy."""
        if self.avance is None or self.esperado is None:
            return None
        return self.avance - self.esperado

    @property
    def brecha_absoluta(self):
        brecha = self.brecha
        return None if brecha is None else abs(brecha)

    @property
    def barra(self):
        return _barra(self.avance)

    @property
    def barra_esperado(self):
        return _barra(self.esperado)

    @property
    def dias_restantes(self):
        return max(0, self.dias_totales - self.dias_transcurridos)

    @property
    def rotulo_reglas(self):
        return self.regla.rotulo


def _aprobadas_por_item(periodo, funcionario=None, delegacion=None, al_dia=None):
    """
    Cuánto acreditan, por ítem, las actividades aprobadas.

    Una sola consulta agregada **sobre ``Actividad``**, sin unirse a
    ``Evidencia``. Esa ausencia de unión es la que importa: si se sumara
    recorriendo evidencias, una actividad con dos evidencias se contaría dos
    veces y el avance saldría inflado. Es justo el error que el caso CAL-01
    busca con «no duplica por evidencia adicional».

    Se suma ``cantidad`` y no se cuentan filas, porque una actividad puede
    acreditar más de una unidad: una mesa territorial con 15 vecinos
    atendidos avanza 15 sobre una meta de 120, no 1.
    """
    consulta = Actividad.objects.filter(
        periodo=periodo, estado=Actividad.Estado.APROBADA,
    )
    if funcionario is not None:
        consulta = consulta.filter(funcionario=funcionario)
    if delegacion is not None:
        consulta = consulta.filter(delegacion=delegacion)
    if al_dia is not None:
        consulta = consulta.filter(fecha__lte=al_dia)

    filas = consulta.values("item_id").annotate(acredita=Sum("cantidad"))
    return {fila["item_id"]: (fila["acredita"] or 0) for fila in filas}


def de_perfil(perfil, periodo, al_dia=None, regla=None):
    """
    El resultado de una persona en un período.

    Devuelve un ``Resultado`` siempre, incluso cuando no se puede calcular:
    en ese caso ``avance`` es None y ``motivo_indefinido`` dice por qué. Es
    deliberado —y es lo que pide CAL-06—: una pantalla tiene que poder
    explicar «no hay metas configuradas» en vez de mostrar un 0 % que se
    confunde con «no hizo nada».
    """
    regla = regla or R.vigente(periodo)
    hoy = al_dia or date.today()

    base = dict(
        periodo=periodo, cargo=None, regla=regla, al_dia=hoy, items=(),
        avance=None, esperado=avance_esperado(periodo, regla, hoy),
        dias_totales=dias_del_periodo(periodo, regla),
        dias_transcurridos=dias_corridos(periodo, regla, hoy),
    )

    cargo = getattr(perfil, "cargo_asignado", None)
    if cargo is None:
        return Resultado(**base, motivo_indefinido=(
            "La persona no tiene cargo asignado, y la meta depende del cargo. "
            "Asígnale uno en su ficha de usuario."
        ))

    metas = list(
        MetaPeriodo.objects
        .filter(periodo=periodo, cargo=cargo, activo=True)
        .select_related("item")
        .order_by("item__codigo")
    )
    base["cargo"] = cargo

    if not metas:
        return Resultado(**base, motivo_indefinido=(
            "No hay metas configuradas para %s en «%s». Sin metas no hay "
            "denominador, y un avance sin denominador no es cero: es "
            "indefinido." % (cargo.nombre, periodo.nombre)
        ))

    aprobadas = _aprobadas_por_item(
        periodo, funcionario=perfil.usuario, al_dia=al_dia,
    )
    filas = tuple(
        resultado_item(meta, aprobadas.get(meta.item_id, 0), regla,
                       esperado=base["esperado"])
        for meta in metas
    )

    validas = [f for f in filas if not f.meta_invalida]
    if not validas:
        base["items"] = filas
        return Resultado(**base, motivo_indefinido=(
            "Todas las metas configuradas son inválidas (meta cero). "
            "Corrígelas antes de medir."
        ))

    base["items"] = filas
    base["avance"] = sum(f.aporte for f in validas)
    return Resultado(**base, motivo_indefinido="")


# =========================================================================
# El resultado de una delegación
# =========================================================================


@dataclass(frozen=True)
class ResultadoDelegacion:
    """El resultado de las personas de una delegación en un período."""

    delegacion: object
    periodo: object
    regla: object
    al_dia: date
    personas: tuple          # ((perfil, Resultado), …)

    @property
    def medidas(self):
        """Las personas cuyo resultado sí se pudo calcular."""
        return tuple((p, r) for p, r in self.personas if r.definido)

    @property
    def sin_medir(self):
        return tuple((p, r) for p, r in self.personas if not r.definido)

    @property
    def promedio(self):
        """
        El promedio simple del avance de las personas medidas.

        Simple y no ponderado por nada: ponderar por cargo, por antigüedad o
        por carga de trabajo son decisiones que nadie ha aprobado, y
        elegirlas en silencio dentro del código es exactamente lo que este
        módulo evita. Si se aprueba otra regla, se agrega a ``ReglaCalculo``.
        """
        medidas = self.medidas
        if not medidas:
            return None
        return sum(r.avance for _, r in medidas) / len(medidas)

    @property
    def esperado(self):
        return avance_esperado(self.periodo, self.regla, self.al_dia)

    @property
    def semaforo(self):
        return semaforo_de(self.promedio, self.esperado, self.regla)

    @property
    def semaforo_clase(self):
        return self.semaforo[0]

    @property
    def semaforo_texto(self):
        return self.semaforo[1]

    @property
    def clase_barra(self):
        return CLASES_BARRA[self.semaforo_clase]

    @property
    def clase_chip(self):
        return CLASES_CHIP[self.semaforo_clase]

    @property
    def barra(self):
        return _barra(self.promedio)

    @property
    def barra_esperado(self):
        return _barra(self.esperado)

    @property
    def dias_totales(self):
        return dias_del_periodo(self.periodo, self.regla)

    @property
    def dias_transcurridos(self):
        return dias_corridos(self.periodo, self.regla, self.al_dia)

    @property
    def actividades_aprobadas(self):
        return sum(
            sum(f.realizado for f in r.items) for _, r in self.personas
        )


# =========================================================================
# El logro colectivo de la agenda (CAL-C y CAL-F)
# =========================================================================


@dataclass(frozen=True)
class LogroAgenda:
    """
    Cuántos compromisos de la agenda están realizados, en porcentaje.

    El lote CAL-C da los números: «10 compromisos distintos, 8 Realizados, 1
    Pendiente y 1 En proceso. Realizado 80 % y no realizado 20 %», con la
    advertencia de «no sumar nuevamente el total de ingresados como si fuera
    otro estado».

    Esa advertencia es contra un error concreto: tratar «ingresado» como una
    categoría aparte y sumarla al denominador además de los abiertos, con lo
    que los porcentajes dejan de cerrar en 100. Acá el denominador son los
    compromisos vivos —realizados más abiertos— y el ingresado es uno de los
    abiertos, no una cuarta cosa.

    Los anulados quedan **fuera** del denominador. Un compromiso anulado dejó
    de ser una deuda, y contarlo como incumplido castigaría a la delegación
    por algo que se dio de baja con su motivo.
    """

    total: int
    realizados: int
    abiertos: int
    anulados: int
    atrasados: int
    realizado: float | None
    no_realizado: float | None
    umbral: int
    estado: str          # "sin_dato" | "no_alcanza" | "alcanza" | "supera"
    texto: str
    motivo: str = ""

    @property
    def alcanza(self):
        return self.estado in ("alcanza", "supera")

    @property
    def clase_chip(self):
        return {"sin_dato": "line", "no_alcanza": "bad",
                "alcanza": "ok", "supera": "ok"}[self.estado]

    @property
    def barra(self):
        return _barra(self.realizado)


def logro_colectivo(realizados, total, umbral):
    """
    La fórmula del logro colectivo, sin base de datos.

    Devuelve ``(realizado, no_realizado, estado, texto)`` envuelto en un
    ``LogroAgenda`` mínimo. Está separada de ``logro_agenda`` por una razón
    práctica: así las fronteras del lote CAL-F —79,99 %, 80 % y 80,01 %— se
    pueden comprobar con tres llamadas y sin inventar 10.000 compromisos en
    la base.

    El umbral se alcanza **desde** su valor: ``>=`` y no ``>``. Es la
    diferencia entre que el 80 % exacto alcance —lo que el plan pide— y que
    quede fuera por un pelo.
    """
    if not total:
        return LogroAgenda(
            total=0, realizados=0, abiertos=0, anulados=0, atrasados=0,
            realizado=None, no_realizado=None, umbral=umbral,
            estado="sin_dato", texto="Sin compromisos",
            motivo=(
                "No hay compromisos, así que no hay denominador. Un 0 % diría "
                "que no se cumplió nada y un 100 % que se cumplió todo; "
                "ninguna de las dos sería cierta."
            ),
        )
    realizado = realizados * 100 / total
    if realizado > umbral:
        estado, texto = "supera", "Supera el umbral"
    elif realizado == umbral:
        estado, texto = "alcanza", "Alcanza el umbral"
    else:
        estado, texto = "no_alcanza", "No alcanza el umbral"
    return LogroAgenda(
        total=total, realizados=realizados, abiertos=total - realizados,
        anulados=0, atrasados=0,
        realizado=realizado,
        # El complemento, no su propia división: así los dos cierran en 100
        # exacto siempre, sin depender de cómo redondee el flotante.
        no_realizado=100.0 - realizado,
        umbral=umbral, estado=estado, texto=texto,
    )


def logro_agenda(periodo, delegacion=None, regla=None, al_dia=None):
    """
    El indicador de realizado / no realizado de la agenda.

    El umbral se alcanza **desde** su valor, no pasándolo: el lote CAL-F lo
    fija con tres cifras —«79,99 % no alcanza; 80 % alcanza; 80,01 %
    supera»— y la diferencia entre ``>=`` y ``>`` es justo lo que separa el
    segundo caso del primero.

    El no realizado se obtiene como complemento del realizado y no con su
    propia división, para que los dos cierren exactamente en 100 % siempre.
    """
    from gestion.modelos_agenda import Compromiso

    regla = regla or R.vigente(periodo)
    hoy = al_dia or date.today()

    consulta = Compromiso.objects.filter(periodo=periodo)
    if delegacion is not None:
        consulta = consulta.filter(delegacion=delegacion)

    realizados = consulta.filter(estado=Compromiso.Estado.REALIZADO).count()
    abiertos = consulta.filter(estado__in=Compromiso.ABIERTOS).count()
    anulados = consulta.filter(estado=Compromiso.Estado.ANULADO).count()
    atrasados = consulta.filter(
        estado__in=Compromiso.ABIERTOS, vencimiento__lt=hoy,
    ).count()

    total = realizados + abiertos

    # La aritmética la hace ``logro_colectivo``, que es la misma fórmula que
    # comprueban las pruebas del lote CAL-F. Acá solo se le agregan los
    # recuentos que la base sí sabe: los anulados que quedaron fuera del
    # denominador y los abiertos que ya vencieron.
    base = logro_colectivo(realizados, total, regla.umbral_realizado)
    return LogroAgenda(
        total=base.total, realizados=base.realizados, abiertos=abiertos,
        anulados=anulados, atrasados=atrasados,
        realizado=base.realizado, no_realizado=base.no_realizado,
        umbral=base.umbral, estado=base.estado, texto=base.texto,
        motivo=base.motivo,
    )


def de_delegacion(delegacion, periodo, al_dia=None, regla=None):
    """El resultado de cada persona activa de la delegación, y su promedio."""
    from organizacion.models import PerfilUsuario

    regla = regla or R.vigente(periodo)
    hoy = al_dia or date.today()

    perfiles = (
        PerfilUsuario.objects
        .filter(delegacion=delegacion, activo=True)
        .select_related("usuario", "cargo_asignado", "rol")
        .order_by("usuario__first_name", "usuario__last_name")
    )
    personas = tuple(
        (perfil, de_perfil(perfil, periodo, al_dia=hoy, regla=regla))
        for perfil in perfiles
    )
    return ResultadoDelegacion(
        delegacion=delegacion, periodo=periodo, regla=regla,
        al_dia=hoy, personas=personas,
    )

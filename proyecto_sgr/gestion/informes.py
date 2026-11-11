"""
Los informes consolidados: la gestión de un período mirada desde arriba.

Los cuatro primeros informes vienen de la maqueta aprobada, que los deja
escritos en su panel de configuración; el quinto, de la hoja TUBO de la
matriz SGR (HU-14):

    Cumplimiento por funcionario   metas, avance y semáforo
    Cumplimiento por delegación    promedios frente al umbral colectivo
    Compromisos de la agenda       pendientes, vencidos y realizados
    Compromisos por colaborador    cuántos tiene cada uno en cada estado
    Tendencia histórica            compara períodos cerrados
    Brechas por cargo e ítem       dónde el cargo no llega a su meta (HU-22)

Por qué este módulo no calcula nada
-----------------------------------
Todo lo que muestra sale de ``gestion.calculo``, el mismo motor que alimenta
el tablero y «Mi resultado». Es deliberado: si el informe recalculara por su
cuenta, bastaría un redondeo distinto para que el papel que se lleva el
delegado diga 66,3 % y la pantalla diga 66,4 %, y a partir de ahí nadie sabe
cuál de los dos creer. Un informe que contradice al sistema es peor que no
tener informe.

Aquí solo se arma la tabla: se eligen las filas, se ordenan, se agrupan y se
les da formato de lectura.

Dos diferencias con la maqueta, y por qué
-----------------------------------------
1. **La columna «Ajustes» llegó con la matriz.** La maqueta la dibujaba con
   0,0 en todas las filas porque no había regla de ajuste. La hoja RECLAMOS
   de la matriz SGR la dio —+10 por felicitación, −20 por reclamo—, y desde
   entonces la columna dice cuánto sumaron y restaron, ya incluido en el
   cumplimiento.

2. **En pantalla las delegaciones son filas de grupo; en el archivo son una
   columna.** Son dos medios distintos. En pantalla, agrupar se lee mejor y
   evita repetir el mismo nombre quince veces. En una planilla, en cambio,
   una fila de grupo es basura: rompe el ordenar y el filtrar, que es
   justamente para lo que alguien abre un Excel. Así que el archivo lleva la
   delegación en cada fila.

Lo que el informe deja por escrito
----------------------------------
Cada informe sale con sus filtros, la fecha y hora en que se generó, quién
lo generó y qué regla de cálculo estaba vigente. Sin eso, dos informes del
mismo período con números distintos son imposibles de explicar; con eso, la
diferencia se ve en el encabezado.
"""

from dataclasses import dataclass
from datetime import date

from gestion import calculo as C
from gestion import reglas as R


# =========================================================================
# Piezas de la tabla
# =========================================================================


def pct(valor):
    """Un porcentaje con coma decimal, como se escribe en español."""
    if valor is None:
        return "—"
    return f"{valor:.1f} %".replace(".", ",")


@dataclass(frozen=True)
class Columna:
    """Una columna del informe. ``derecha`` es para los números."""

    titulo: str
    derecha: bool = False
    ancho: int = 22


@dataclass(frozen=True)
class Celda:
    """
    Una celda ya formateada para leer.

    El formato se resuelve acá y no en la plantilla a propósito: la misma
    celda la lee la pantalla y la escribe el archivo, y si cada uno le diera
    su propio formato terminarían diciendo cosas distintas.
    """

    texto: str
    chip: str = ""        # "ok" | "warn" | "bad" | "line" | ""
    fuerte: bool = False
    enlace: str = ""      # solo en pantalla; el archivo lleva el texto


@dataclass(frozen=True)
class Fila:
    """Una fila de datos, o —si ``grupo`` viene con texto— un encabezado."""

    celdas: tuple = ()
    grupo: str = ""
    delegacion: str = ""   # se usa solo en la exportación


@dataclass(frozen=True)
class Informe:
    """Un informe armado, con todo lo que hace falta para mostrarlo o bajarlo."""

    tipo: str
    titulo: str
    columnas: tuple
    filas: tuple
    pie: tuple = ()           # fila de totales, o vacío
    etiquetas: tuple = ()     # los distintivos del encabezado
    nota: str = ""
    generado: object = None
    quien: str = ""
    regla: object = None
    sin_datos: str = ""
    #: La columna que en pantalla va como fila de grupo y en el archivo
    #: como columna propia: la delegación, salvo en brechas, que es el cargo.
    titulo_grupo: str = "Delegación"

    @property
    def hay_datos(self):
        return any(not f.grupo for f in self.filas)

    @property
    def columnas_derecha(self):
        """
        Los índices de las columnas numéricas.

        La plantilla alinea celda por celda y no tiene cómo preguntarle a la
        columna número N si va a la derecha, así que se le entrega la lista
        hecha. La alternativa —repetir la alineación en cada celda— duplica
        el dato y deja que la cabecera y el cuerpo se desalineen.
        """
        return [i for i, c in enumerate(self.columnas) if c.derecha]

    @property
    def cuantas(self):
        """Cuántas filas de datos trae. Las de grupo no se cuentan."""
        return sum(1 for f in self.filas if not f.grupo)


# =========================================================================
# Los seis informes
# =========================================================================


TIPOS = (
    ("funcionario", "Cumplimiento por funcionario",
     "Metas, avance y semáforo de cada persona"),
    ("delegacion", "Cumplimiento por delegación",
     "Promedios frente al umbral colectivo"),
    ("compromisos", "Compromisos de la agenda",
     "Pendientes, vencidos y realizados"),
    ("responsables", "Compromisos por colaborador",
     "Cuántos tiene cada uno en cada estado"),
    ("tendencia", "Tendencia histórica",
     "Compara los períodos ya cerrados"),
    ("brechas", "Brechas por cargo e ítem",
     "Dónde el cargo no llega a su meta, período a período"),
)

TIPOS_VALIDOS = {clave for clave, _, _ in TIPOS}
POR_OMISION = "funcionario"

NOTA_AJUSTES = (
    "El cumplimiento incluye las felicitaciones (suman) y los reclamos "
    "(restan) registrados en el período, según la regla de cálculo, y nunca "
    "pasa del tope ni baja de cero."
)


def _nombre_cargo(resultado, perfil):
    if resultado.cargo is not None:
        return resultado.cargo.nombre
    asignado = getattr(perfil, "cargo_asignado", None)
    return asignado.nombre if asignado else "Sin cargo asignado"


def _chip_de(clase):
    """Traduce el color del semáforo al distintivo de la hoja de estilos."""
    return {"verde": "ok", "ambar": "warn", "rojo": "bad"}.get(clase, "line")


def _por_funcionario(periodo, delegaciones, item, regla, al_dia):
    """Una fila por persona medida, agrupada por delegación."""
    columnas = (
        Columna("Funcionario", ancho=26),
        Columna("Cargo", ancho=26),
        Columna("Ítems", derecha=True, ancho=10),
        Columna("Ajustes", derecha=True, ancho=10),
        Columna("Cumplimiento", derecha=True, ancho=15),
        Columna("Semáforo", ancho=20),
    )

    filas = []
    suma, cuantos = 0.0, 0

    for delegacion in delegaciones:
        resultado = C.de_delegacion(delegacion, periodo, al_dia=al_dia, regla=regla)
        medidas = []

        for perfil, r in resultado.personas:
            if not r.definido:
                continue

            if item is not None:
                # Con un ítem elegido, la fila deja de ser «cómo va esta
                # persona» y pasa a ser «cómo va esta persona en este ítem».
                suyos = [ri for ri in r.items if ri.item.pk == item.pk]
                if not suyos:
                    continue
                propio = suyos[0]
                valor = propio.cumplimiento
                ajuste = ""
                cuantos_items = 1
                clase = propio.semaforo_clase
                texto = propio.semaforo_texto
            else:
                valor = r.avance
                ajuste = ("%+.0f" % r.ajuste).replace("-", "−") if r.ajuste else "0"
                cuantos_items = len(r.items)
                clase = r.semaforo_clase
                texto = r.semaforo_texto

            if valor is None:
                continue

            medidas.append((valor, Fila(
                celdas=(
                    Celda(perfil.nombre, fuerte=True),
                    Celda(_nombre_cargo(r, perfil)),
                    Celda(str(cuantos_items)),
                    Celda(ajuste or "—"),
                    Celda(pct(valor), fuerte=True),
                    Celda(texto, chip=_chip_de(clase)),
                ),
                delegacion=delegacion.nombre,
            )))
            suma += valor
            cuantos += 1

        if not medidas:
            continue

        # El promedio se calcula con los números, no releyendo el texto que
        # se acaba de formatear: ese viaje de ida y vuelta pierde decimales
        # y produce un total que no cuadra con sus propias filas.
        promedio = sum(v for v, _ in medidas) / len(medidas)
        umbral = regla.umbral_ambar
        relacion = "sobre" if promedio >= umbral else "bajo"
        filas.append(Fila(grupo=(
            "%s · promedio %s · %s el umbral de %d %%"
            % (delegacion.nombre, pct(promedio), relacion, umbral)
        )))
        filas.extend(fila for _, fila in medidas)

    pie = ()
    if cuantos:
        pie = (
            Celda("Total del informe · %d funcionario%s"
                  % (cuantos, "" if cuantos == 1 else "s")),
            Celda(""), Celda(""), Celda(""),
            Celda(pct(suma / cuantos), fuerte=True),
            Celda(""),
        )

    return columnas, tuple(filas), pie, (
        "Cumplimiento = avance aprobado ÷ meta × 100. No se incluyen "
        "actividades anuladas ni evidencias pendientes. " + NOTA_AJUSTES
    ), "Ninguna persona de las delegaciones elegidas tiene metas medibles en este período."


def _por_delegacion(periodo, delegaciones, item, regla, al_dia):
    """Una fila por delegación, con su promedio frente al umbral."""
    columnas = (
        Columna("Delegación", ancho=28),
        Columna("Personas medidas", derecha=True, ancho=17),
        Columna("Sin medir", derecha=True, ancho=11),
        Columna("Promedio", derecha=True, ancho=12),
        Columna("Esperado a la fecha", derecha=True, ancho=19),
        Columna("Semáforo", ancho=20),
    )

    filas, suma, cuantas = [], 0.0, 0
    for delegacion in delegaciones:
        resultado = C.de_delegacion(delegacion, periodo, al_dia=al_dia, regla=regla)
        if resultado.promedio is None:
            filas.append(Fila(celdas=(
                Celda(delegacion.nombre, fuerte=True),
                Celda("0"),
                Celda(str(len(resultado.sin_medir))),
                Celda("—"), Celda("—"),
                Celda("Sin metas definidas", chip="line"),
            ), delegacion=delegacion.nombre))
            continue

        filas.append(Fila(celdas=(
            Celda(delegacion.nombre, fuerte=True),
            Celda(str(len(resultado.medidas))),
            Celda(str(len(resultado.sin_medir))),
            Celda(pct(resultado.promedio), fuerte=True),
            Celda(pct(resultado.esperado)),
            Celda(resultado.semaforo_texto, chip=_chip_de(resultado.semaforo_clase)),
        ), delegacion=delegacion.nombre))
        suma += resultado.promedio
        cuantas += 1

    pie = ()
    if cuantas:
        pie = (
            Celda("Promedio de %d delegación%s"
                  % (cuantas, "" if cuantas == 1 else "es")),
            Celda(""), Celda(""),
            Celda(pct(suma / cuantas), fuerte=True),
            Celda(""), Celda(""),
        )

    return columnas, tuple(filas), pie, (
        "El promedio de una delegación se calcula solo sobre las personas "
        "que tienen metas definidas. Quien no tiene metas no baja el "
        "promedio de los demás. " + NOTA_AJUSTES
    ), "Las delegaciones elegidas no tienen resultados en este período."


ROTULO_ESTADO = {
    "ingresado": ("Ingresado", "line"),
    "pendiente": ("Pendiente", "warn"),
    "en_proceso": ("En proceso", "warn"),
    "realizado": ("Realizado", "ok"),
    "anulado": ("Anulado", "line"),
}


def _compromisos(periodo, delegaciones, item, regla, al_dia):
    """Los compromisos del período, con su plazo y su atraso."""
    from gestion.modelos_agenda import Compromiso

    columnas = (
        Columna("Código", ancho=12),
        Columna("Solicitante", ancho=26),
        Columna("Origen", ancho=10),
        Columna("Responsable", ancho=24),
        Columna("Vence", ancho=12),
        Columna("Estado", ancho=14),
        Columna("Atraso", derecha=True, ancho=10),
    )

    consulta = (
        Compromiso.objects
        .filter(periodo=periodo, delegacion__in=delegaciones)
        .select_related("responsable", "delegacion")
        .order_by("delegacion__nombre", "vencimiento")
    )
    if item is not None:
        consulta = consulta.filter(item=item)

    filas, por_delegacion = [], {}
    for c in consulta:
        por_delegacion.setdefault(c.delegacion.nombre, []).append(c)

    abiertos = vencidos = realizados = 0
    for nombre, grupo in por_delegacion.items():
        atrasados = sum(
            1 for c in grupo
            if c.estado in Compromiso.ABIERTOS and c.vencimiento < al_dia
        )
        filas.append(Fila(grupo=(
            "%s · %d compromiso%s · %d vencido%s sin realizar"
            % (nombre, len(grupo), "" if len(grupo) == 1 else "s",
               atrasados, "" if atrasados == 1 else "s")
        )))

        for c in grupo:
            rotulo, chip = ROTULO_ESTADO.get(c.estado, (c.get_estado_display(), "line"))

            if c.cerrado:
                dias = c.dias_de_atraso or 0
                atraso = f"{dias} d" if dias else "en plazo"
            elif c.vencimiento < al_dia:
                atraso = "%d d" % (al_dia - c.vencimiento).days
            else:
                atraso = "—"

            if c.estado in Compromiso.ABIERTOS:
                abiertos += 1
                if c.vencimiento < al_dia:
                    vencidos += 1
            elif c.estado == Compromiso.Estado.REALIZADO:
                realizados += 1

            filas.append(Fila(celdas=(
                Celda(c.codigo, fuerte=True),
                Celda(c.solicitante),
                Celda({"interno": "INT", "externo": "EXT"}.get(c.origen, "—")),
                Celda(c.responsable.get_full_name() or c.responsable.get_username()),
                Celda(c.vencimiento.strftime("%d-%m-%Y")),
                Celda(rotulo, chip=chip),
                Celda(atraso),
            ), delegacion=nombre))

    total = abiertos + realizados
    pie = ()
    if filas:
        pie = (
            Celda("%d abierto%s · %d vencido%s · %d realizado%s"
                  % (abiertos, "" if abiertos == 1 else "s",
                     vencidos, "" if vencidos == 1 else "s",
                     realizados, "" if realizados == 1 else "s")),
            Celda(""), Celda(""), Celda(""), Celda(""), Celda(""),
            Celda("%d" % total),
        )

    return columnas, tuple(filas), pie, (
        "El atraso de un compromiso cerrado es el que se guardó al cerrarlo "
        "y no cambia aunque después se modifique la regla de fechas. Los "
        "anulados salen del denominador de la agenda.",
    )[0], "No hay compromisos registrados en este período para las delegaciones elegidas."


def _por_responsable(periodo, delegaciones, item, regla, al_dia):
    """
    Cuántos compromisos tiene cada colaborador en cada estado (HU-14).

    Es el cuadro resumen de la hoja TUBO. El % realizado sale de
    ``calculo.resumen_por_responsable``, el mismo que alimenta el ítem
    «Soluciones de ingresos al tubo»: el informe y el resultado de la persona
    no pueden decir cosas distintas.
    """
    columnas = (
        Columna("Colaborador", ancho=26),
        Columna("Ingresado", derecha=True, ancho=11),
        Columna("Pendiente", derecha=True, ancho=11),
        Columna("En proceso", derecha=True, ancho=11),
        Columna("Realizado", derecha=True, ancho=11),
        Columna("% realizado", derecha=True, ancho=13),
    )
    resumen = C.resumen_por_responsable(periodo, [d.pk for d in delegaciones])

    filas, actual = [], None
    total = {"i": 0, "p": 0, "e": 0, "r": 0}
    for t in resumen:
        if t.delegacion.nombre != actual:
            actual = t.delegacion.nombre
            suyos = [x for x in resumen if x.delegacion.pk == t.delegacion.pk]
            filas.append(Fila(grupo="%s · %d colaborador%s" % (
                actual, len(suyos), "" if len(suyos) == 1 else "es")))
        # El color dice si llega al umbral de realizado de la regla.
        if t.realizado is None:
            chip = "line"
        elif t.realizado >= regla.umbral_realizado:
            chip = "ok"
        else:
            chip = "warn"
        filas.append(Fila(celdas=(
            Celda(t.nombre, fuerte=True),
            Celda(str(t.ingresados)), Celda(str(t.pendientes)),
            Celda(str(t.en_proceso)), Celda(str(t.realizados)),
            Celda(pct(t.realizado), chip=chip),
        ), delegacion=t.delegacion.nombre))
        total["i"] += t.ingresados
        total["p"] += t.pendientes
        total["e"] += t.en_proceso
        total["r"] += t.realizados

    pie = ()
    vigentes = sum(total.values())
    if resumen:
        pie = (
            Celda("Total del informe"),
            Celda(str(total["i"])), Celda(str(total["p"])),
            Celda(str(total["e"])), Celda(str(total["r"])),
            Celda(pct(total["r"] * 100 / vigentes) if vigentes else "—", fuerte=True),
        )
    return columnas, tuple(filas), pie, (
        "%% realizado = realizados ÷ (ingresados + pendientes + en proceso + "
        "realizados). Los anulados quedan fuera. En verde, desde el %d %%: el "
        "umbral de realizado de la regla. Es el número que mide el ítem "
        "«Soluciones de ingresos al tubo» de cada persona." % regla.umbral_realizado
    ), "No hay compromisos en este período para las delegaciones elegidas."


def _tendencia(periodo, delegaciones, item, regla, al_dia):
    """
    Los períodos ya cerrados, para comparar.

    Solo cerrados: el resultado de un período abierto todavía se mueve, y una
    serie histórica donde el último punto cambia cada día no es una serie, es
    una foto mal tomada. El período elegido arriba se muestra igual, aparte y
    marcado como en curso, porque es el que la persona está mirando.
    """
    from gestion.models import Periodo

    columnas = (
        Columna("Período", ancho=26),
        Columna("Delegación", ancho=26),
        Columna("Personas medidas", derecha=True, ancho=17),
        Columna("Promedio", derecha=True, ancho=12),
        Columna("Semáforo", ancho=20),
    )

    cerrados = list(
        Periodo.objects
        .filter(estado=Periodo.Estado.CERRADO)
        .order_by("-inicio")[:8]
    )

    filas = []
    for p in cerrados + ([periodo] if periodo not in cerrados else []):
        en_curso = p.estado != Periodo.Estado.CERRADO
        regla_suya = R.vigente(p)
        medidas = []
        for delegacion in delegaciones:
            r = C.de_delegacion(delegacion, p, regla=regla_suya)
            if r.promedio is None:
                continue
            medidas.append(Fila(celdas=(
                Celda(p.nombre + (" · en curso" if en_curso else ""), fuerte=True),
                Celda(delegacion.nombre),
                Celda(str(len(r.medidas))),
                Celda(pct(r.promedio), fuerte=True),
                Celda(r.semaforo_texto, chip=_chip_de(r.semaforo_clase)),
            ), delegacion=delegacion.nombre))

        if medidas:
            filas.append(Fila(grupo=(
                "%s%s · del %s al %s"
                % (p.nombre, " (en curso, el resultado todavía se mueve)"
                   if en_curso else "",
                   p.inicio.strftime("%d-%m-%Y"), p.termino.strftime("%d-%m-%Y"))
            )))
            filas.extend(medidas)

    from gestion.brechas import diferencias_de_reglas

    distintas = diferencias_de_reglas([R.vigente(p) for p in cerrados])
    aviso = (" Ojo: no todos se midieron con la misma regla (%s)."
             % ", ".join(distintas).lower()) if distintas else ""
    return columnas, tuple(filas), (), (
        "Solo se comparan períodos cerrados, cuyo resultado quedó congelado. "
        "Cada período se calcula con la regla que estaba vigente en él, no "
        "con la de hoy: así la comparación es honesta." + aviso
    ), "Todavía no hay períodos cerrados con los que comparar."


def _brechas(periodo, delegaciones, item, regla, al_dia):
    """
    Cada ítem de cada cargo frente a su meta, en los períodos cerrados (HU-22).

    Una fila por cargo e ítem; una columna por período, con el cumplimiento
    promedio del cargo. El nombre del ítem lleva a la ficha con el detalle
    de cada persona, que es lo que sostiene el promedio.
    """
    from django.urls import reverse

    from gestion import brechas as B

    analisis = B.analizar(periodo, delegaciones, item=item)
    if not analisis.comparable:
        return (), (), (), B.NO_DECIDE, (
            "Hacen falta al menos dos períodos cerrados para ver una "
            "tendencia, y hasta ahora hay %d. Se compara solo lo cerrado: "
            "a mitad de período casi todo está bajo la meta por falta de "
            "tiempo, no de trabajo." % len(analisis.periodos)
        )

    # Lo que decide va primero: en una pantalla angosta los períodos quedan
    # al fondo de la tabla, y la situación y la tendencia siguen a la vista.
    columnas = (
        Columna("Ítem", ancho=34),
        Columna("Situación", ancho=20),
        Columna("Tendencia", ancho=20),
        *(Columna(p.periodo.codigo, derecha=True, ancho=12) for p in analisis.periodos),
        Columna("Cambios de meta", ancho=28),
    )
    base = reverse("gestion:brecha")
    filtro_delegacion = (f"&delegacion={delegaciones[0].pk}"
                         if len(delegaciones) == 1 else "")
    filas = []
    cargo_anterior = None
    for linea in analisis.lineas:
        if linea.cargo.pk != cargo_anterior:
            filas.append(Fila(grupo=linea.cargo.nombre))
            cargo_anterior = linea.cargo.pk
        enlace = (f"{base}?periodo={periodo.pk}&cargo={linea.cargo.pk}"
                  f"&item={linea.item.pk}{filtro_delegacion}")
        filas.append(Fila(celdas=(
            Celda(linea.item.nombre, fuerte=True, enlace=enlace),
            Celda(linea.situacion_texto, chip=linea.situacion_chip),
            Celda(linea.tendencia),
            *(Celda(pct(t.promedio), fuerte=t.brecha) for t in linea.tramos),
            Celda(" · ".join(linea.cambios) or "Sin cambios"),
        ), delegacion=linea.cargo.nombre))

    reglas = "; ".join(f"{p.periodo.codigo} con {p.rotulo_regla}" for p in analisis.periodos)
    nota = (
        "Cumplimiento promedio de las personas del cargo en cada ítem, con la "
        "regla de cada período (%s). Hay brecha cuando el promedio queda bajo "
        "el umbral de ítem realizado de esa regla. %s %s"
        % (reglas, B.advertencia_reglas(analisis), B.NO_DECIDE)
    ).replace("  ", " ")
    etiquetas = (
        "Períodos comparados: " + ", ".join(p.periodo.codigo for p in analisis.periodos),
        "%d con brecha de %d" % (len(analisis.con_brecha), len(analisis.lineas)),
    )
    return columnas, tuple(filas), (), nota, (
        "Ningún cargo tiene metas medidas en los períodos cerrados con los "
        "filtros elegidos."
    ), {"etiquetas": etiquetas, "titulo_grupo": "Cargo"}


CONSTRUCTORES = {
    "funcionario": _por_funcionario,
    "delegacion": _por_delegacion,
    "compromisos": _compromisos,
    "responsables": _por_responsable,
    "tendencia": _tendencia,
    "brechas": _brechas,
}


# =========================================================================
# La función que usa la vista
# =========================================================================


def construir(tipo, periodo, delegaciones, item=None, regla=None,
              al_dia=None, quien=""):
    """
    Arma el informe pedido.

    ``delegaciones`` ya viene acotada por la vista a las que la persona tiene
    autorizadas. Este módulo no decide quién ve qué: si lo decidiera acá,
    habría dos lugares donde se resuelve el alcance y tarde o temprano
    dirían cosas distintas.
    """
    from django.utils import timezone as tz

    tipo = tipo if tipo in TIPOS_VALIDOS else POR_OMISION
    regla = regla or R.vigente(periodo)
    al_dia = al_dia or date.today()
    delegaciones = list(delegaciones)

    armado = CONSTRUCTORES[tipo](periodo, delegaciones, item, regla, al_dia)
    columnas, filas, pie, nota, sin_datos = armado[:5]
    # Un informe puede sumar distintivos propios —el de brechas dice qué
    # períodos comparó, que es parte de lo que el reporte tiene que mostrar—
    # y agrupar por otra cosa que la delegación.
    extra = armado[5] if len(armado) > 5 else {}

    nombre_tipo = next(t for c, t, _ in TIPOS if c == tipo)

    etiquetas = [
        "Delegaciones: " + (
            ", ".join(d.nombre for d in delegaciones[:3])
            + (f" y {len(delegaciones) - 3} más" if len(delegaciones) > 3 else "")
            if delegaciones else "ninguna"
        ),
        "Ítems: " + (item.nombre if item is not None else "todos"),
    ]
    if tipo in ("funcionario", "delegacion", "tendencia", "brechas"):
        etiquetas.append("Solo evidencias aprobadas")
    etiquetas.extend(extra.get("etiquetas", ()))

    return Informe(
        tipo=tipo,
        titulo=f"{nombre_tipo} · {periodo.nombre}",
        columnas=columnas,
        filas=filas,
        pie=pie,
        etiquetas=tuple(etiquetas),
        nota=nota,
        generado=tz.localtime(),
        quien=quien,
        regla=regla,
        sin_datos=sin_datos,
        titulo_grupo=extra.get("titulo_grupo", "Delegación"),
    )


# =========================================================================
# Exportación
# =========================================================================


@dataclass(frozen=True)
class ColumnaExportada:
    """
    Adaptador para ``comun.excel``, que espera columnas con ``valor(fila)``.

    Existe para no tener dos descripciones de la misma tabla. La alternativa
    —escribir las columnas otra vez para el archivo— es exactamente cómo un
    informe y su exportación terminan mostrando cosas distintas.
    """

    titulo: str
    indice: int
    ancho: int = 22

    def valor(self, fila):
        if self.indice < 0:
            return fila.delegacion
        return fila.celdas[self.indice].texto


def para_exportar(informe):
    """
    Las columnas y las filas del informe, en la forma que pide ``comun.excel``.

    Se agrega el grupo —la delegación o, en brechas, el cargo— como primera
    columna y se sueltan las filas de grupo: en una planilla, la agrupación
    visual estorba y lo que sirve es poder ordenar y filtrar por esa columna.
    """
    lleva_grupo = not any(c.titulo == informe.titulo_grupo for c in informe.columnas)

    columnas = []
    if lleva_grupo:
        columnas.append(ColumnaExportada(informe.titulo_grupo, -1, ancho=26))
    columnas += [
        ColumnaExportada(c.titulo, i, ancho=c.ancho)
        for i, c in enumerate(informe.columnas)
    ]

    filas = [f for f in informe.filas if not f.grupo]
    return columnas, filas


def describir_filtros(informe):
    """Una línea con los filtros aplicados, para el encabezado del archivo."""
    return " · ".join(informe.etiquetas)

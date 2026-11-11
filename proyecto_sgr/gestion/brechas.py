"""
Brechas de productividad: cada ítem del cargo, período a período (HU-22).

La pregunta que responde
------------------------
«¿En qué ítems el cargo no está llegando a su meta, y eso viene de antes o es
nuevo?». Para cada cruce de cargo e ítem se toma, en cada período cerrado, el
cumplimiento promedio de las personas de ese cargo, y se compara con el
umbral de «ítem realizado» de la regla de **ese** período. Por debajo del
umbral hay brecha.

Tres reglas que vienen de los criterios de aceptación
-----------------------------------------------------
1. **Cada período con su regla** (criterio 1). Un período cerrado tiene su
   regla congelada desde la HU-25, y ``reglas.vigente(periodo)`` la devuelve.
   Se calcula con ella, no con la de hoy: si el umbral subió de 80 a 90, un
   80 % de hace dos períodos no se convierte en brecha retroactiva.
2. **El detalle que origina el número** (criterio 2). Cada brecha se abre en
   una ficha con las personas, lo realizado y la meta de cada período: el
   promedio no se discute, se revisa.
3. **Sin decisiones automáticas** (criterio 3). El análisis describe; no
   etiqueta personas ni propone medidas de recursos humanos. Por eso la
   unidad es el cargo y no la persona, y la ficha de detalle lo dice.

Cuando los parámetros cambiaron entre los períodos comparados —otra meta,
otro ponderador, otra regla— se advierte en la fila y en el informe (CU-62):
un 60 % sobre una meta de 30 no es lo mismo que un 60 % sobre una de 20.

Como el resto de los informes, este módulo no hace aritmética de
cumplimiento: los números vienen de ``gestion.calculo``.
"""

from dataclasses import dataclass, field

from gestion import calculo as C
from gestion import reglas as R

#: Cuántos períodos cerrados se comparan como máximo. Más que eso no cabe en
#: una fila legible, y la tendencia la deciden los últimos.
MAXIMO_PERIODOS = 4

#: Bajo esta diferencia, en puntos, la tendencia se lee como estable.
ESTABLE = 1.0

#: Campos de la regla que no cambian el cálculo y no se comparan.
_NO_CALCULAN = {"Nombre", "Alcance", "Estado", "Aprobada"}

SITUACIONES = {
    "persistente": ("Brecha persistente", "bad", 0),
    "nueva": ("Brecha nueva", "warn", 1),
    "unica": ("Bajo el umbral", "warn", 2),
    "cerrada": ("Brecha cerrada", "ok", 3),
    "sin": ("Sin brecha", "ok", 4),
}


def _pct(valor):
    return "—" if valor is None else f"{valor:.1f} %".replace(".", ",")


def _puntos(valor):
    signo = "+" if valor > 0 else "−" if valor < 0 else ""
    return f"{signo}{abs(valor):.1f} pts".replace(".", ",")


# =========================================================================
# Las piezas
# =========================================================================


@dataclass
class PeriodoComparado:
    """Un período de la comparación, con la regla con que se midió."""

    periodo: object
    regla: object

    @property
    def version_regla(self):
        return self.regla.version if self.regla.pk else None

    @property
    def rotulo_regla(self):
        if not self.regla.pk:
            return "Propuesta del plan, sin regla guardada"
        return f"«{self.regla.nombre}», versión {self.version_regla}"


@dataclass
class Persona:
    """Lo que una persona del cargo logró en el ítem, en un período."""

    delegacion: object
    perfil: object
    item: object            # calculo.ResultadoItem

    @property
    def nombre(self):
        usuario = self.perfil.usuario
        return usuario.get_full_name() or usuario.get_username()


@dataclass
class EnPeriodo:
    """El cruce cargo-ítem en un período: la meta y cómo le fue al cargo."""

    comparado: PeriodoComparado
    personas: list = field(default_factory=list)

    @property
    def periodo(self):
        return self.comparado.periodo

    @property
    def meta(self):
        return self.personas[0].item.meta if self.personas else None

    @property
    def ponderador(self):
        return self.personas[0].item.ponderador if self.personas else None

    @property
    def umbral(self):
        return self.comparado.regla.umbral_realizado

    @property
    def promedio(self):
        """El cumplimiento promedio del cargo en el ítem, ya con el tope."""
        if not self.personas:
            return None
        return sum(p.item.cumplimiento for p in self.personas) / len(self.personas)

    @property
    def alcanzaron(self):
        return sum(1 for p in self.personas if p.item.alcanzado)

    @property
    def brecha(self):
        return self.promedio is not None and self.promedio < self.umbral

    @property
    def distancia(self):
        """Cuántos puntos le faltan al promedio para el umbral."""
        if self.promedio is None:
            return None
        return max(0.0, self.umbral - self.promedio)


@dataclass
class Linea:
    """Un cargo y un ítem a lo largo de los períodos comparados."""

    cargo: object
    item: object
    tramos: list            # un EnPeriodo por período comparado, en orden

    @property
    def con_datos(self):
        return [t for t in self.tramos if t.personas]

    @property
    def ultimo(self):
        datos = self.con_datos
        return datos[-1] if datos else None

    @property
    def previo(self):
        datos = self.con_datos
        return datos[-2] if len(datos) > 1 else None

    @property
    def diferencia(self):
        if self.ultimo is None or self.previo is None:
            return None
        return self.ultimo.promedio - self.previo.promedio

    @property
    def tendencia(self):
        diferencia = self.diferencia
        if diferencia is None:
            return "Sin período anterior"
        if abs(diferencia) < ESTABLE:
            return "Estable (%s)" % _puntos(diferencia)
        return ("Sube " if diferencia > 0 else "Baja ") + _puntos(diferencia)

    @property
    def situacion(self):
        """La clave de ``SITUACIONES``."""
        ultimo, previo = self.ultimo, self.previo
        if ultimo is None:
            return "sin"
        if previo is None:
            return "unica" if ultimo.brecha else "sin"
        if ultimo.brecha:
            return "persistente" if previo.brecha else "nueva"
        return "cerrada" if previo.brecha else "sin"

    @property
    def situacion_texto(self):
        return SITUACIONES[self.situacion][0]

    @property
    def situacion_chip(self):
        return SITUACIONES[self.situacion][1]

    @property
    def orden(self):
        return SITUACIONES[self.situacion][2]

    @property
    def cambios(self):
        """
        Lo que cambió en la meta del cargo entre los períodos (CU-62).

        Una lista de textos: «Meta 20 → 30», «Ponderador 25 % → 30 %».
        Vacía si los parámetros fueron los mismos.
        """
        datos = self.con_datos
        salida = []
        metas = [t.meta for t in datos]
        if len(set(metas)) > 1:
            salida.append("Meta " + " → ".join(str(m) for m in metas))
        ponderadores = [t.ponderador for t in datos]
        if len(set(ponderadores)) > 1:
            salida.append("Ponderador " + " → ".join(f"{p} %" for p in ponderadores))
        return salida


@dataclass
class Analisis:
    periodos: list          # PeriodoComparado, del más antiguo al más nuevo
    lineas: list
    diferencias_regla: list  # los parámetros de la regla que cambiaron

    @property
    def comparable(self):
        return len(self.periodos) >= 2

    @property
    def con_brecha(self):
        return [l for l in self.lineas if l.situacion in ("persistente", "nueva", "unica")]


# =========================================================================
# El análisis
# =========================================================================


def periodos_a_comparar(ancla, maximo=MAXIMO_PERIODOS):
    """
    Los períodos cerrados hasta el elegido, del más antiguo al más nuevo.

    Solo cerrados: el resultado de uno abierto todavía se mueve, y a mitad
    de período casi todo está «bajo el umbral» porque falta tiempo, no
    trabajo. Si el elegido está abierto, se comparan los cerrados de antes.
    """
    from gestion.models import Periodo

    cerrados = list(
        Periodo.objects
        .filter(estado=Periodo.Estado.CERRADO, inicio__lte=ancla.inicio)
        .order_by("-inicio")[:maximo]
    )
    return list(reversed(cerrados))


def diferencias_de_reglas(reglas):
    """Los parámetros de cálculo que no valen lo mismo en todas las reglas."""
    fotos = [r.datos_version() for r in reglas]
    if len(fotos) < 2:
        return []
    return [
        campo for campo in fotos[0]
        if campo not in _NO_CALCULAN and len({f.get(campo) for f in fotos}) > 1
    ]


def analizar(ancla, delegaciones, item=None, cargo=None):
    """
    Compara, cargo por cargo e ítem por ítem, los períodos cerrados.

    ``delegaciones`` ya viene acotada por la vista al alcance de la persona,
    igual que en los demás informes.
    """
    periodos = [
        PeriodoComparado(periodo=p, regla=R.vigente(p))
        for p in periodos_a_comparar(ancla)
    ]
    lineas = {}
    for indice, comparado in enumerate(periodos):
        for delegacion in delegaciones:
            resultado = C.de_delegacion(delegacion, comparado.periodo,
                                        regla=comparado.regla)
            for perfil, res in resultado.personas:
                if res.cargo is None or (cargo is not None and res.cargo.pk != cargo.pk):
                    continue
                for fila in res.items:
                    if fila.meta_invalida:
                        continue
                    if item is not None and fila.item.pk != item.pk:
                        continue
                    clave = (res.cargo.pk, fila.item.pk)
                    if clave not in lineas:
                        lineas[clave] = Linea(
                            cargo=res.cargo, item=fila.item,
                            tramos=[EnPeriodo(comparado=c) for c in periodos],
                        )
                    lineas[clave].tramos[indice].personas.append(
                        Persona(delegacion=delegacion, perfil=perfil, item=fila))

    ordenadas = sorted(
        lineas.values(),
        key=lambda l: (l.cargo.nombre, l.orden, l.item.codigo),
    )
    return Analisis(
        periodos=periodos,
        lineas=ordenadas,
        diferencias_regla=diferencias_de_reglas([p.regla for p in periodos]),
    )


def advertencia_reglas(analisis):
    """El aviso de CU-62 para la regla, o cadena vacía si fue la misma."""
    if not analisis.diferencias_regla:
        return ""
    return (
        "Ojo: los períodos se midieron con reglas distintas (%s). Cada uno se "
        "calculó con la suya, así que la comparación es justa, pero las "
        "cifras no son intercambiables." % ", ".join(analisis.diferencias_regla).lower()
    )


NO_DECIDE = (
    "Este análisis describe resultados registrados y aprobados. No adopta "
    "decisiones de recursos humanos ni califica a nadie: una brecha es una "
    "pregunta para conversar con el equipo, no una conclusión."
)

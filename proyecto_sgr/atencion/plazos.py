"""
Los tiempos de respuesta de un caso social, tramo por tramo.

Cada tramo va de un hito a otro y tiene un plazo en días, que se lee de la
regla de cálculo. Un tramo puede estar en cinco situaciones:

    a_tiempo    terminó dentro del plazo
    fuera       terminó, pero pasado el plazo
    en_curso    no ha terminado y todavía está dentro del plazo
    vencido     no ha terminado y ya se pasó del plazo
    espera      todavía no empieza, porque falta el hito anterior

Los días se cuentan de calendario, como en la matriz: la columna «DIF
INGRESO PROGRAMADA» es la resta de las dos fechas, sin descontar fines de
semana.

Como el resto del cálculo, nada de esto se guarda: se deduce de las fechas
cada vez que se mira, y si alguien corrige una fecha el plazo se recalcula
solo.
"""

from dataclasses import dataclass
from datetime import date

CHIP = {
    "a_tiempo": "ok",
    "fuera": "bad",
    "en_curso": "line",
    "vencido": "bad",
    "espera": "off",
}

TEXTO = {
    "a_tiempo": "A tiempo",
    "fuera": "Fuera de plazo",
    "en_curso": "En curso",
    "vencido": "Vencido",
    "espera": "Todavía no empieza",
}


@dataclass(frozen=True)
class Tramo:
    clave: str
    nombre: str
    inicio: date | None
    fin: date | None
    plazo: int
    hoy: date

    @property
    def dias(self):
        """Los días que tomó, o los que lleva si no ha terminado."""
        if self.inicio is None:
            return None
        hasta = self.fin or self.hoy
        return (hasta - self.inicio).days

    @property
    def estado(self):
        if self.inicio is None:
            return "espera"
        dias = self.dias
        if self.fin is not None:
            return "a_tiempo" if dias <= self.plazo else "fuera"
        return "en_curso" if dias <= self.plazo else "vencido"

    @property
    def chip(self):
        return CHIP[self.estado]

    @property
    def texto(self):
        return TEXTO[self.estado]

    @property
    def excedido(self):
        return self.estado in ("fuera", "vencido")

    @property
    def detalle(self):
        """«3 de 4 días», «faltan 2 días», «2 días de atraso»."""
        if self.inicio is None:
            return "Falta el paso anterior"
        dias = self.dias
        if dias < 0:
            # Una visita programada para dentro de unos días.
            return "En %d día%s" % (-dias, "" if dias == -1 else "s")
        if self.clave == "visita":
            # Aquí no se mide cuánto tomó, sino cuánto se corrió de lo
            # programado: «sin diferencia» es la meta.
            if self.fin is not None:
                if dias == 0:
                    return "Se hizo el día programado"
                return "Se hizo %d día%s después de lo programado" % (
                    dias, "" if dias == 1 else "s")
            if dias == 0:
                return "Programada para hoy"
            return "Lleva %d día%s de atraso" % (dias, "" if dias == 1 else "s")
        plazo = ("sin diferencia" if self.plazo == 0
                 else "plazo %d día%s" % (self.plazo, "" if self.plazo == 1 else "s"))
        tomo = "%d día%s" % (dias, "" if dias == 1 else "s")
        if self.fin is not None:
            return "Tomó %s · %s" % (tomo, plazo)
        return "Lleva %s · %s" % (tomo, plazo)


def tramos(caso, regla, hoy=None):
    """Los tramos del caso, en el orden en que ocurren."""
    hoy = hoy or date.today()
    salida = []
    if caso.requiere_visita:
        salida.append(Tramo("programar", "Programar la visita",
                            caso.ingreso, caso.visita_programada,
                            regla.plazo_programar_visita, hoy))
        # La visita se mide contra lo programado: una programada para la
        # próxima semana está «en curso» hasta ese día, y desde el día
        # siguiente sin visita está vencida.
        salida.append(Tramo("visita", "Hacer la visita en la fecha programada",
                            caso.visita_programada, caso.visita_realizada,
                            regla.tolerancia_visita, hoy))
        inicio_informe = caso.visita_realizada
    else:
        inicio_informe = caso.ingreso
    salida.append(Tramo("informe", "Entregar el informe",
                        inicio_informe, caso.informe_entregado,
                        regla.plazo_informe, hoy))
    if caso.lleva_beneficio:
        salida.append(Tramo("beneficio", "Entregar el beneficio",
                            caso.informe_entregado, caso.beneficio_entregado,
                            regla.plazo_beneficio, hoy))
    salida.append(Tramo("total", "Del ingreso al cierre",
                        caso.ingreso, caso.cierre,
                        regla.plazo_total_caso, hoy))
    return salida


def situacion(caso, regla, hoy=None):
    """
    (clave, texto, chip) del caso completo.

    Un caso cerrado está «a tiempo» si ningún tramo se pasó; uno abierto
    está «al día» si ninguno está vencido ni terminó fuera de plazo.
    """
    lista = tramos(caso, regla, hoy)
    excedidos = [t for t in lista if t.excedido]
    if caso.cerrado:
        if excedidos:
            return ("cerrado_fuera", "Cerrado fuera de plazo", "warn")
        return ("cerrado_a_tiempo", "Cerrado a tiempo", "ok")
    if any(t.estado == "vencido" for t in lista):
        return ("vencido", "Con un plazo vencido", "bad")
    if excedidos:
        return ("atrasado", "Abierto, con un paso fuera de plazo", "warn")
    return ("al_dia", "Abierto, al día", "line")


def resumen(casos, regla, hoy=None):
    """
    Los tiempos de respuesta de un conjunto de casos (la fila «TIEMPOS DE
    RESPUESTA» de la matriz): por tramo, cuántos terminaron y cuántos a
    tiempo.
    """
    hoy = hoy or date.today()
    por_tramo = {}
    nombres = {}
    abiertos = vencidos = cerrados = a_tiempo = con_devolucion = 0
    duraciones = []
    for caso in casos:
        clave, _, _ = situacion(caso, regla, hoy)
        if caso.cerrado:
            cerrados += 1
            a_tiempo += clave == "cerrado_a_tiempo"
            duraciones.append((caso.cierre - caso.ingreso).days)
        else:
            abiertos += 1
            vencidos += clave == "vencido"
        con_devolucion += caso.devoluciones > 0
        for t in tramos(caso, regla, hoy):
            nombres[t.clave] = t.nombre
            fila = por_tramo.setdefault(t.clave, {"terminados": 0, "a_tiempo": 0, "plazo": t.plazo})
            if t.fin is not None and t.inicio is not None:
                fila["terminados"] += 1
                fila["a_tiempo"] += t.estado == "a_tiempo"
    orden = ["programar", "visita", "informe", "beneficio", "total"]
    filas = []
    for clave in orden:
        if clave not in por_tramo:
            continue
        fila = por_tramo[clave]
        filas.append({
            "nombre": nombres[clave],
            "plazo": fila["plazo"],
            "terminados": fila["terminados"],
            "a_tiempo": fila["a_tiempo"],
            "porcentaje": (fila["a_tiempo"] * 100 / fila["terminados"]
                           if fila["terminados"] else None),
        })
    return {
        "abiertos": abiertos,
        "vencidos": vencidos,
        "cerrados": cerrados,
        "cerrados_a_tiempo": a_tiempo,
        "con_devolucion": con_devolucion,
        "promedio_dias": (sum(duraciones) / len(duraciones)) if duraciones else None,
        "tramos": filas,
    }

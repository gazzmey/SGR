"""
Las alertas de la delegación: qué requiere atención hoy.

Las cinco reglas vienen de la maqueta aprobada, que las deja escritas en su
panel de «reglas vigentes»:

    compromiso por vencer     7 días antes        avisa al responsable
    compromiso vencido        al vencer           avisa al delegado
    avance bajo el umbral     bajo el 60 % de lo esperado
    sin registros             10 días sin registrar
    evidencia sin revisar     5 días en espera    avisa al verificador

Los cuatro umbrales viven en ``ReglaCalculo`` y se configuran desde pantalla.
El del avance bajo **no es un umbral propio**: es el mismo del semáforo, de
modo que la alerta aparece exactamente cuando el semáforo está en rojo. Con
dos umbrales separados, el tablero podría decir «atrasado» mientras la
alerta grita «crítico» sobre la misma persona.

Por qué las alertas no se guardan
---------------------------------
Se calculan cada vez, a partir del estado actual. Una alerta almacenada se
queda desactualizada en cuanto cambia lo que la originó: un compromiso
vencido que se cierra dejaría su aviso colgando hasta que alguien lo borrara
a mano, y un avance que se recupera seguiría apareciendo en rojo.

Lo que sí se guarda es la **revisión**: que alguien miró ese aviso. Por eso
marcar revisada no borra nada —es lo que pide el caso TAB-06 con «la
revisión no elimina el evento original»—: escribe una fila aparte y no toca
el compromiso, la evidencia ni el avance. Si la condición sigue dándose, la
alerta sigue existiendo; solo deja de aparecer entre las pendientes.
"""

from dataclasses import dataclass
from datetime import date

from django.urls import reverse

from comun.models import AlertaRevisada
from gestion import calculo as C
from gestion import reglas as R


def dias(cuantos):
    """«1 día» o «5 días». Escribir «1 días» delata que nadie lo leyó."""
    return f"{cuantos} día" + ("" if cuantos == 1 else "s")


def pct(valor):
    """Un porcentaje con coma decimal, como se escribe en español."""
    return f"{valor:.1f}".replace(".", ",")


@dataclass(frozen=True)
class Alerta:
    """Un aviso calculado, con todo lo que la pantalla necesita mostrar."""

    tipo: str
    clave: str
    titulo: str
    detalle: str
    responsable: str
    desde: date
    url: str
    rotulo_enlace: str
    gravedad: str          # "alta" | "media"

    #: ¿El enlace lleva a una ficha que debe devolver acá al apretar «Volver»?
    #:
    #: Es verdadero solo en las alertas que abren la ficha de un compromiso.
    #: Las que llevan al tablero o a la cola de validación no lo necesitan:
    #: esas son pantallas de lista, no tienen botón «Volver», y arrastrarles
    #: un parámetro que nadie lee deja direcciones que nadie puede explicar.
    vuelve: bool = False

    @property
    def dias(self):
        return (date.today() - self.desde).days

    @property
    def clase_chip(self):
        return "bad" if self.gravedad == "alta" else "warn"


# =========================================================================
# Las cinco reglas
# =========================================================================


def _compromisos(periodo, delegacion, regla, hoy):
    """Compromisos vencidos y por vencer."""
    from gestion.modelos_agenda import Compromiso

    from datetime import timedelta

    avisa_desde = hoy + timedelta(days=regla.dias_aviso_vencimiento)
    abiertos = (
        Compromiso.objects
        .filter(periodo=periodo, delegacion=delegacion,
                estado__in=Compromiso.ABIERTOS)
        .select_related("responsable")
        .order_by("vencimiento")
    )

    salida = []
    for c in abiertos:
        quien = c.responsable.get_full_name() or c.responsable.get_username()
        enlace = reverse("gestion:compromiso_detalle", args=[c.pk])

        if c.vencimiento < hoy:
            atraso = (hoy - c.vencimiento).days
            salida.append(Alerta(
                tipo="compromiso_vencido",
                clave=f"compromiso_vencido:{c.pk}",
                titulo="Compromiso vencido sin realizar",
                detalle=(
                    "%s · %s · venció el %s, hace %s."
                    % (c.codigo, c.solicitante,
                       c.vencimiento.strftime("%d-%m-%Y"), dias(atraso))
                ),
                responsable=quien, desde=c.vencimiento,
                url=enlace, rotulo_enlace="Ver compromiso",
                gravedad="alta", vuelve=True,
            ))
        elif c.vencimiento <= avisa_desde:
            faltan = (c.vencimiento - hoy).days
            salida.append(Alerta(
                tipo="compromiso_por_vencer",
                clave=f"compromiso_por_vencer:{c.pk}",
                titulo="Compromiso próximo a vencer",
                detalle=(
                    "%s · %s · vence el %s%s."
                    % (c.codigo, c.solicitante,
                       c.vencimiento.strftime("%d-%m-%Y"),
                       " (hoy)" if faltan == 0 else f", en {dias(faltan)}")
                ),
                responsable=quien, desde=hoy,
                url=enlace, rotulo_enlace="Ver compromiso",
                gravedad="media", vuelve=True,
            ))
    return salida


def _avance_bajo(resultado, regla):
    """
    Personas cuyo avance está bajo la frontera del semáforo.

    Se usa el semáforo del motor en vez de recalcular la comparación aquí:
    si alguien cambia la regla, el tablero y la alerta se mueven juntos.
    """
    salida = []
    esperado = resultado.esperado
    for perfil, r in resultado.personas:
        if not r.definido or r.semaforo_clase != "rojo":
            continue
        proporcion = (r.avance * 100 / esperado) if esperado else 0
        salida.append(Alerta(
            tipo="avance_bajo",
            clave=f"avance_bajo:{perfil.pk}:{resultado.periodo.pk}",
            titulo="Avance bajo el umbral",
            detalle=(
                "%s lleva %s %%, el %.0f %% de lo esperado a la fecha "
                "(%s %%). El umbral está en el %d %%."
                % (perfil.nombre, pct(r.avance), proporcion, pct(esperado),
                   regla.umbral_ambar)
            ),
            responsable=perfil.nombre, desde=resultado.al_dia,
            url=reverse("gestion:tablero"), rotulo_enlace="Ver resultado",
            gravedad="alta",
        ))
    return salida


def _sin_registros(resultado, uso, regla, hoy):
    """Personas que llevan demasiado tiempo sin registrar nada."""
    salida = []
    for fila in uso["filas"]:
        perfil = fila["perfil"]
        # Quien no tiene metas no está obligado a registrar: avisar de eso
        # sería pedirle que mida algo que nadie le pidió medir.
        resultado_suyo = dict(
            (p.pk, r) for p, r in resultado.personas
        ).get(perfil.pk)
        if resultado_suyo is None or not resultado_suyo.definido:
            continue

        sin = fila["sin_registrar"]
        if fila["ultima"] is None:
            salida.append(Alerta(
                tipo="sin_registros",
                clave=f"sin_registros:{perfil.pk}:{resultado.periodo.pk}",
                titulo="Sin registros en la herramienta",
                detalle=("%s no ha registrado ninguna actividad en el período."
                         % perfil.nombre),
                responsable=perfil.nombre, desde=resultado.periodo.inicio,
                url=reverse("gestion:tablero"), rotulo_enlace="Ver uso",
                gravedad="alta",
            ))
        elif sin is not None and sin >= regla.dias_sin_registrar:
            salida.append(Alerta(
                tipo="sin_registros",
                clave=f"sin_registros:{perfil.pk}:{resultado.periodo.pk}",
                titulo="Sin registros en la herramienta",
                detalle=(
                    "%s no registra actividades desde el %s (%s). "
                    "El umbral es de %s."
                    % (perfil.nombre, fila["ultima"].strftime("%d-%m-%Y"),
                       dias(sin), dias(regla.dias_sin_registrar))
                ),
                responsable=perfil.nombre, desde=fila["ultima"],
                url=reverse("gestion:tablero"), rotulo_enlace="Ver uso",
                gravedad="media",
            ))
    return salida


def _evidencias(periodo, delegacion, regla, hoy):
    """
    Evidencias que llevan demasiado tiempo esperando decisión.

    El corte se compara como **fecha y hora completa**, no con el filtro
    ``creada__date``. No es una preferencia de estilo: con ``USE_TZ``
    activado, Django traduce ``__date`` a
    ``DATE(CONVERT_TZ(creada, 'UTC', 'America/Santiago'))``, y en MariaDB
    ``CONVERT_TZ`` con nombres de zona necesita las tablas ``mysql.time_zone``
    cargadas. En una instalación corriente vienen vacías, la función devuelve
    NULL, la comparación nunca se cumple y la consulta no encuentra nada
    —sin error y sin aviso—.

    Sobre SQLite sí funciona, porque ahí Django hace la conversión por su
    cuenta. Es decir: el defecto es invisible para las comprobaciones
    automatizadas y solo aparece en el motor con el que se entrega. Se
    encontró revisando a mano sobre MariaDB.

    Comparar fecha y hora contra fecha y hora no llama a ``CONVERT_TZ`` y
    funciona igual en los dos motores. De paso, mide lo que dice medir:
    «lleva más de cinco días esperando» son cinco por veinticuatro horas, y
    no «se cargó en una fecha de calendario anterior».
    """
    from datetime import timedelta

    from django.utils import timezone as tz

    from gestion.modelos_actividad import Evidencia

    corte = tz.now() - timedelta(days=regla.dias_evidencia_espera)
    esperando = (
        Evidencia.objects
        .filter(actividad__periodo=periodo,
                actividad__delegacion=delegacion,
                decision=Evidencia.Decision.PENDIENTE,
                anulada=False,
                creada__lte=corte)
        .order_by("creada")
    )
    cuantas = esperando.count()
    if not cuantas:
        return []

    codigos = ", ".join(e.codigo for e in esperando[:4])
    if cuantas > 4:
        codigos += f" y {cuantas - 4} más"
    primera = esperando.first().creada.date()
    return [Alerta(
        tipo="evidencia_sin_revisar",
        clave=f"evidencia_sin_revisar:{delegacion.pk}:{periodo.pk}:{cuantas}",
        titulo="Evidencias esperando validación",
        detalle=(
            "%s %s más de %s sin revisar."
            % (codigos, "lleva" if cuantas == 1 else "llevan",
               dias(regla.dias_evidencia_espera))
        ),
        responsable="Quien valida en la delegación",
        desde=primera,
        url=reverse("gestion:validar"), rotulo_enlace="Ir a validar",
        gravedad="alta",
    )]


# =========================================================================
# La consulta que usa la pantalla
# =========================================================================


ORDEN_GRAVEDAD = {"alta": 0, "media": 1}


def de_delegacion(delegacion, periodo, al_dia=None, regla=None):
    """
    Todas las alertas de una delegación, separadas en activas y revisadas.

    Devuelve también las reglas vigentes, porque la pantalla las muestra: una
    alerta sin su umbral a la vista no se puede discutir.
    """
    from gestion import tablero as T

    if periodo is None or delegacion is None:
        return {"activas": [], "revisadas": [], "regla": regla, "total": 0}

    regla = regla or R.vigente(periodo)
    hoy = al_dia or date.today()

    resultado = C.de_delegacion(delegacion, periodo, al_dia=hoy, regla=regla)
    uso = T.uso_de(resultado, al_dia=hoy)

    todas = []
    todas += _compromisos(periodo, delegacion, regla, hoy)
    todas += _avance_bajo(resultado, regla)
    todas += _sin_registros(resultado, uso, regla, hoy)
    todas += _evidencias(periodo, delegacion, regla, hoy)

    revisadas = {
        r.clave: r for r in AlertaRevisada.objects
        .filter(clave__in=[a.clave for a in todas])
        .select_related("quien")
    }

    activas = [a for a in todas if a.clave not in revisadas]
    activas.sort(key=lambda a: (ORDEN_GRAVEDAD.get(a.gravedad, 9), a.desde))

    # Las revisadas que se muestran son las de esta delegación, estén o no
    # entre las que siguen dándose: el registro de la revisión no desaparece
    # porque la condición se haya resuelto.
    historial = list(
        AlertaRevisada.objects
        .filter(delegacion=delegacion)
        .select_related("quien")[:12]
    )

    return {
        "activas": activas,
        "revisadas": historial,
        "vigentes": [a for a in todas if a.clave in revisadas],
        "regla": regla,
        "total": len(activas),
    }

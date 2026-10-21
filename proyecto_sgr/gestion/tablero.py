"""
Lo que las pantallas de resultado necesitan además del cálculo.

El motor de ``calculo.py`` responde «cuánto». Aquí se arma el resto de lo
que una persona necesita ver para hacer algo con ese número: qué tiene
pendiente, qué pasó últimamente, y —en el tablero— quién lleva cuánto
tiempo sin registrar.

Todo se consulta, nada se guarda. Igual que el motor: el día que cambie una
evidencia, estas pantallas cambian solas.

Sobre el «promedio diario» del lote TAB-02
------------------------------------------
El caso pide el promedio de registros por día «según el denominador
aprobado», y el denominador no está aprobado. Aquí se usa el de días
**transcurridos** del período, no el de días totales: dividir por los días
totales a mitad de período daría siempre la mitad de lo real. Queda rotulado
en pantalla para que se vea cuál se usó.
"""

from datetime import date

from django.db.models import Count, Max
from django.urls import reverse

from gestion import calculo as C
from gestion.modelos_actividad import Actividad, Evidencia
from gestion.models import Periodo


# =========================================================================
# Qué período se está mirando
# =========================================================================


def periodos_visibles():
    """Los períodos que se pueden consultar, del más reciente al más viejo."""
    return Periodo.objects.filter(activo=True).order_by("-inicio")


def periodo_elegido(request):
    """
    El período que corresponde mostrar.

    Manda el parámetro ``?periodo=`` de la dirección, para que la pantalla
    sea enlazable y el cambio de período no dependa de la sesión. Si no
    viene, el abierto; si no hay abierto, el más reciente.
    """
    pedido = request.GET.get("periodo")
    if pedido:
        elegido = periodos_visibles().filter(pk=pedido).first()
        if elegido is not None:
            return elegido
    abierto = periodos_visibles().filter(estado=Periodo.Estado.ABIERTO).first()
    return abierto or periodos_visibles().first()


# =========================================================================
# Lo de una persona
# =========================================================================


def resumen_actividades(perfil, periodo):
    """Cuántas actividades y evidencias tiene, por situación."""
    suyas = Actividad.objects.filter(funcionario=perfil.usuario, periodo=periodo)
    por_estado = dict(
        suyas.values_list("estado").annotate(cuantas=Count("pk"))
    )
    evidencias = Evidencia.objects.filter(
        actividad__funcionario=perfil.usuario, actividad__periodo=periodo,
        anulada=False,
    )
    en_revision = evidencias.filter(
        decision=Evidencia.Decision.PENDIENTE).count()
    a_corregir = evidencias.filter(
        decision=Evidencia.Decision.RECHAZADA).count()
    return {
        "total": suyas.count(),
        "aprobadas": por_estado.get(Actividad.Estado.APROBADA, 0),
        "sin_evidencia": por_estado.get(Actividad.Estado.BORRADOR, 0),
        "pendientes": por_estado.get(Actividad.Estado.PENDIENTE, 0),
        "rechazadas": por_estado.get(Actividad.Estado.RECHAZADA, 0),
        "anuladas": por_estado.get(Actividad.Estado.ANULADA, 0),
        "en_revision": en_revision,
        "a_corregir": a_corregir,
        "por_resolver": en_revision + a_corregir,
    }


def pendientes_de(perfil, periodo, tope=8):
    """
    Lo que esta persona tiene por hacer, de lo más urgente a lo menos.

    Tres cosas, en este orden: lo que le devolvieron para corregir, lo que
    registró y no respaldó, y lo que está esperando decisión. El orden no es
    estético: lo primero depende de ella y bloquea puntaje, lo último no
    depende de ella en absoluto.
    """
    filas = []

    devueltas = (
        Evidencia.objects
        .select_related("actividad", "actividad__item")
        .filter(actividad__funcionario=perfil.usuario,
                actividad__periodo=periodo,
                decision=Evidencia.Decision.RECHAZADA, anulada=False)
        .order_by("-decidida")
    )
    for evidencia in devueltas[:tope]:
        filas.append({
            "clase": "bad",
            "titulo": "Corrección solicitada",
            "detalle": "%s · %s" % (
                evidencia.codigo,
                (evidencia.motivo or "").strip()[:110] or "sin motivo registrado",
            ),
            "url": reverse("gestion:actividad_detalle",
                           args=[evidencia.actividad_id]),
        })

    sin_respaldo = (
        Actividad.objects
        .select_related("item")
        .filter(funcionario=perfil.usuario, periodo=periodo,
                estado=Actividad.Estado.BORRADOR)
        .order_by("-fecha")
    )
    for actividad in sin_respaldo[:tope]:
        filas.append({
            "clase": "",
            "titulo": "Actividad sin evidencia",
            "detalle": "%s · %s · %s" % (
                actividad.codigo, actividad.accion,
                actividad.fecha.strftime("%d-%m-%Y"),
            ),
            "url": reverse("gestion:actividad_detalle", args=[actividad.pk]),
        })

    esperando = (
        Evidencia.objects
        .select_related("actividad")
        .filter(actividad__funcionario=perfil.usuario,
                actividad__periodo=periodo,
                decision=Evidencia.Decision.PENDIENTE, anulada=False)
        .order_by("creada")
    )
    for evidencia in esperando[:tope]:
        filas.append({
            "clase": "info",
            "titulo": "Evidencia en revisión",
            "detalle": "%s · %s" % (evidencia.codigo, evidencia.actividad.accion),
            "url": reverse("gestion:actividad_detalle",
                           args=[evidencia.actividad_id]),
        })

    return filas[:tope]


def recientes_de(perfil, periodo, tope=8):
    """
    Lo último que pasó con sus actividades, en una línea de tiempo.

    Se mezclan dos cosas: lo que la persona hizo —registrar— y lo que le
    hicieron —aprobar, rechazar, anular—. Se ordenan juntas por fecha,
    porque así es como se entiende la historia de una actividad.
    """
    sucesos = []

    for actividad in (
        Actividad.objects.select_related("item")
        .filter(funcionario=perfil.usuario, periodo=periodo)
        .order_by("-registrada")[:tope]
    ):
        sucesos.append({
            "cuando": actividad.registrada,
            "punto": "acc",
            "titulo": "Registraste %s" % actividad.codigo,
            "detalle": actividad.accion,
        })

    decididas = (
        Evidencia.objects
        .select_related("actividad", "verificador")
        .filter(actividad__funcionario=perfil.usuario,
                actividad__periodo=periodo, decidida__isnull=False)
        .order_by("-decidida")[:tope]
    )
    for evidencia in decididas:
        quien = (evidencia.verificador.get_full_name()
                 if evidencia.verificador else "El verificador")
        if evidencia.anulada:
            punto, verbo = "warn", "anuló"
        elif evidencia.decision == Evidencia.Decision.APROBADA:
            punto, verbo = "ok", "aprobó"
        else:
            punto, verbo = "warn", "pidió corregir"
        sucesos.append({
            "cuando": evidencia.decidida,
            "punto": punto,
            "titulo": "%s %s %s" % (quien, verbo, evidencia.codigo),
            "detalle": evidencia.actividad.accion,
        })

    sucesos.sort(key=lambda s: s["cuando"], reverse=True)
    return sucesos[:tope]


# =========================================================================
# Lo de la delegación
# =========================================================================


def uso_de(resultado, al_dia=None):
    """
    Cuánto se está usando el sistema en esa delegación (RF-030, lote TAB-02).

    Cuatro cifras por persona: registros del período, promedio diario,
    último registro y días sin registrar. La última es la que dispara el
    aviso: alguien que lleva dos semanas sin registrar no está midiendo mal,
    está sin medir.
    """
    hoy = al_dia or date.today()
    dias = max(1, C.dias_corridos(resultado.periodo, resultado.regla, hoy))

    usuarios = [perfil.usuario_id for perfil, _ in resultado.personas]
    datos = {
        fila["funcionario_id"]: fila
        for fila in Actividad.objects
        .filter(periodo=resultado.periodo, funcionario_id__in=usuarios)
        .values("funcionario_id")
        .annotate(cuantas=Count("pk"), ultima=Max("fecha"))
    }

    filas = []
    for perfil, _ in resultado.personas:
        fila = datos.get(perfil.usuario_id, {})
        cuantas = fila.get("cuantas", 0)
        ultima = fila.get("ultima")
        filas.append({
            "perfil": perfil,
            "registros": cuantas,
            "promedio": cuantas / dias,
            "ultima": ultima,
            # Se recorta en cero. El modelo ya no admite fechas futuras, pero
            # una fila escrita antes de esa regla —o directamente en la base—
            # haría que esta resta diera negativo, y «−21 días sin registrar»
            # no significa nada. Ante un dato imposible, la pantalla muestra
            # el valor más cercano que sí se entiende y no una rareza.
            "sin_registrar": max(0, (hoy - ultima).days) if ultima else None,
        })
    filas.sort(key=lambda f: (-(f["sin_registrar"] or 0), f["registros"]))
    return {"filas": filas, "dias": dias}


def evidencias_por_revisar(delegacion, periodo):
    """Las que esperan decisión en esa delegación, y cuántas llevan esperando."""
    hoy = date.today()
    consulta = (
        Evidencia.objects
        .filter(actividad__delegacion=delegacion, actividad__periodo=periodo,
                decision=Evidencia.Decision.PENDIENTE, anulada=False)
        .order_by("creada")
    )
    filas = list(consulta[:20])
    antiguas = sum(1 for e in filas if (hoy - e.creada.date()).days >= 5)
    return {"total": consulta.count(), "antiguas": antiguas, "filas": filas}

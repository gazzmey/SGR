"""
La pantalla de informes.

Tres decisiones que conviene tener escritas, porque las tres se pueden
discutir y ninguna es obvia.

**El estado vive en la dirección, no en la sesión.** Tipo, período,
delegación e ítem viajan como ``?tipo=&periodo=&delegacion=&item=``. Así un
informe se puede guardar en favoritos, pegar en un correo o adjuntar a un
acta, y quien lo abra ve exactamente lo mismo. Guardarlo en la sesión haría
que el mismo enlace mostrara cosas distintas según quién lo abra, que es la
peor propiedad que puede tener un informe.

**El alcance se resuelve acá y en un solo lugar.** La lista de delegaciones
sale siempre de ``perfil.delegaciones_visibles()``. Si alguien escribe a
mano el identificador de una delegación que no tiene autorizada, la vista
responde 403 en vez de devolver una lista vacía: una lista vacía se parece
demasiado a «no hay datos» y esconde que hubo un intento de ver algo ajeno.

**El archivo sale de lo mismo que la pantalla.** La exportación vuelve a
llamar a ``informes.construir`` con los mismos parámetros y luego traduce el
resultado. No hay una segunda consulta para el archivo, así que es
imposible que el Excel traiga filas que la pantalla no mostraba —que es
justo lo que pide el caso UX-03: lo exportado es lo filtrado y autorizado,
ni más ni menos—.
"""

from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import redirect, render

from catalogos.models import Item
from comun import permisos as P
from comun.auditoria import registrar
from comun.contexto import delegacion_activa
from comun.excel import csv_de_listado, libro_de_listado
from comun.models import EventoAuditoria
from comun.permisos import redirect_al_login, tiene_permiso
from comun.resultado import anunciar
from gestion import informes as I
from gestion import reglas as R
from gestion import tablero as T
from organizacion.models import Delegacion


def _exigir(request, permiso, mensaje):
    """Devuelve un desvío si falta el permiso, o ``None`` si todo está bien."""
    if not request.user.is_authenticated:
        return redirect_al_login(request)
    if not tiene_permiso(request.user, permiso):
        raise PermissionDenied(mensaje)
    return None


def _delegaciones_permitidas(request):
    perfil = P.perfil_de(request.user)
    if perfil is not None:
        return perfil.delegaciones_visibles()
    return Delegacion.objects.filter(activo=True)


def _alcance(request):
    """
    (permitidas, elegida, delegaciones) del pedido.

    Lo usan el informe y la ficha de una brecha: los dos tienen que decidir
    igual qué delegaciones entran, o el detalle podría mostrar personas que
    el informe no contó.
    """
    permitidas = _delegaciones_permitidas(request).filter(activo=True)
    pedida = (request.GET.get("delegacion") or "").strip()
    elegida = None
    if pedida:
        elegida = permitidas.filter(pk=pedida).first() if pedida.isdigit() else None
        if elegida is None:
            raise PermissionDenied(
                "Esa delegación no está entre las que tu perfil autoriza."
            )
        delegaciones = [elegida]
    else:
        # Sin elección explícita se usan todas las autorizadas. Para quien
        # tiene una sola, es su delegación; para quien tiene varias, el
        # consolidado, que es lo que un informe debería dar por omisión.
        delegaciones = list(permitidas.order_by("nombre"))
        activa = delegacion_activa(request)
        if activa is not None and not delegaciones:
            delegaciones = [activa]
    return permitidas, elegida, delegaciones


def informes(request):
    """Arma el informe pedido, o lo entrega como archivo si lo piden así."""
    desvio = _exigir(request, P.VER_INFORMES,
                     "No tienes permiso para consultar informes.")
    if desvio:
        return desvio

    periodo = T.periodo_elegido(request)
    permitidas, elegida, delegaciones = _alcance(request)

    # --- qué ítem ---------------------------------------------------------
    pedido_item = (request.GET.get("item") or "").strip()
    item = Item.objects.filter(pk=pedido_item).first() if pedido_item else None

    tipo = (request.GET.get("tipo") or I.POR_OMISION).strip()

    comun = {
        "menu": "informes",
        "periodos": T.periodos_visibles(),
        "periodo": periodo,
        "delegaciones_posibles": permitidas.order_by("nombre"),
        "items_posibles": Item.objects.filter(activo=True).order_by("nombre"),
        "tipos": I.TIPOS,
        "tipo": tipo if tipo in I.TIPOS_VALIDOS else I.POR_OMISION,
        "delegacion_elegida": elegida,
        "item_elegido": item,
    }

    if periodo is None:
        return render(request, "gestion/informes.html", {
            **comun, "informe": None,
            "sin_datos": "Todavía no hay un período configurado.",
        })
    if not delegaciones:
        return render(request, "gestion/informes.html", {
            **comun, "informe": None,
            "sin_datos": "Tu perfil no tiene delegaciones autorizadas.",
        })

    quien = request.user.get_full_name() or request.user.get_username()
    informe = I.construir(
        comun["tipo"], periodo, delegaciones, item=item,
        regla=R.vigente(periodo), quien=quien,
    )

    formato = (request.GET.get("export") or "").strip().lower()
    if formato in ("excel", "csv"):
        return _exportar(request, informe, formato)

    return render(request, "gestion/informes.html", {
        **comun, "informe": informe, "sin_datos": "",
    })


def _exportar(request, informe, formato):
    """
    Baja el informe como archivo.

    Queda registrado en la auditoría. No es celo burocrático: un informe de
    cumplimiento lleva el nombre y el rendimiento de personas concretas, y
    cuando sale del sistema deja de estar bajo sus reglas de acceso. Saber
    quién se llevó qué y cuándo es lo mínimo que se le puede pedir a un
    sistema que guarda ese dato.
    """
    if not informe.hay_datos:
        anunciar(request, "No hay nada que exportar",
                 "El informe no devolvió filas con los filtros aplicados.",
                 icono="warning")
        return redirect(request.path + "?" + request.GET.urlencode().replace(
            f"export={formato}", "").strip("&"))

    columnas, filas = I.para_exportar(informe)

    registrar(request, EventoAuditoria.Accion.EXPORTAR,
              entidad="Informe", objeto_texto=informe.titulo,
              despues=f"{informe.cuantas} filas · {formato}",
              detalle=I.describir_filtros(informe))

    comun = dict(
        titulo=informe.titulo,
        filtro=I.describir_filtros(informe),
        columnas=columnas,
        filas=filas,
        archivo="SGR_informe_" + informe.tipo,
    )
    if formato == "csv":
        return csv_de_listado(**comun)
    # En Excel, cada fila con el color de su semáforo, igual que en pantalla.
    return libro_de_listado(**comun, tono_de=lambda fila: fila.tono)


def brecha(request):
    """
    La ficha de una brecha: el detalle que origina el promedio (HU-22).

    Por cada período comparado, la regla con que se midió, la meta del
    cargo y lo que logró cada persona. Mismo permiso y mismo alcance que el
    informe del que se llega.
    """
    from django.shortcuts import get_object_or_404

    from gestion import brechas as B
    from gestion.models import Cargo, MetaPeriodo
    from gestion.versiones import version_de

    desvio = _exigir(request, P.VER_INFORMES,
                     "No tienes permiso para consultar informes.")
    if desvio:
        return desvio

    periodo = T.periodo_elegido(request)
    _, elegida, delegaciones = _alcance(request)
    pedidos = {c: (request.GET.get(c) or "").strip() for c in ("cargo", "item")}
    if not all(v.isdigit() for v in pedidos.values()):
        raise Http404("Falta el cargo o el ítem de la brecha.")
    cargo = get_object_or_404(Cargo, pk=int(pedidos["cargo"]))
    item = get_object_or_404(Item, pk=int(pedidos["item"]))
    if periodo is None:
        raise PermissionDenied("Todavía no hay un período configurado.")

    analisis = B.analizar(periodo, delegaciones, item=item, cargo=cargo)
    linea = analisis.lineas[0] if analisis.lineas else None

    tramos = []
    for indice, comparado in enumerate(analisis.periodos):
        tramo = linea.tramos[indice] if linea else None
        meta = MetaPeriodo.objects.filter(
            periodo=comparado.periodo, cargo=cargo, item=item, activo=True).first()
        tramos.append({
            "comparado": comparado,
            "tramo": tramo,
            "meta": meta,
            "version_meta": version_de(meta) if meta else None,
            "personas": sorted(
                tramo.personas if tramo else [],
                key=lambda p: (p.delegacion.nombre, p.nombre),
            ),
        })

    volver = request.GET.copy()
    for clave in ("cargo", "item"):
        volver.pop(clave, None)
    volver["tipo"] = "brechas"

    return render(request, "gestion/brecha_detalle.html", {
        "menu": "informes",
        "cargo": cargo,
        "item": item,
        "periodo": periodo,
        "analisis": analisis,
        "linea": linea,
        "tramos": list(reversed(tramos)),
        "delegacion_elegida": elegida,
        "delegaciones": delegaciones,
        "advertencia_reglas": B.advertencia_reglas(analisis),
        "no_decide": B.NO_DECIDE,
        "puede_historial": tiene_permiso(request.user, P.CONFIGURAR_PERIODO),
        "volver": volver.urlencode(),
    })

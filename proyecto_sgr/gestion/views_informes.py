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


def informes(request):
    """Arma el informe pedido, o lo entrega como archivo si lo piden así."""
    desvio = _exigir(request, P.VER_INFORMES,
                     "No tienes permiso para consultar informes.")
    if desvio:
        return desvio

    periodo = T.periodo_elegido(request)
    permitidas = _delegaciones_permitidas(request).filter(activo=True)

    # --- qué delegaciones entran ----------------------------------------
    pedida = (request.GET.get("delegacion") or "").strip()
    elegida = None
    if pedida:
        elegida = permitidas.filter(pk=pedida).first()
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

    construir_archivo = csv_de_listado if formato == "csv" else libro_de_listado
    return construir_archivo(
        titulo=informe.titulo,
        filtro=I.describir_filtros(informe),
        columnas=columnas,
        filas=filas,
        archivo="SGR_informe_" + informe.tipo,
    )

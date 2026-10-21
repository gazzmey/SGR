"""
Ingreso de atención ciudadana y consulta de lo registrado en la delegación.

La atención se asocia siempre a la **delegación activa de la sesión** y al
usuario que la registra. Ninguno de los dos viaja en el formulario: si lo
hicieran, bastaría con cambiar un valor enviado a mano para registrar
atenciones a nombre de otra persona o de otra delegación.
"""

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse

from atencion.forms import AtencionForm
from atencion.models import Atencion, Solicitante, limpiar_rut, rut_valido
from catalogos.models import SubAtencion
from comun import envio, permisos as P
from comun.contexto import delegacion_activa
from comun.resultado import anunciar


@login_required
def ingreso(request):
    """Formulario de registro de una atención."""
    if not P.tiene_permiso(request.user, P.REGISTRAR_ATENCION):
        raise PermissionDenied("No tienes permiso para registrar atenciones.")

    activa = delegacion_activa(request)

    formulario = AtencionForm(
        request.POST or None,
        delegacion=activa,
        funcionario=request.user,
    )

    if request.method == "POST":
        # La ficha se gasta antes de validar: si el formulario trae errores,
        # la pantalla se dibuja de nuevo con una ficha nueva, y el envío
        # repetido de este POST ya no encontrará la suya.
        primera_vez = envio.consumir(request)

        if not primera_vez:
            anunciar(
                request,
                "Ese envío ya se había registrado",
                "El formulario se envió dos veces. No se creó una segunda "
                "atención: la primera quedó guardada.",
                icono="warning",
                acciones=[
                    ("Ver las registradas", reverse("atencion:registradas")),
                    ("Registrar otra", reverse("atencion:ingreso")),
                ],
            )
            return redirect("atencion:registradas")

        if formulario.is_valid():
            atencion = formulario.save()
            anunciar(
                request,
                "Atención registrada",
                "Nº %d · %s%s. Queda asociada a %s, a tu nombre y con la "
                "fecha y hora del servidor." % (
                    atencion.pk,
                    formulario.solicitante.nombre,
                    " (ficha nueva)" if formulario.era_nuevo else "",
                    activa.nombre,
                ),
                acciones=[
                    ("Registrar otra", reverse("atencion:ingreso")),
                    ("Ver la registrada", reverse("atencion:registradas")),
                ],
            )
            return redirect("atencion:registradas")

    return render(request, "atencion/ingreso.html", {
        "menu": "atencion",
        "form": formulario,
        "activa": activa,
        "ficha_envio": envio.nueva_ficha(request),
        "campo_envio": envio.CAMPO,
        "por_tipo": _subatenciones_por_tipo(),
        "ultimas": (
            Atencion.objects
            .filter(delegacion=activa)
            .select_related("solicitante", "subatencion")[:5]
            if activa else []
        ),
    })


def _subatenciones_por_tipo():
    """
    Las subatenciones agrupadas por tipo, para el selector dependiente.

    Van en la página, no en una petición por cada cambio de tipo: son pocas
    y así el selector responde al instante. La validación de que la
    subatención corresponda al tipo la hace el servidor de todas formas.

    Se devuelve el diccionario, no su texto JSON: la plantilla lo publica con
    el filtro ``json_script``, que escapa el contenido. Escribir el JSON a
    mano dentro de la página dejaría la puerta abierta a que un nombre con
    caracteres raros rompiera la etiqueta.
    """
    agrupadas = {}
    consulta = (
        SubAtencion.objects
        .filter(activo=True, tipo_atencion__activo=True)
        .order_by("tipo_atencion__codigo", "codigo")
    )
    for sub in consulta:
        agrupadas.setdefault(str(sub.tipo_atencion_id), []).append({
            "id": sub.pk,
            "nombre": sub.nombre,
            "documento": bool(sub.documento),
        })
    return agrupadas


@login_required
def registradas(request):
    """Lo registrado en la delegación activa. Pantalla de consulta."""
    if not P.tiene_permiso(request.user, P.REGISTRAR_ATENCION):
        raise PermissionDenied("No tienes permiso para ver las atenciones.")

    activa = delegacion_activa(request)
    atenciones = (
        Atencion.objects
        .filter(delegacion=activa)
        .select_related("solicitante", "subatencion", "subatencion__tipo_atencion", "funcionario")
        if activa else Atencion.objects.none()
    )

    termino = (request.GET.get("q") or "").strip()
    if termino:
        from django.db.models import Q

        atenciones = atenciones.filter(
            Q(solicitante__nombre__icontains=termino)
            | Q(solicitante__rut__icontains=limpiar_rut(termino))
            | Q(subatencion__nombre__icontains=termino)
            | Q(detalle__icontains=termino)
        )

    return render(request, "atencion/registradas.html", {
        "menu": "atencion",
        "activa": activa,
        "atenciones": atenciones[:100],
        "total": atenciones.count(),
        "termino": termino,
    })


@login_required
def buscar_solicitante(request):
    """
    Busca una ficha por RUT y la devuelve como JSON.

    Lo usa la pantalla de ingreso para completar los datos de alguien que ya
    fue atendido. Devuelve solo lo que el formulario necesita rellenar, y
    nunca dice más de lo que ya se le preguntó: hay que escribir el RUT
    completo y correcto para obtener algo.
    """
    if not P.tiene_permiso(request.user, P.REGISTRAR_ATENCION):
        raise PermissionDenied("No tienes permiso para consultar solicitantes.")

    rut = limpiar_rut(request.GET.get("rut"))
    if not rut_valido(rut):
        return JsonResponse({"valido": False, "encontrado": False})

    solicitante = Solicitante.objects.filter(rut=rut).first()
    if solicitante is None:
        return JsonResponse({"valido": True, "encontrado": False})

    return JsonResponse({
        "valido": True,
        "encontrado": True,
        "nombre": solicitante.nombre,
        "telefono": solicitante.telefono,
        "territorio": solicitante.territorio,
        "atenciones": solicitante.atenciones.count(),
    })

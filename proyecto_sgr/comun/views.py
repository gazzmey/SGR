"""
Vistas transversales: el panel de entrada y el cambio de delegación activa.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from atencion.models import Atencion
from catalogos.models import Item, SubAtencion, TipoAtencion
from comun import permisos as P
from comun.contexto import CLAVE_DELEGACION, delegacion_activa
from comun.navegacion import desde_formulario
from organizacion.models import Delegacion, PerfilUsuario, Rol


@login_required
def panel(request):
    """
    Pantalla de entrada. Resume lo que hay y lleva a cada mantenedor.

    Los accesos que se muestran dependen del rol: alguien sin el permiso de
    gestionar catálogos no ve esas tarjetas. Y si igual escribe la dirección
    a mano, la vista de destino lo rechaza.
    """
    activa = delegacion_activa(request)

    tarjetas = []
    if P.tiene_permiso(request.user, P.GESTIONAR_USUARIO):
        tarjetas += [
            {
                "titulo": "Delegaciones",
                "cuenta": Delegacion.objects.filter(activo=True).count(),
                "pie": "activas de %d" % Delegacion.objects.count(),
                "url": reverse("organizacion:delegaciones"),
            },
            {
                "titulo": "Usuarios",
                "cuenta": PerfilUsuario.objects.filter(activo=True).count(),
                "pie": "con acceso al sistema",
                "url": reverse("organizacion:usuarios"),
            },
            {
                "titulo": "Roles",
                "cuenta": Rol.objects.filter(activo=True).count(),
                "pie": "definidos y en uso",
                "url": reverse("organizacion:roles"),
            },
        ]
    if P.tiene_permiso(request.user, P.GESTIONAR_CATALOGO):
        tarjetas += [
            {
                "titulo": "Ítems y metas",
                "cuenta": Item.objects.filter(activo=True).count(),
                "pie": "medibles este período",
                "url": reverse("catalogos:items"),
            },
            {
                "titulo": "Tipos de atención",
                "cuenta": TipoAtencion.objects.filter(activo=True).count(),
                "pie": "con %d subatenciones" % SubAtencion.objects.filter(activo=True).count(),
                "url": reverse("catalogos:tipos"),
            },
        ]
    if P.tiene_permiso(request.user, P.REGISTRAR_ATENCION):
        tarjetas.append({
            "titulo": "Atenciones",
            "cuenta": Atencion.objects.filter(delegacion=activa).count() if activa else 0,
            "pie": "registradas en esta delegación",
            "url": reverse("atencion:ingreso"),
        })

    return render(request, "comun/panel.html", {
        "menu": "panel",
        "tarjetas": tarjetas,
    })


@require_POST
@login_required
def cambiar_delegacion(request):
    """
    Cambia la delegación activa de la sesión.

    Se comprueba contra las delegaciones que el perfil autoriza. Aceptar sin
    comprobar sería un agujero: bastaría con enviar otro identificador para
    ver datos ajenos.

    Lo mismo vale para el ``volver``, y por eso pasa por
    ``comun.navegacion``. Este selector vive en la barra de **todas** las
    pantallas y su campo oculto se rellena con la dirección actual: si
    alguien abre el sistema con una dirección que trae basura en la consulta,
    esa basura queda escrita en el formulario y llega hasta acá. Validarla al
    recibirla es lo que corta la cadena.
    """
    perfil = P.perfil_de(request.user)
    elegida = request.POST.get("delegacion")
    volver = desde_formulario(request, "comun:panel")

    if perfil is None:
        if request.user.is_superuser and Delegacion.objects.filter(pk=elegida).exists():
            request.session[CLAVE_DELEGACION] = int(elegida)
        return redirect(volver)

    permitida = perfil.delegaciones_visibles().filter(pk=elegida).first()
    if not permitida:
        messages.error(
            request,
            "Esa delegación no está entre las que tu perfil autoriza.",
        )
        return redirect(volver)

    request.session[CLAVE_DELEGACION] = permitida.pk
    messages.success(
        request,
        f"Delegación activa: {permitida.nombre}. "
        "Los listados y los registros nuevos quedan en "
        f"{permitida.codigo}.",
    )
    return redirect(volver)


def sin_permiso(request, exception=None):
    """Página del error 403, con la identidad del sistema."""
    return render(request, "comun/403.html", {"detalle": str(exception or "")}, status=403)


def no_encontrado(request, exception=None):
    return render(request, "comun/404.html", status=404)

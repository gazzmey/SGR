"""
Vistas transversales: el panel de entrada y el cambio de delegación activa.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from comun import permisos as P
from comun.contexto import CLAVE_DELEGACION, delegacion_activa
from comun.navegacion import desde_formulario
from organizacion.models import Delegacion


@login_required
def panel(request):
    """
    Pantalla de entrada: lo que hay que atender, el avance y los módulos.

    Lo que se muestra depende del rol, con las mismas condiciones que el
    menú. Si alguien escribe a mano la dirección de un módulo que no tiene,
    la vista de destino lo rechaza igual. Cómo se arma cada parte está en
    ``comun/modulos.py``.
    """
    from comun.modulos import panel_de

    return render(request, "comun/panel.html", {
        "menu": "panel",
        **panel_de(request, delegacion_activa(request)),
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

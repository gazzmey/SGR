"""
Lo que la plantilla base necesita saber en todas las pantallas.

La cabecera muestra la delegación activa, el nombre y el rol de quien entró,
y el menú lateral muestra solo los módulos que el rol habilita. Eso se
calcula una vez por petición y queda disponible en todas las plantillas.

La delegación activa vive en la sesión del servidor, no en el navegador. Es
deliberado: lo que el usuario elige en la cabecera decide a qué datos accede,
y una decisión así no puede quedar en manos del cliente.
"""

from comun import permisos as P
from comun.resultado import tomar as tomar_resultado

CLAVE_DELEGACION = "sgr_delegacion"


def delegacion_activa(request):
    """
    La delegación con la que está trabajando quien entró.

    Siempre se comprueba contra las delegaciones que su perfil autoriza: si
    en la sesión quedó una que ya no le corresponde —porque le cambiaron el
    rol, o porque la desactivaron— se descarta y vuelve a la suya.
    """
    perfil = P.perfil_de(request.user)
    if perfil is None:
        return None

    permitidas = perfil.delegaciones_visibles()
    elegida = request.session.get(CLAVE_DELEGACION)
    if elegida:
        encontrada = permitidas.filter(pk=elegida).first()
        if encontrada:
            return encontrada
        request.session.pop(CLAVE_DELEGACION, None)

    return permitidas.first() or perfil.delegacion


def sesion_sgr(request):
    """Procesador de contexto declarado en settings.TEMPLATES."""
    perfil = P.perfil_de(request.user)
    activa = delegacion_activa(request)

    if perfil is not None:
        disponibles = list(perfil.delegaciones_visibles())
    elif getattr(request.user, "is_superuser", False):
        from organizacion.models import Delegacion

        disponibles = list(Delegacion.objects.filter(activo=True))
        activa = activa or (disponibles[0] if disponibles else None)
    else:
        disponibles = []

    return {
        "sgr_perfil": perfil,
        "sgr_delegacion": activa,
        "sgr_delegaciones": disponibles,
        "sgr_puede_cambiar_delegacion": len(disponibles) > 1,
        "sgr_permisos": _permisos_de(request.user),
        # El resultado de la última operación, que se consume al mostrarlo.
        "sgr_resultado": tomar_resultado(request),
    }


def _permisos_de(usuario):
    """
    Diccionario clave → True/False para usar en las plantillas.

    En la plantilla se escribe ``{% if sgr_permisos.gestionar_usuario %}``,
    que se lee bien. Esconder una opción del menú es cortesía, no seguridad:
    la vista vuelve a comprobar el permiso igual.
    """
    if getattr(usuario, "is_superuser", False):
        return {clave: True for clave in P.CLAVES}
    perfil = P.perfil_de(usuario)
    if perfil is None:
        return {clave: False for clave in P.CLAVES}
    propios = set(perfil.rol.permisos or [])
    return {clave: clave in propios for clave in P.CLAVES}

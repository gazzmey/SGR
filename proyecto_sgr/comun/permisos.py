"""
Catálogo de permisos del SGR y cómo se comprueban.

El documento de la entrega pide que la tabla de permisos esté definida y
aprobada antes de ejecutar las pruebas de seguridad. Esta es esa tabla: cada
clave corresponde a una acción concreta del sistema, y un rol habilita las
que le correspondan.

Por qué no se usan los permisos de Django
-----------------------------------------
``django.contrib.auth`` trae permisos por modelo (add / change / delete /
view). Sirven para el administrador, y ahí se usan. Pero el SGR necesita
permisos por **acción de negocio** —validar una evidencia, registrar un
ajuste, configurar un período— que no calzan uno a uno con un modelo. Por eso
el rol guarda su propia lista y estas funciones la consultan.

Lo que no cambia: **la comprobación es del servidor**. Que una pantalla no
muestre un botón no protege nada; lo que protege es el mixin que rechaza la
petición.
"""

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect

# --- claves ---------------------------------------------------------------

REGISTRAR_ACTIVIDAD = "registrar_actividad"
ADJUNTAR_EVIDENCIA = "adjuntar_evidencia"
REGISTRAR_ATENCION = "registrar_atencion"
VALIDAR_EVIDENCIA = "validar_evidencia"
VER_TABLERO = "ver_tablero"
REASIGNAR_COMPROMISO = "reasignar_compromiso"
REGISTRAR_AJUSTE = "registrar_ajuste"
VER_INFORMES = "ver_informes"
CONFIGURAR_PERIODO = "configurar_periodo"
DEFINIR_META = "definir_meta"
GESTIONAR_CATALOGO = "gestionar_catalogo"
GESTIONAR_USUARIO = "gestionar_usuario"
VER_AUDITORIA = "ver_auditoria"

# --- tabla, en el orden en que se muestra ---------------------------------

PERMISOS = [
    (REGISTRAR_ACTIVIDAD, "Registrar actividades", "Mi gestión"),
    (ADJUNTAR_EVIDENCIA, "Adjuntar evidencias", "Mi gestión"),
    (REGISTRAR_ATENCION, "Registrar atención ciudadana", "Mi gestión"),
    (VALIDAR_EVIDENCIA, "Validar evidencias", "Supervisión"),
    (VER_TABLERO, "Ver el tablero de delegación", "Supervisión"),
    (REASIGNAR_COMPROMISO, "Reasignar compromisos", "Supervisión"),
    (REGISTRAR_AJUSTE, "Registrar ajustes", "Supervisión"),
    (VER_INFORMES, "Ver informes", "Supervisión"),
    (CONFIGURAR_PERIODO, "Configurar períodos", "Configuración"),
    (DEFINIR_META, "Definir metas y ponderadores", "Configuración"),
    (GESTIONAR_CATALOGO, "Gestionar catálogos", "Configuración"),
    (GESTIONAR_USUARIO, "Gestionar usuarios y roles", "Administración"),
    (VER_AUDITORIA, "Consultar la auditoría", "Administración"),
]

CLAVES = [clave for clave, _, _ in PERMISOS]
ETIQUETAS = {clave: texto for clave, texto, _ in PERMISOS}
OPCIONES = [(clave, texto) for clave, texto, _ in PERMISOS]


def agrupados():
    """Los permisos por grupo, para dibujar el formulario de roles."""
    grupos = []
    for clave, texto, grupo in PERMISOS:
        if not grupos or grupos[-1][0] != grupo:
            grupos.append((grupo, []))
        grupos[-1][1].append((clave, texto))
    return grupos


def etiqueta(clave):
    return ETIQUETAS.get(clave, clave)


# --- comprobación ---------------------------------------------------------


def perfil_de(usuario):
    """El perfil del usuario, o None si no tiene (por ejemplo, un superusuario)."""
    if not getattr(usuario, "is_authenticated", False):
        return None
    return getattr(usuario, "perfil", None)


def tiene_permiso(usuario, clave):
    """
    True si esa persona puede hacer esa acción.

    Un superusuario pasa siempre: es quien administra el sistema y no
    depende de que alguien le haya creado un perfil.
    """
    if not getattr(usuario, "is_authenticated", False):
        return False
    if usuario.is_superuser:
        return True
    perfil = perfil_de(usuario)
    return bool(perfil and perfil.puede(clave))


class RequierePermiso:
    """
    Mixin para vistas: exige iniciar sesión y tener el permiso indicado.

    Se antepone a la vista, no se consulta dentro de ella, para que no haya
    forma de olvidarlo en una rama del código.
    """

    permiso = None

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_al_login(request)

        if self.permiso and not tiene_permiso(request.user, self.permiso):
            messages.error(
                request,
                "No tienes permiso para entrar ahí. Si crees que es un error, "
                "pídele al administrador que revise tu rol.",
            )
            raise PermissionDenied(
                f"Falta el permiso «{etiqueta(self.permiso)}»."
            )
        return super().dispatch(request, *args, **kwargs)


def redirect_al_login(request):
    from django.urls import reverse

    destino = reverse("cuenta:login")
    siguiente = request.get_full_path()
    if siguiente and siguiente != "/":
        destino = f"{destino}?next={siguiente}"
    return redirect(destino)

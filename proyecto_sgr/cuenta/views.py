"""
Acceso al sistema y recuperación de contraseña en cuatro pasos.

El recorrido es el de la maqueta: se pide el código, llega por correo, se
valida y se crea la contraseña nueva. Lo que cambia es dónde vive el estado.
En la maqueta el correo viajaba en la dirección, a la vista de todos; aquí va
en la **sesión del servidor**, y lo único que el navegador conserva es la
cookie de sesión.

Dos decisiones que conviene poder explicar
------------------------------------------
1. **El sistema responde lo mismo exista o no el correo.** Si contestara
   distinto, cualquiera podría averiguar qué direcciones están registradas
   probando una por una. Por eso el paso 1 siempre lleva a la pantalla del
   código, y cuando el correo no corresponde a nadie simplemente no hay
   código que pueda coincidir.

2. **Las reglas del código están en el modelo, no aquí.** Vigencia de diez
   minutos, un solo uso y tres intentos las aplica
   ``CodigoRecuperacion``. La vista pregunta; no decide.
"""

import time

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.views import LoginView, LogoutView
from django.core.mail import send_mail
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views.decorators.http import require_POST

from cuenta.forms import (
    AccesoForm,
    NuevaClaveForm,
    PedirCodigoForm,
    ValidarCodigoForm,
)
from comun.resultado import anunciar
from cuenta.models import CodigoRecuperacion

Usuario = get_user_model()

# Dónde se guarda el estado del recorrido dentro de la sesión.
CLAVE_FLUJO = "sgr_recuperacion"


# =========================================================================
# Entrar y salir
# =========================================================================


class Acceso(LoginView):
    """Inicio de sesión. Reemplaza al del administrador para el uso normal."""

    template_name = "cuenta/login.html"
    authentication_form = AccesoForm
    redirect_authenticated_user = True

    def form_valid(self, form):
        respuesta = super().form_valid(form)
        perfil = getattr(self.request.user, "perfil", None)
        if perfil:
            messages.success(
                self.request,
                f"Hola de nuevo, {perfil.nombre.split(' ')[0]}. "
                f"Estás trabajando en {perfil.delegacion.nombre}.",
            )
        return respuesta


class Salida(LogoutView):
    """
    Cierre de sesión.

    Desde Django 5 solo acepta POST, y por eso el botón de la cabecera es un
    formulario: con un enlace, cualquier página externa podría cerrarle la
    sesión a quien la visite.
    """

    next_page = reverse_lazy("cuenta:login")


# =========================================================================
# Paso 1 · pedir el código
# =========================================================================


def recuperar(request):
    """Pide el correo y envía el código."""
    if request.method == "POST":
        formulario = PedirCodigoForm(request.POST)
        if formulario.is_valid():
            correo = formulario.cleaned_data["correo"]
            registro = _emitir_para(correo)

            request.session[CLAVE_FLUJO] = {
                "correo": correo,
                "codigo_id": registro.pk if registro else None,
                "validado": False,
                # Marca de tiempo del último envío, para la espera entre
                # reenvíos. Se guarda haya o no cuenta detrás del correo: si
                # solo se guardara cuando existe, el tiempo de espera
                # delataría qué direcciones están registradas.
                "ultimo_envio": time.time(),
            }
            return redirect("cuenta:codigo")
    else:
        formulario = PedirCodigoForm()

    return render(request, "cuenta/recuperar.html", {"form": formulario})


def _emitir_para(correo):
    """
    Emite y envía el código si ese correo corresponde a una cuenta que puede
    usarlo. Si no, devuelve None **sin decirlo**: quien llama responde igual
    en los dos casos.
    """
    usuario = Usuario.objects.filter(email__iexact=correo, is_active=True).first()
    if usuario is None:
        return None

    perfil = getattr(usuario, "perfil", None)
    if perfil is not None and not perfil.activo:
        # La cuenta existe pero está desactivada: recuperar la contraseña no
        # le serviría de nada, porque igual no podría entrar.
        return None

    registro = CodigoRecuperacion.emitir(usuario)
    _enviar(usuario, registro)
    return registro


def _enviar(usuario, registro):
    """
    Manda el correo con el código.

    Con el backend de consola —el de desarrollo— el código aparece en la
    terminal donde corre ``runserver``. Es el mismo código real: no hay una
    rama distinta para desarrollo.
    """
    send_mail(
        subject="SGR · tu código para crear una contraseña nueva",
        message=(
            f"Hola {usuario.get_full_name() or usuario.get_username()}:\n\n"
            f"Tu código para crear una contraseña nueva es {registro.codigo}.\n\n"
            f"Vence en {CodigoRecuperacion.VIGENCIA_MINUTOS} minutos y sirve "
            "una sola vez. Tienes tres intentos para escribirlo.\n\n"
            "Si no pediste este código, no hagas nada: sin él, nadie puede "
            "cambiar tu contraseña.\n\n"
            "Sistema de Gestión de Resultados\n"
            "Delegaciones municipales de La Serena\n"
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[usuario.email],
        fail_silently=True,
    )


# =========================================================================
# Pasos 2 y 3 · validar el código
# =========================================================================


def codigo(request):
    """Recibe los seis dígitos y comprueba el código de la sesión."""
    flujo = request.session.get(CLAVE_FLUJO)
    if not flujo:
        messages.info(request, "Empecemos de nuevo: escribe tu correo institucional.")
        return redirect("cuenta:recuperar")

    registro = _registro_de(flujo)
    formulario = ValidarCodigoForm(request.POST or None)

    if request.method == "POST" and formulario.is_valid():
        escrito = formulario.cleaned_data["codigo"]

        if registro is not None and registro.comprobar(escrito):
            flujo["validado"] = True
            request.session[CLAVE_FLUJO] = flujo
            return redirect("cuenta:nueva_clave")

        if registro is None:
            # Sin cuenta detrás no hay código, pero la pantalla tiene que
            # comportarse como si lo hubiera: los intentos se descuentan y el
            # plazo corre igual. Si no, el reloj y los intentos delatarían
            # qué correos están registrados.
            segundos, quedan = _simulado(flujo)
            if segundos and quedan:
                flujo["intentos_simulados"] = flujo.get("intentos_simulados", 0) + 1
                request.session[CLAVE_FLUJO] = flujo

        # El mismo mensaje haya o no código, por la misma razón.
        formulario.add_error("codigo", _por_que_no_sirve(registro, flujo))

    if registro is not None:
        segundos, intentos = registro.segundos_restantes, registro.intentos_restantes
        if not registro.vigente:
            intentos = 0
    else:
        segundos, intentos = _simulado(flujo)

    return render(request, "cuenta/codigo.html", {
        "form": formulario,
        "correo": flujo["correo"],
        "segundos": segundos,
        "intentos": intentos,
        "espera_reenvio": _espera_restante(flujo),
        "mostrar_codigo": (
            registro.codigo
            if (registro and getattr(settings, "SGR_MOSTRAR_CODIGO", False))
            else ""
        ),
    })


def _registro_de(flujo):
    """El código de la sesión, o None si no había o ya no sirve."""
    if not flujo.get("codigo_id"):
        return None
    return CodigoRecuperacion.objects.filter(pk=flujo["codigo_id"]).first()


def _simulado(flujo):
    """
    Segundos de vigencia e intentos que quedan cuando el correo no tiene
    cuenta. Imitan a un código real: corren desde el último envío y se
    descuentan con cada intento, para que la pantalla no delate si el correo
    está registrado.
    """
    emitido = float(flujo.get("ultimo_envio") or time.time())
    segundos = max(0, int(emitido + CodigoRecuperacion.VIGENCIA_MINUTOS * 60 - time.time()))
    if not segundos:
        return 0, 0
    quedan = max(0, CodigoRecuperacion.INTENTOS_MAXIMOS - flujo.get("intentos_simulados", 0))
    return segundos, quedan


def _por_que_no_sirve(registro, flujo=None):
    """El mensaje que ve la persona cuando el código no la deja pasar."""
    if registro is None:
        segundos, quedan = _simulado(flujo or {})
        vencido, usado, agotado = not segundos, False, not quedan
    else:
        vencido, usado, agotado = registro.vencido, registro.usado, registro.agotado
        quedan = registro.intentos_restantes
    if vencido:
        return (
            f"El código venció: dura {CodigoRecuperacion.VIGENCIA_MINUTOS} "
            "minutos. Pide uno nuevo para continuar."
        )
    if usado:
        return "Ese código ya se usó. Pide uno nuevo para continuar."
    if agotado:
        return (
            "Se agotaron los tres intentos de este código. Pide uno nuevo "
            "para continuar."
        )
    aviso = "Te queda un intento" if quedan == 1 else f"Te quedan {quedan} intentos"
    return f"El código no coincide. {aviso} antes de tener que pedir uno nuevo."


@require_POST
def reenviar(request):
    """Emite otro código para el mismo correo y anula el anterior."""
    flujo = request.session.get(CLAVE_FLUJO)
    if not flujo:
        return redirect("cuenta:recuperar")

    espera = _espera_restante(flujo)
    if espera:
        messages.warning(
            request,
            f"Espera {espera} segundo{'s' if espera != 1 else ''} antes de "
            "pedir otro código.",
        )
        return redirect("cuenta:codigo")

    registro = _emitir_para(flujo["correo"])
    flujo["codigo_id"] = registro.pk if registro else None
    flujo["validado"] = False
    flujo["ultimo_envio"] = time.time()
    flujo["intentos_simulados"] = 0
    request.session[CLAVE_FLUJO] = flujo

    messages.success(
        request,
        "Te enviamos un código nuevo. El anterior quedó sin efecto.",
    )
    return redirect("cuenta:codigo")


def _espera_restante(flujo):
    """
    Segundos que faltan para poder pedir otro código. 0 si ya se puede.

    El control vive en la sesión y no en la base de datos a propósito: así
    funciona igual cuando el correo no corresponde a ninguna cuenta y no hay
    ningún código que consultar. Si dependiera del registro, el reenvío
    respondería distinto según existiera o no la cuenta.
    """
    ultimo = flujo.get("ultimo_envio")
    if not ultimo:
        return 0
    pasados = time.time() - float(ultimo)
    faltan = CodigoRecuperacion.ESPERA_REENVIO_SEGUNDOS - pasados
    return max(0, int(faltan + 0.999)) if faltan > 0 else 0


# =========================================================================
# Paso 4 · la contraseña nueva
# =========================================================================


def nueva_clave(request):
    """Guarda la contraseña nueva y consume el código."""
    flujo = request.session.get(CLAVE_FLUJO)
    registro = _registro_de(flujo) if flujo else None

    # Se vuelve a comprobar aquí, no solo en el paso anterior: entrar
    # escribiendo la dirección a mano no debe servir de nada.
    if not flujo or not flujo.get("validado") or registro is None or not registro.vigente:
        messages.error(
            request,
            "Para crear una contraseña nueva hay que validar primero un "
            "código vigente.",
        )
        return redirect("cuenta:recuperar")

    usuario = registro.usuario

    if request.method == "POST":
        formulario = NuevaClaveForm(usuario, request.POST)
        if formulario.is_valid():
            formulario.save()          # set_password() + save(): guarda el hash
            registro.consumir()        # el código queda usado
            request.session.pop(CLAVE_FLUJO, None)
            anunciar(
                request,
                "Contraseña actualizada",
                "Ya puedes iniciar sesión con la contraseña nueva. La "
                "anterior dejó de servir y el código que usaste quedó "
                "invalidado.",
            )
            return redirect("cuenta:login")
    else:
        formulario = NuevaClaveForm(usuario)

    return render(request, "cuenta/nueva_clave.html", {
        "form": formulario,
        "correo": usuario.email,
    })

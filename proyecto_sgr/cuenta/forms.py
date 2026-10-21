"""
Formularios de acceso y de recuperación de contraseña.

Se apoyan en los de Django —``AuthenticationForm`` y ``SetPasswordForm``—
porque son los que ya traen el trabajo delicado hecho: autenticar sin filtrar
si el usuario existe, y validar la contraseña con los validadores
configurados en ``AUTH_PASSWORD_VALIDATORS``. Lo que se agrega es lo propio
del SGR: entrar con el correo institucional en lugar del nombre de usuario, y
el código de seis dígitos.
"""

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, SetPasswordForm

Usuario = get_user_model()


class AccesoForm(AuthenticationForm):
    """
    Inicio de sesión con el correo institucional.

    Django autentica por ``username``. Aquí la persona escribe su correo, así
    que antes de autenticar se traduce el correo al nombre de usuario que le
    corresponde. La traducción no revela nada: si el correo no existe, se
    envía tal cual y el resultado es el mismo mensaje de siempre.
    """

    username = forms.CharField(
        label="Correo institucional",
        widget=forms.EmailInput(attrs={
            "class": "input",
            "autocomplete": "username",
            "placeholder": "nombre.apellido@ejemplo.cl",
            "autofocus": True,
        }),
    )
    password = forms.CharField(
        label="Contraseña",
        strip=False,
        widget=forms.PasswordInput(attrs={
            "class": "input",
            "autocomplete": "current-password",
        }),
    )

    error_messages = {
        "invalid_login": (
            "El correo o la contraseña no son correctos, o la cuenta no está "
            "activa. Revisa tus datos e inténtalo de nuevo."
        ),
        "inactive": (
            "Esa cuenta está desactivada. Pídele al administrador del sistema "
            "que la reactive."
        ),
    }

    def clean(self):
        escrito = (self.cleaned_data.get("username") or "").strip()
        if "@" in escrito:
            usuario = Usuario.objects.filter(email__iexact=escrito).first()
            if usuario:
                self.cleaned_data["username"] = usuario.get_username()
        return super().clean()

    def confirm_login_allowed(self, user):
        """
        Además de ``is_active``, se revisa el perfil del SGR.

        Un usuario puede estar activo en Django y tener su perfil o su rol
        desactivados en el sistema; en ese caso no debe entrar, porque no
        tendría ni delegación ni permisos.
        """
        super().confirm_login_allowed(user)

        if user.is_superuser:
            return

        perfil = getattr(user, "perfil", None)
        if perfil is None:
            raise forms.ValidationError(
                "Tu cuenta todavía no tiene perfil en el SGR. Pídele al "
                "administrador que te asigne rol y delegación.",
                code="sin_perfil",
            )
        if not perfil.activo:
            raise forms.ValidationError(
                "Tu perfil está desactivado. Pídele al administrador del "
                "sistema que lo reactive.",
                code="perfil_inactivo",
            )
        if not perfil.rol.activo:
            raise forms.ValidationError(
                "El rol «%(rol)s» está desactivado, así que tu cuenta no "
                "tiene permisos asignados. Avisa al administrador.",
                code="rol_inactivo",
                params={"rol": perfil.rol.nombre},
            )


class PedirCodigoForm(forms.Form):
    """Primer paso: a qué correo se envía el código."""

    correo = forms.EmailField(
        label="Correo institucional",
        widget=forms.EmailInput(attrs={
            "class": "input",
            "autocomplete": "username",
            "placeholder": "nombre.apellido@ejemplo.cl",
            "autofocus": True,
        }),
        help_text="El mismo con el que inicias sesión.",
    )

    def clean_correo(self):
        return (self.cleaned_data["correo"] or "").strip().lower()


class ValidarCodigoForm(forms.Form):
    """
    Segundo paso: los seis dígitos.

    El campo es uno solo: un cuadro donde se escriben los seis dígitos. Si
    hay JavaScript, se reemplaza por las seis casillas de la maqueta, que son
    más cómodas y que al escribir rellenan este mismo campo. Sin JavaScript
    la pantalla sigue funcionando con el cuadro.

    Quien decide si el código sirve es el modelo ``CodigoRecuperacion``, que
    además controla la vigencia y los intentos.
    """

    codigo = forms.CharField(
        label="Código de verificación",
        min_length=6,
        max_length=6,
        widget=forms.TextInput(attrs={
            "class": "input",
            "inputmode": "numeric",
            "maxlength": "6",
            "autocomplete": "one-time-code",
            "placeholder": "000000",
            "autofocus": True,
            "data-codigo-completo": "1",
        }),
        error_messages={
            "required": "Escribe los seis dígitos del código.",
            "min_length": "El código tiene seis dígitos.",
            "max_length": "El código tiene seis dígitos.",
        },
    )

    def clean_codigo(self):
        valor = (self.cleaned_data["codigo"] or "").strip()
        if not valor.isdigit():
            raise forms.ValidationError("El código son seis dígitos, sin letras ni espacios.")
        return valor


class NuevaClaveForm(SetPasswordForm):
    """
    Último paso: la contraseña nueva.

    Hereda de ``SetPasswordForm``, así que la comprobación de las dos
    escrituras y los validadores de ``AUTH_PASSWORD_VALIDATORS`` se aplican
    sin reescribirlos. Guardar llama a ``set_password()``, que almacena el
    hash: la contraseña en claro no se guarda en ninguna parte.
    """

    # El mensaje de «no coinciden» lo busca el propio formulario en
    # self.error_messages, no en el campo, así que se reemplaza aquí.
    error_messages = {
        **SetPasswordForm.error_messages,
        "password_mismatch": "Las dos contraseñas no coinciden.",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["new_password1"].label = "Contraseña nueva"
        self.fields["new_password1"].widget.attrs.update({
            "class": "input",
            "autocomplete": "new-password",
            "data-clave": "1",
            "autofocus": True,
        })
        # Django ya publica aquí el texto de los validadores configurados; la
        # pantalla muestra además el medidor de fuerza, que es solo informativo.
        self.fields["new_password1"].help_text = ""

        self.fields["new_password2"].label = "Repite la contraseña"
        self.fields["new_password2"].widget.attrs.update({
            "class": "input",
            "autocomplete": "new-password",
        })

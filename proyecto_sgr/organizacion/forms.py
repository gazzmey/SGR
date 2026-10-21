"""
Formularios de delegaciones, roles y usuarios.

Las reglas que la maqueta comprobaba en el navegador están aquí. Es el
mismo criterio escrito donde corresponde: el navegador avisa antes de
enviar, pero quien decide si algo se guarda es el servidor.
"""

from django import forms
from django.contrib.auth import get_user_model
from django.db import transaction

from comun import permisos as P
from comun.utilidades import proximo_codigo
from organizacion.models import Delegacion, PerfilUsuario, Rol

Usuario = get_user_model()


class _Base(forms.ModelForm):
    """Lo común: el código se asigna solo y no se escribe a mano."""

    prefijo = ""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "codigo" in self.fields:
            self.fields["codigo"].disabled = True
            self.fields["codigo"].required = False
            if not self.instance.pk:
                self.initial["codigo"] = proximo_codigo(self._meta.model, self.prefijo)
            self.fields["codigo"].help_text = (
                "Asignado al crear. No se puede cambiar: lo usan los informes, "
                "la exportación y la auditoría."
            )

    def save(self, commit=True):
        objeto = super().save(commit=False)
        if not objeto.pk and not objeto.codigo.startswith(f"{self.prefijo}-"):
            objeto.codigo = proximo_codigo(self._meta.model, self.prefijo)
        if commit:
            objeto.save()
            self.save_m2m()
        return objeto


# =========================================================================
# Delegaciones
# =========================================================================


class DelegacionForm(_Base):
    prefijo = "DEL"

    class Meta:
        model = Delegacion
        fields = [
            "codigo", "nombre", "zona", "comuna", "direccion",
            "telefono", "horario",
        ]
        widgets = {
            "nombre": forms.TextInput(attrs={"placeholder": "Por ejemplo: Las Compañías"}),
            "direccion": forms.TextInput(attrs={
                "placeholder": "Calle o avenida, numeración y referencia",
                "ancho": True,
            }),
            "telefono": forms.TextInput(attrs={"placeholder": "51 2 200 000", "inputmode": "tel"}),
            "horario": forms.TextInput(attrs={"placeholder": "Lun a vie · 09:00 a 14:00"}),
        }

    def clean_nombre(self):
        nombre = (self.cleaned_data["nombre"] or "").strip()
        if len(nombre) < 3:
            raise forms.ValidationError("El nombre debe tener al menos 3 caracteres.")
        return nombre

    def clean_direccion(self):
        direccion = (self.cleaned_data.get("direccion") or "").strip()
        if direccion and len(direccion) < 5:
            raise forms.ValidationError("La dirección parece incompleta.")
        return direccion

    def clean_telefono(self):
        telefono = (self.cleaned_data.get("telefono") or "").strip()
        if telefono and not all(c.isdigit() or c in " +()-" for c in telefono):
            raise forms.ValidationError(
                "El teléfono solo admite números, espacios y los signos + ( ) -"
            )
        return telefono


# =========================================================================
# Roles
# =========================================================================


class RolForm(_Base):
    prefijo = "ROL"

    permisos = forms.MultipleChoiceField(
        label="Acciones habilitadas",
        choices=P.OPCIONES,
        widget=forms.CheckboxSelectMultiple,
        required=True,
        help_text="Hay que marcar al menos una.",
    )

    class Meta:
        model = Rol
        fields = ["codigo", "nombre", "descripcion", "alcance", "permisos"]
        widgets = {
            "nombre": forms.TextInput(attrs={"placeholder": "Por ejemplo: Verificador"}),
            "descripcion": forms.Textarea(attrs={
                "rows": 3,
                "placeholder": "Una frase que explique la función",
                "ancho": True,
            }),
        }
        labels = {"descripcion": "Qué hace quien tiene este rol"}

    def clean_descripcion(self):
        texto = (self.cleaned_data.get("descripcion") or "").strip()
        if len(texto) < 20:
            raise forms.ValidationError(
                "Describe el rol con un poco más de detalle."
            )
        return texto


# =========================================================================
# Usuarios
# =========================================================================


class UsuarioForm(_Base):
    """
    Un formulario sobre dos modelos.

    El nombre y el correo viven en ``auth.User``; el cargo, el rol y las
    delegaciones, en ``PerfilUsuario``. El formulario los muestra juntos y
    los guarda en una sola transacción: si algo falla, no queda un usuario
    a medio crear sin perfil.

    La contraseña no está aquí a propósito. Una cuenta nueva nace sin
    contraseña utilizable y la persona crea la suya con el enlace de
    recuperación; así nadie, ni el administrador, llega a conocerla.
    """

    prefijo = "USR"

    nombre = forms.CharField(
        label="Nombre y apellido", max_length=120,
        widget=forms.TextInput(attrs={"placeholder": "Por ejemplo: Marcela Ríos"}),
    )
    correo = forms.EmailField(
        label="Correo institucional",
        widget=forms.EmailInput(attrs={
            "placeholder": "nombre.apellido@ejemplo.cl",
            "ancho": True,
        }),
        help_text="Es su usuario de acceso. Tiene que ser único.",
    )

    class Meta:
        model = PerfilUsuario
        fields = [
            "codigo", "nombre", "correo", "cargo", "cargo_asignado",
            "delegacion", "delegaciones_autorizadas", "rol",
        ]
        widgets = {
            "delegaciones_autorizadas": forms.CheckboxSelectMultiple,
            "cargo": forms.TextInput(attrs={"placeholder": "Por ejemplo: Encargado territorial"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Los selectores solo ofrecen lo activo, más lo que ya tenga el
        # registro que se edita: no se ofrece un inactivo, pero tampoco se
        # borra en silencio el valor guardado.
        self.fields["delegacion"].queryset = self._activas(
            Delegacion, getattr(self.instance, "delegacion_id", None)
        )
        self.fields["delegaciones_autorizadas"].queryset = self._activas(
            Delegacion,
            *(self.instance.delegaciones_autorizadas.values_list("pk", flat=True)
              if self.instance.pk else ()),
        )
        self.fields["rol"].queryset = self._activas(
            Rol, getattr(self.instance, "rol_id", None)
        )
        self.fields["delegaciones_autorizadas"].required = False

        # El cargo con metas decide con qué ítems se mide a la persona, así
        # que es el que usa el cálculo. Se ofrece aquí porque es aquí donde
        # se administra a la gente; sin este campo en el formulario, una
        # cuenta nueva no se podía medir nunca y había que tocar la base.
        from gestion.models import Cargo

        self.fields["cargo_asignado"].queryset = self._activas(
            Cargo, getattr(self.instance, "cargo_asignado_id", None)
        )
        self.fields["cargo_asignado"].required = False
        self.fields["cargo_asignado"].empty_label = "Sin cargo con metas"

        if self.instance.pk:
            self.initial.setdefault("nombre", self.instance.usuario.get_full_name())
            self.initial.setdefault("correo", self.instance.usuario.email)

    @staticmethod
    def _activas(modelo, *incluir):
        pks = [pk for pk in incluir if pk]
        consulta = modelo._default_manager.filter(activo=True)
        if pks:
            from django.db.models import Q

            consulta = modelo._default_manager.filter(Q(activo=True) | Q(pk__in=pks))
        return consulta.distinct()

    def clean_nombre(self):
        nombre = (self.cleaned_data["nombre"] or "").strip()
        if len(nombre) < 5:
            raise forms.ValidationError("Escribe el nombre completo.")
        return nombre

    def clean_correo(self):
        correo = (self.cleaned_data["correo"] or "").strip().lower()
        otros = Usuario.objects.filter(email__iexact=correo)
        if self.instance.pk:
            otros = otros.exclude(pk=self.instance.usuario_id)
        if otros.exists():
            raise forms.ValidationError(
                "Ya hay una cuenta con ese correo. El correo es el usuario de "
                "acceso, así que no puede repetirse."
            )
        return correo

    @transaction.atomic
    def save(self, commit=True):
        """Guarda el usuario de Django y su perfil como una sola operación."""
        nombre = self.cleaned_data["nombre"]
        correo = self.cleaned_data["correo"]
        partes = nombre.split(" ", 1)

        if self.instance.pk:
            usuario = self.instance.usuario
        else:
            usuario = Usuario()
            # Contraseña inutilizable: la persona la define con el enlace de
            # recuperación. set_unusable_password() no guarda ningún hash
            # con el que se pueda entrar.
            usuario.set_unusable_password()

        usuario.username = correo[:150]
        usuario.email = correo
        usuario.first_name = partes[0][:150]
        usuario.last_name = (partes[1] if len(partes) > 1 else "")[:150]
        usuario.is_active = True
        usuario.save()

        perfil = super().save(commit=False)
        perfil.usuario = usuario
        perfil.save()
        self.save_m2m()
        return perfil

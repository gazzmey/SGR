"""
Formularios de delegaciones, roles y usuarios.

Las reglas que la maqueta comprobaba en el navegador están aquí. Es el
mismo criterio escrito donde corresponde: el navegador avisa antes de
enviar, pero quien decide si algo se guarda es el servidor.
"""

import re
from decimal import Decimal, InvalidOperation

from django import forms
from django.contrib.auth import get_user_model
from django.db import transaction

from comun import permisos as P
from comun.formularios import (
    ConAlcance, activos_mas, limpiar_telefono, nombre_de_usuario, telefono_obligatorio,
)
from comun.rut import limpiar_rut, rut_valido
from comun.utilidades import proximo_codigo
from organizacion.models import Delegacion, PerfilUsuario, Rol, Territorio

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
            "telefono", "horario", "delegado",
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        telefono_obligatorio(self.fields["telefono"])
        actual = getattr(self.instance, "delegado_id", None)
        consulta = Usuario.objects.filter(is_active=True, perfil__activo=True)
        if actual:
            from django.db.models import Q

            consulta = Usuario.objects.filter(
                Q(pk__in=consulta.values("pk")) | Q(pk=actual))
        self.fields["delegado"].queryset = consulta.order_by("first_name", "last_name")
        self.fields["delegado"].label_from_instance = nombre_de_usuario
        self.fields["delegado"].empty_label = "Sin delegado asignado"

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
        return limpiar_telefono(self.cleaned_data.get("telefono"))


# =========================================================================
# Territorios
# =========================================================================


# Lo que el mapa acepta como ubicación: la Región de Coquimbo con holgura.
# Sirve para atajar el error más común, que es pegar las coordenadas al
# revés (longitud primero) o con el signo cambiado.
REGION_LATITUD = (-32.5, -28.0)
REGION_LONGITUD = (-72.0, -69.5)


def leer_ubicacion(texto):
    """
    «-29.8705, -71.2365» → (Decimal latitud, Decimal longitud), o None si
    viene vacío. Acepta coma o punto y coma entre los dos números, y la coma
    decimal si los números van separados por punto y coma o espacio.
    """
    texto = (texto or "").strip()
    if not texto:
        return None
    partes = [p for p in re.split(r"\s*[;,]\s*|\s+", texto) if p]
    if len(partes) == 4:          # «-29,8705; -71,2365» partido en las comas
        partes = [partes[0] + "." + partes[1], partes[2] + "." + partes[3]]
    if len(partes) != 2:
        raise forms.ValidationError(
            "Escribe la latitud y la longitud separadas por una coma, "
            "por ejemplo: -29.8705, -71.2365.")
    try:
        latitud, longitud = (Decimal(p.replace(",", ".")) for p in partes)
    except InvalidOperation:
        raise forms.ValidationError("Las coordenadas deben ser números, por ejemplo: -29.8705, -71.2365.")
    if REGION_LONGITUD[0] <= latitud <= REGION_LONGITUD[1] and \
            REGION_LATITUD[0] <= longitud <= REGION_LATITUD[1]:
        raise forms.ValidationError(
            "Parece que están al revés: va primero la latitud (cerca de -29.9) "
            "y después la longitud (cerca de -71.2).")
    if not (REGION_LATITUD[0] <= latitud <= REGION_LATITUD[1]
            and REGION_LONGITUD[0] <= longitud <= REGION_LONGITUD[1]):
        raise forms.ValidationError(
            "Esa ubicación queda fuera de la Región de Coquimbo. Revisa el signo: "
            "en La Serena las dos coordenadas son negativas.")
    return latitud.quantize(Decimal("0.000001")), longitud.quantize(Decimal("0.000001"))


class TerritorioForm(ConAlcance, _Base):
    prefijo = "TER"

    ubicacion = forms.CharField(
        label="Ubicación en el mapa", required=False, max_length=60,
        widget=forms.TextInput(attrs={"placeholder": "Por ejemplo: -29.8705, -71.2365",
                                      "inputmode": "decimal", "autocomplete": "off"}),
        help_text=(
            "Un punto aproximado al centro del territorio, para el mapa de presencia. "
            "En Google Maps, mantén presionado el lugar y copia los números que aparecen. "
            "No pongas la casa de un vecino: basta el centro del sector."),
    )

    class Meta:
        model = Territorio
        fields = ["codigo", "nombre", "delegacion", "descripcion"]
        widgets = {
            "nombre": forms.TextInput(attrs={"placeholder": "Por ejemplo: Unidad vecinal 7 · Las Rosas"}),
            "descripcion": forms.Textarea(attrs={
                "rows": 3, "ancho": True,
                "placeholder": "Calles, poblaciones o sectores que comprende",
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["delegacion"].queryset = self.delegaciones(
            getattr(self.instance, "delegacion_id", None))
        self.fields["delegacion"].empty_label = "Elige la delegación"
        if self.instance.pk and not self.is_bound:
            self.initial["ubicacion"] = self.instance.ubicacion_texto

    def clean_nombre(self):
        nombre = (self.cleaned_data["nombre"] or "").strip()
        if len(nombre) < 3:
            raise forms.ValidationError("El nombre debe tener al menos 3 caracteres.")
        return nombre

    def clean_ubicacion(self):
        return leer_ubicacion(self.cleaned_data.get("ubicacion"))

    def save(self, commit=True):
        punto = self.cleaned_data.get("ubicacion")
        self.instance.latitud, self.instance.longitud = punto if punto else (None, None)
        return super().save(commit=commit)

    def clean(self):
        datos = super().clean()
        nombre, delegacion = datos.get("nombre"), datos.get("delegacion")
        if nombre and delegacion:
            repetido = (Territorio.objects.filter(delegacion=delegacion, nombre__iexact=nombre)
                        .exclude(pk=self.instance.pk).exists())
            if repetido:
                self.add_error("nombre", "%s ya tiene un territorio con ese nombre."
                               % delegacion.nombre)
        return datos


# =========================================================================
# Roles
# =========================================================================


class RolForm(_Base):
    """
    El formulario general del rol: código, nombre y descripción.

    Los privilegios —acciones, alcance y grupo de Django— no están aquí: los
    configura quien administra el acceso en una pantalla aparte
    (``RolPrivilegiosForm``). Así el perfil Gestión puede mantener los roles
    sin poder darse a sí mismo, ni a nadie, más permisos.
    """

    prefijo = "ROL"

    class Meta:
        model = Rol
        fields = ["codigo", "nombre", "descripcion"]
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
                f"Describe el rol con un poco más de detalle. Debe tener al menos 20 caracteres (escribiste {len(texto)})."
            )
        return texto



class RolPrivilegiosForm(forms.ModelForm):
    """
    Los privilegios de un rol. Solo lo usa quien administra el acceso.

    Se edita por separado del formulario general a propósito: la Evaluación
    3 pide mantener la asignación de permisos fuera de los formularios
    generales.
    """

    permisos = forms.MultipleChoiceField(
        label="Acciones habilitadas",
        choices=P.OPCIONES,
        widget=forms.CheckboxSelectMultiple,
        required=False,
        help_text="Las acciones de negocio del SGR. Un rol puede no tener ninguna si su grupo de Django le da acceso.",
    )

    class Meta:
        model = Rol
        fields = ["alcance", "grupo", "permisos"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["grupo"].empty_label = "Sin grupo de Django"

    def clean(self):
        datos = super().clean()
        if not datos.get("permisos") and not datos.get("grupo"):
            raise forms.ValidationError(
                "Un rol sin acciones y sin grupo no puede hacer nada. Marca al "
                "menos una acción o elige un grupo de Django."
            )
        return datos

    def clean_permisos(self):
        """Separación de funciones: quien registra actividades no las valida."""
        elegidos = self.cleaned_data.get("permisos") or []
        for uno, otro in P.INCOMPATIBLES:
            if uno in elegidos and otro in elegidos:
                raise forms.ValidationError(
                    "Un mismo rol no puede «%s» y «%s»: aprobaría su propio "
                    "trabajo. Validar es del Verificador y del Administrador."
                    % (P.etiqueta(uno).lower(), P.etiqueta(otro).lower())
                )
        return elegidos


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

    nombres = forms.CharField(
        label="Nombres", max_length=150,
        widget=forms.TextInput(attrs={"placeholder": "Por ejemplo: Marcela Andrea"}),
    )
    apellidos = forms.CharField(
        label="Apellidos", max_length=150,
        widget=forms.TextInput(attrs={"placeholder": "Por ejemplo: Ríos Contreras"}),
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
            "codigo", "rut", "nombres", "apellidos", "correo", "cargo", "cargo_asignado",
            "delegacion", "delegaciones_autorizadas", "rol",
        ]
        widgets = {
            "delegaciones_autorizadas": forms.CheckboxSelectMultiple,
            "cargo": forms.TextInput(attrs={"placeholder": "Por ejemplo: Encargado territorial"}),
            "rut": forms.TextInput(attrs={"placeholder": "12.345.678-5", "class": "mono"}),
        }

    #: Lo que nadie cambia de su propia cuenta: decide qué puede hacer.
    CAMPOS_DE_PRIVILEGIO = ("rol", "delegacion", "delegaciones_autorizadas")

    def __init__(self, *args, editor=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.editor = editor

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

        self.fields["rut"].required = True
        self.fields["rut"].help_text = "Ficticio, con dígito verificador. No se repite entre usuarios."

        if self.instance.pk:
            self.initial.setdefault("nombres", self.instance.usuario.first_name)
            self.initial.setdefault("apellidos", self.instance.usuario.last_name)
            self.initial.setdefault("correo", self.instance.usuario.email)

        # Nadie se asigna privilegios a sí mismo: en la propia ficha, el rol
        # y las delegaciones quedan bloqueados. ``disabled`` hace que Django
        # ignore lo que llegue en el envío y conserve lo guardado.
        if editor is not None and self.instance.pk and self.instance.usuario_id == editor.pk:
            for nombre in self.CAMPOS_DE_PRIVILEGIO:
                self.fields[nombre].disabled = True
            self.fields["rol"].help_text = (
                "Es tu propia cuenta: tu rol y tus delegaciones los cambia otra "
                "persona con permiso para administrar usuarios."
            )
        elif editor is not None:
            # Quien no administra el acceso solo asigna roles que no dan más
            # de lo que él mismo tiene (ver roles_asignables).
            actual = getattr(self.instance, "rol_id", None)
            asignables = [r.pk for r in roles_asignables(editor)]
            self.fields["rol"].queryset = Rol.objects.filter(
                pk__in=asignables + ([actual] if actual else [])).distinct()

    @staticmethod
    def _activas(modelo, *incluir):
        pks = [pk for pk in incluir if pk]
        consulta = modelo._default_manager.filter(activo=True)
        if pks:
            from django.db.models import Q

            consulta = modelo._default_manager.filter(Q(activo=True) | Q(pk__in=pks))
        return consulta.distinct()

    def clean_nombres(self):
        valor = (self.cleaned_data["nombres"] or "").strip()
        if len(valor) < 2:
            raise forms.ValidationError("Escribe al menos un nombre.")
        return valor

    def clean_apellidos(self):
        valor = (self.cleaned_data["apellidos"] or "").strip()
        if len(valor) < 2:
            raise forms.ValidationError("Escribe al menos un apellido.")
        return valor

    def clean_rut(self):
        valor = limpiar_rut(self.cleaned_data.get("rut"))
        if not rut_valido(valor):
            raise forms.ValidationError(
                "Ese RUT no es válido: revisa el número y el dígito verificador.")
        otro = PerfilUsuario.objects.filter(rut=valor).exclude(pk=self.instance.pk).first()
        if otro is not None:
            raise forms.ValidationError("Ese RUT ya es de %s." % otro.nombre)
        return valor

    def clean_rol(self):
        rol = self.cleaned_data.get("rol")
        editor = self.editor
        if (rol and editor is not None and not (self.instance.pk and self.instance.usuario_id == editor.pk)
                and rol.pk != getattr(self.instance, "rol_id", None)
                and rol not in roles_asignables(editor)):
            raise forms.ValidationError(
                "No puedes asignar «%s»: da permisos que tú no tienes." % rol.nombre)
        return rol

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
        correo = self.cleaned_data["correo"]

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
        usuario.first_name = self.cleaned_data["nombres"][:150]
        usuario.last_name = self.cleaned_data["apellidos"][:150]
        usuario.is_active = True
        usuario.save()

        perfil = super().save(commit=False)
        perfil.usuario = usuario
        perfil.save()
        self.save_m2m()
        return perfil


# =========================================================================
# Quién puede asignar qué rol
# =========================================================================


def privilegios_de_rol(rol):
    """Las acciones de negocio y los permisos de Django que entrega un rol."""
    permisos = set()
    if rol.grupo_id:
        permisos = {f"{p.content_type.app_label}.{p.codename}"
                    for p in rol.grupo.permissions.select_related("content_type")}
    return set(rol.permisos or []), permisos


def roles_asignables(editor):
    """
    Los roles activos que esa persona puede asignar a otra.

    Quien administra el acceso (la acción «Gestionar usuarios y roles», o el
    superusuario) asigna cualquiera. Quien solo gestiona registros —el
    perfil Gestión— asigna únicamente roles que no le dan a otro más de lo
    que tiene él: sin acciones de negocio que no tenga y sin permisos de
    Django que no tenga. Así no puede fabricarse una cuenta con más poder
    que la suya.
    """
    activos = list(Rol.objects.filter(activo=True).select_related("grupo"))
    if P.tiene_permiso(editor, P.GESTIONAR_USUARIO):
        return activos
    propios = editor.get_all_permissions() if editor.is_active else set()
    permitidos = []
    for rol in activos:
        acciones, de_django = privilegios_de_rol(rol)
        if all(P.tiene_permiso(editor, a) for a in acciones) and de_django <= propios:
            permitidos.append(rol)
    return permitidos

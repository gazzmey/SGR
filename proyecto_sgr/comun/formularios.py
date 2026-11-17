"""
Piezas que comparten los formularios de las entidades de la Evaluación 3.

* ``ConAlcance``: el formulario recibe quién edita y qué delegaciones puede
  usar, y limita sus selectores a eso. Así un formulario enviado a mano con
  la clave de una delegación ajena no pasa la validación: el valor no está
  entre las opciones.
* ``activos_mas``: los registros activos de un modelo, más el que ya tenga
  el registro en edición. Un registro que apunta a algo desactivado después
  no pierde ese dato al editarse.
* ``fecha``: el campo de fecha del navegador, en formato ISO.
"""

from django import forms
from django.db.models import Q

from comun.utilidades import proximo_codigo


def fecha():
    return forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")


def activos_mas(consulta, *actuales):
    """Los activos de ``consulta`` más los pk indicados, sin repetir."""
    pks = [pk for pk in actuales if pk]
    modelo = consulta.model
    if pks:
        return modelo._default_manager.filter(
            Q(pk__in=consulta.filter(activo=True).values("pk")) | Q(pk__in=pks)
        ).distinct()
    return consulta.filter(activo=True)


TELEFONO_VALIDO = set("0123456789 +()-")
TELEFONO_FALTA = "El teléfono es obligatorio: es la forma de avisar cuando el trámite avance."


def limpiar_telefono(valor):
    """
    Teléfono obligatorio, con 8 a 12 dígitos.

    Admite espacios y los signos + ( ) -, así que «9 1234 5678», «51 2 200 101»
    y «+56 9 1234 5678» sirven. Lo usan todos los formularios que piden
    teléfono: vecino, delegación, ingreso de atención y regalos.
    """
    valor = (valor or "").strip()
    if not valor:
        raise forms.ValidationError(TELEFONO_FALTA)
    if not set(valor) <= TELEFONO_VALIDO:
        raise forms.ValidationError("El teléfono solo admite números, espacios y los signos + ( ) -")
    digitos = sum(c.isdigit() for c in valor)
    if digitos < 8:
        raise forms.ValidationError(
            f"El teléfono parece incompleto: tiene {digitos} dígitos y necesita al menos 8.")
    if digitos > 12:
        raise forms.ValidationError(f"El teléfono tiene {digitos} dígitos: revisa que no sobre ninguno.")
    return valor


def telefono_obligatorio(campo):
    campo.required = True
    campo.error_messages["required"] = TELEFONO_FALTA


def nombre_de_usuario(usuario):
    return usuario.get_full_name() or usuario.get_username()


class ConAlcance:
    """Mixin para ModelForm: conoce a quien edita y su alcance de delegaciones."""

    def __init__(self, *args, usuario=None, delegaciones=None, **kwargs):
        self.usuario = usuario
        #: Lista de pk de delegaciones permitidas, o None si no hay límite.
        self.permitidas = delegaciones
        super().__init__(*args, **kwargs)
        for campo in self.fields.values():
            if isinstance(campo, forms.DateField):
                campo.input_formats = ["%Y-%m-%d"]

    def delegaciones(self, actual=None):
        from organizacion.models import Delegacion

        consulta = Delegacion.objects.all()
        if self.permitidas is not None:
            consulta = consulta.filter(pk__in=self.permitidas)
        return activos_mas(consulta, actual)

    def territorios(self, actual=None):
        from organizacion.models import Territorio

        consulta = Territorio.objects.select_related("delegacion")
        if self.permitidas is not None:
            consulta = consulta.filter(delegacion_id__in=self.permitidas)
        # Por delegación y por nombre: la lista se lee agrupada y en orden,
        # no en el orden en que se fueron creando.
        return activos_mas(consulta, actual).select_related("delegacion").order_by(
            "delegacion__nombre", "nombre")

    def territorios_de_primero(self, delegacion, nombre="territorio"):
        """
        Pone primero los territorios de ``delegacion`` (la activa, por lo
        general). En la lista se ven agrupados por delegación, y el grupo de
        quien está registrando queda arriba en vez de en orden alfabético.
        """
        from django.db.models import Case, IntegerField, Value, When

        campo = self.fields.get(nombre)
        if campo is None or delegacion is None:
            return
        campo.queryset = campo.queryset.order_by(
            Case(When(delegacion=delegacion, then=Value(0)), default=Value(1),
                 output_field=IntegerField()),
            "delegacion__nombre", "nombre")

    def personas(self, *actuales):
        """Usuarios activos con perfil activo, dentro del alcance."""
        from django.contrib.auth import get_user_model

        Usuario = get_user_model()
        consulta = Usuario.objects.filter(is_active=True, perfil__activo=True)
        if self.permitidas is not None:
            consulta = consulta.filter(
                Q(perfil__delegacion_id__in=self.permitidas)
                | Q(perfil__delegaciones_autorizadas__in=self.permitidas)
            )
        pks = [pk for pk in actuales if pk]
        if pks:
            consulta = Usuario.objects.filter(
                Q(pk__in=consulta.values("pk")) | Q(pk__in=pks))
        return consulta.distinct().order_by("first_name", "last_name")

    @staticmethod
    def rotular_personas(*campos):
        for campo in campos:
            campo.label_from_instance = nombre_de_usuario

    def proponer(self, nombre, valor):
        """
        Valor inicial sugerido para un campo (relleno inteligente).

        Solo al crear, en el formulario sin enviar, y si nadie lo puso antes:
        lo que llega por la dirección desde una ficha manda. Si el valor no
        está entre las opciones —fuera del alcance o inactivo— no se propone.
        """
        if valor in (None, "") or nombre not in self.fields or self.is_bound or self.instance.pk:
            return
        if self.initial.get(nombre) not in (None, ""):
            return
        consulta = getattr(self.fields[nombre], "queryset", None)
        if consulta is not None:
            valor = getattr(valor, "pk", valor)
            if not consulta.filter(pk=valor).exists():
                return
        self.initial[nombre] = valor
        # Una propuesta, no una elección: el navegador la puede reemplazar
        # cuando otro campo indique algo más preciso.
        self.fields[nombre].widget.attrs["data-propuesto"] = "1"


class ConCodigo(forms.ModelForm):
    """
    El código se asigna solo al crear y no se edita.

    Es el mismo criterio de los mantenedores de la segunda entrega: los
    códigos son únicos (lo garantiza la base) y los genera el sistema, así
    que nadie tiene que inventarlos ni puede repetirlos.
    """

    prefijo = ""
    ancho = 2

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "codigo" in self.fields:
            self.fields["codigo"].disabled = True
            self.fields["codigo"].required = False
            if not self.instance.pk:
                self.initial["codigo"] = proximo_codigo(self._meta.model, self.prefijo, self.ancho)
            self.fields["codigo"].help_text = "Asignado al crear. No se puede cambiar."

    def save(self, commit=True):
        objeto = super().save(commit=False)
        if not objeto.pk and not (objeto.codigo or "").startswith(f"{self.prefijo}-"):
            objeto.codigo = proximo_codigo(self._meta.model, self.prefijo, self.ancho)
        if commit:
            objeto.save()
            self.save_m2m()
        return objeto

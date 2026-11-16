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
        return activos_mas(consulta, actual)

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

"""Formularios de actividades y evidencias."""

from django import forms

from catalogos.models import Item
from comun.utilidades import proximo_codigo
from gestion.modelos_actividad import Actividad, Evidencia
from gestion.models import MetaPeriodo, Periodo


class ActividadForm(forms.ModelForm):
    """
    Registro de una actividad.

    Tres datos **no** están en el formulario y se ponen en la vista: el
    funcionario, la delegación y el período. Si viajaran en el formulario,
    bastaría con cambiarlos a mano para registrar a nombre de otra persona,
    en otra delegación o en un período cerrado.

    El selector de ítems tampoco ofrece todo el catálogo: solo los ítems que
    tienen meta para el cargo de quien registra. Registrar en un ítem que no
    te miden no suma a nada, y ofrecerlo solo invita a perder el tiempo.
    """

    class Meta:
        model = Actividad
        fields = ["item", "fecha", "cantidad", "accion", "detalle", "contacto"]
        widgets = {
            "fecha": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "cantidad": forms.NumberInput(attrs={"min": 1, "step": 1}),
            "accion": forms.TextInput(attrs={
                "placeholder": "En una línea: qué se hizo",
                "ancho": True,
            }),
            "detalle": forms.Textarea(attrs={
                "rows": 4, "ancho": True,
                "placeholder": "Qué se hizo, con quién y qué resultó",
            }),
            "contacto": forms.TextInput(attrs={
                "placeholder": "Con quién se coordinó. Opcional.",
            }),
        }

    def __init__(self, *args, perfil=None, periodo=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.perfil = perfil
        self.periodo = periodo

        # Se le ponen al objeto ANTES de validar, no al guardar. Django valida
        # el modelo en _post_clean(), y Actividad.clean() necesita el período
        # para comprobar que la fecha cae dentro: sin esto, la comprobación se
        # saltaba sola y aceptaba fechas de cualquier mes.
        if periodo is not None:
            self.instance.periodo = periodo
        if perfil is not None:
            self.instance.funcionario = perfil.usuario
            self.instance.delegacion = perfil.delegacion

        self.fields["fecha"].input_formats = ["%Y-%m-%d"]
        self.fields["item"].empty_label = "Elige el ítem al que suma"

        self.fields["item"].queryset = self._items_con_meta()

        # La unidad del ítem elegido cambia qué significa la cantidad, y eso
        # no se puede saber hasta que se elige. El texto deja claro que el
        # número va en la unidad del ítem, no en «actividades».
        self.fields["cantidad"].help_text = (
            "En la unidad del ítem. Si atendiste a 15 vecinos en una mesa, "
            "pon 15: la actividad es una, pero acredita quince."
        )

        if periodo is not None:
            self.fields["fecha"].help_text = (
                "Tiene que caer entre el %s y el %s, que es lo que dura «%s»."
                % (periodo.inicio.strftime("%d-%m-%Y"),
                   periodo.termino.strftime("%d-%m-%Y"), periodo.nombre)
            )

    def _items_con_meta(self):
        """Los ítems con meta para el cargo de esta persona en este período."""
        if self.perfil is None or self.periodo is None:
            return Item.objects.none()
        cargo = self.perfil.cargo_asignado
        if cargo is None:
            return Item.objects.none()
        return Item.objects.filter(
            activo=True,
            metas__periodo=self.periodo,
            metas__cargo=cargo,
            metas__activo=True,
        ).distinct()

    def clean_accion(self):
        texto = (self.cleaned_data["accion"] or "").strip()
        if len(texto) < 10:
            raise forms.ValidationError("Resume la acción en una frase entendible.")
        return texto

    def clean_detalle(self):
        texto = (self.cleaned_data["detalle"] or "").strip()
        if len(texto) < 25:
            raise forms.ValidationError(
                "El detalle es lo que lee el verificador para decidir. "
                "Escríbelo con lo que hace falta para entender qué pasó."
            )
        return texto

    def save(self, commit=True):
        # El funcionario, la delegación y el período ya quedaron puestos en
        # __init__, para que la validación del modelo los viera.
        actividad = super().save(commit=False)
        if not actividad.pk:
            actividad.codigo = proximo_codigo(Actividad, "ACT", ancho=4)
        if commit:
            actividad.save()
        return actividad


class EvidenciaForm(forms.ModelForm):
    """
    Carga de la evidencia de una actividad.

    Se guarda la referencia del documento, no el archivo: esta entrega no
    implementa subida. El código se asigna al crearla y no vuelve a cambiar.
    """

    class Meta:
        model = Evidencia
        fields = ["descripcion", "referencia"]
        widgets = {
            "descripcion": forms.TextInput(attrs={
                "placeholder": "Por ejemplo: Acta de la mesa de trabajo",
                "ancho": True,
            }),
            "referencia": forms.TextInput(attrs={
                "placeholder": "Nombre o número del documento",
            }),
        }

    def __init__(self, *args, actividad=None, autor=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.actividad = actividad
        self.autor = autor

    def clean_descripcion(self):
        texto = (self.cleaned_data["descripcion"] or "").strip()
        if len(texto) < 8:
            raise forms.ValidationError("Di qué es el documento y qué acredita.")
        return texto

    def save(self, commit=True):
        evidencia = super().save(commit=False)
        evidencia.actividad = self.actividad
        evidencia.autor = self.autor
        if not evidencia.pk:
            evidencia.codigo = proximo_codigo(Evidencia, "EVI", ancho=4)
        if commit:
            evidencia.save()
        return evidencia


class RechazoForm(forms.Form):
    """El motivo con el que un verificador devuelve una evidencia."""

    motivo = forms.CharField(
        label="Qué hay que corregir",
        widget=forms.Textarea(attrs={
            "class": "input", "rows": 3,
            "placeholder": "Explica qué falta o qué no corresponde",
        }),
        help_text="Lo lee quien registró la actividad, para corregir y volver a enviar.",
    )

    def clean_motivo(self):
        texto = (self.cleaned_data["motivo"] or "").strip()
        if len(texto) < 15:
            raise forms.ValidationError(
                "Un motivo de una palabra no le sirve a nadie. Explica qué corregir."
            )
        return texto

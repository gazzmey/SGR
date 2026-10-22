"""Formularios de actividades y evidencias."""

import os

from django import forms

from catalogos.models import Item
from comun.utilidades import proximo_codigo
from gestion import evidencias
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
            raise forms.ValidationError(f"Resume la acción en una frase entendible. Debe tener al menos 10 caracteres (escribiste {len(texto)}).")
        return texto

    def clean_detalle(self):
        texto = (self.cleaned_data["detalle"] or "").strip()
        if len(texto) < 25:
            raise forms.ValidationError(
                "El detalle es lo que lee el verificador para decidir. "
                f"Escríbelo con lo que hace falta para entender qué pasó. Debe tener al menos 25 caracteres (escribiste {len(texto)})."
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
    Carga de la evidencia de una actividad: el archivo y qué acredita.

    El archivo es obligatorio al cargar una evidencia nueva, aunque en el
    modelo no lo sea: las evidencias registradas antes de HU-09 no lo tienen y
    siguen siendo válidas. Las reglas del archivo están en
    ``gestion/evidencias.py``. El código se asigna al crearla y no vuelve a
    cambiar.
    """

    class Meta:
        model = Evidencia
        fields = ["archivo", "descripcion", "referencia"]
        widgets = {
            "archivo": forms.FileInput(attrs={"ancho": True}),
            "descripcion": forms.TextInput(attrs={
                "placeholder": "Por ejemplo: Acta de la mesa de trabajo",
                "ancho": True,
            }),
            "referencia": forms.TextInput(attrs={
                "placeholder": "Por ejemplo: Acta N° 14/2026",
            }),
        }

    def __init__(self, *args, actividad=None, autor=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.actividad = actividad
        self.autor = autor

        self.formatos_texto = evidencias.formatos_texto()
        self.maximo_mb = evidencias.maximo_mb()
        archivo = self.fields["archivo"]
        archivo.required = True
        archivo.label = "Archivo"
        archivo.widget.attrs["accept"] = evidencias.accept()
        archivo.help_text = (
            f"{self.formatos_texto}, hasta {self.maximo_mb} MB. Una foto del "
            f"celular o el PDF escaneado sirven."
        )
        archivo.error_messages["required"] = (
            f"Adjunta el archivo: {self.formatos_texto}, hasta {self.maximo_mb} MB."
        )
        # Los mensajes que trae Django dicen «fichero»: se reemplazan por los
        # del sistema.
        archivo.error_messages["empty"] = (
            "El archivo está vacío. Vuelve a elegirlo desde el original."
        )
        archivo.error_messages["invalid"] = (
            "No llegó un archivo. Vuelve a elegirlo y adjunta de nuevo."
        )
        # El nombre con que se guarda lo genera el sistema; el largo del
        # nombre original no importa.
        archivo.max_length = None

    def clean_archivo(self):
        archivo = self.cleaned_data.get("archivo")
        if archivo:
            evidencias.validar(archivo)
        return archivo

    def clean_descripcion(self):
        texto = (self.cleaned_data["descripcion"] or "").strip()
        if len(texto) < 8:
            raise forms.ValidationError(f"Di qué es el documento y qué acredita. Debe tener al menos 8 caracteres (escribiste {len(texto)}).")
        return texto

    def save(self, commit=True):
        evidencia = super().save(commit=False)
        evidencia.actividad = self.actividad
        evidencia.autor = self.autor
        archivo = self.cleaned_data.get("archivo")
        if archivo:
            # El nombre original solo se muestra y se usa al descargar. Si es
            # muy largo se corta antes de la extensión, para que el archivo
            # descargado siga abriéndose con el programa que corresponde.
            nombre = os.path.basename(archivo.name)
            if len(nombre) > 160:
                raiz, ext = os.path.splitext(nombre)
                nombre = raiz[:160 - len(ext)] + ext
            evidencia.nombre_original = nombre
            evidencia.tamano = archivo.size
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
                f"Un motivo de una palabra no le sirve a nadie. Explica qué corregir. Debe tener al menos 15 caracteres (escribiste {len(texto)})."
            )
        return texto

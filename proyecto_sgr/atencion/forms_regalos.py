"""Formularios de las campañas de regalos y de la inscripción de un niño."""

from django import forms
from django.urls import reverse_lazy
from django.utils import timezone

from atencion.modelos_regalos import CampanaRegalos, InscripcionRegalo
from atencion.models import Solicitante, limpiar_rut, rut_valido
from comun.utilidades import proximo_codigo

FECHA = forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")


class CampanaForm(forms.ModelForm):
    class Meta:
        model = CampanaRegalos
        fields = ["evento", "anio", "edad_maxima", "inscripcion_hasta",
                  "fecha_entrega", "observacion"]
        widgets = {
            "anio": forms.NumberInput(attrs={"min": 2020, "max": 2100, "step": 1}),
            "edad_maxima": forms.NumberInput(attrs={"min": 1, "max": 17, "step": 1}),
            "inscripcion_hasta": FECHA,
            "fecha_entrega": FECHA,
            "observacion": forms.Textarea(attrs={
                "rows": 3, "ancho": True,
                "placeholder": "Dónde se entregan, qué se entrega por tramo, a quién llamar",
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in ("inscripcion_hasta", "fecha_entrega"):
            self.fields[campo].input_formats = ["%Y-%m-%d"]
        self.fields["evento"].choices = (
            [("", "Elige el evento")] + list(CampanaRegalos.Evento.choices))
        if not self.instance.pk:
            self.initial.setdefault("anio", timezone.localdate().year)

    def save(self, commit=True):
        campana = super().save(commit=False)
        if not campana.pk:
            campana.codigo = proximo_codigo(CampanaRegalos, "CRG")
        if commit:
            campana.save()
        return campana


class InscripcionForm(forms.ModelForm):
    """
    Inscribe a un niño en una campaña.

    El adulto se busca por RUT y, si no existe, se crea su ficha: es la
    misma ficha de atención ciudadana, así que una persona ya atendida no se
    vuelve a escribir. La delegación no viaja en el formulario: es la activa.
    """

    rut_apoderado = forms.CharField(
        label="RUT del adulto", max_length=12,
        widget=forms.TextInput(attrs={
            "class": "input mono", "placeholder": "12.345.678-5", "autocomplete": "off",
            "data-buscar-rut": reverse_lazy("atencion:buscar_solicitante"),
        }),
        help_text="Madre, padre o quien tenga su cuidado. Si ya fue atendido, se reutiliza su ficha.",
    )
    nombre_apoderado = forms.CharField(
        label="Nombre del adulto", max_length=120,
        widget=forms.TextInput(attrs={"class": "input", "autocomplete": "off",
                                      "data-rut-nombre": "1"}),
    )
    telefono_apoderado = forms.CharField(
        label="Teléfono del adulto", max_length=20, required=False,
        widget=forms.TextInput(attrs={"class": "input", "inputmode": "tel",
                                      "placeholder": "9 1234 5678", "data-rut-telefono": "1"}),
        help_text="Para avisarle cuándo y dónde retirar el regalo.",
    )

    class Meta:
        model = InscripcionRegalo
        fields = ["campana", "rut_menor", "tramo_edad"]
        widgets = {
            "rut_menor": forms.TextInput(attrs={
                "class": "input mono", "placeholder": "12.345.678-5", "autocomplete": "off",
            }),
        }

    def __init__(self, *args, delegacion=None, usuario=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.delegacion = delegacion
        self.usuario = usuario
        if delegacion is not None and not self.instance.pk:
            self.instance.delegacion = delegacion

        hoy = timezone.localdate()
        abiertas = [c.pk for c in CampanaRegalos.objects.filter(activo=True) if c.abierta(hoy)]
        if self.instance.pk:
            # Al corregir una inscripción, su campaña sigue ofreciéndose
            # aunque ya haya cerrado: si no, el formulario no se podría guardar.
            abiertas.append(self.instance.campana_id)
        self.fields["campana"].queryset = CampanaRegalos.objects.filter(pk__in=abiertas)
        self.fields["campana"].empty_label = "Elige la campaña"
        if len(abiertas) == 1 and not self.instance.pk:
            self.initial.setdefault("campana", abiertas[0])
        self.fields["tramo_edad"].choices = (
            [("", "Elige el tramo")] + list(InscripcionRegalo.Tramo.choices))

        if self.instance.pk and self.instance.apoderado_id:
            apoderado = self.instance.apoderado
            self.initial.setdefault("rut_apoderado", apoderado.rut)
            self.initial.setdefault("nombre_apoderado", apoderado.nombre)
            self.initial.setdefault("telefono_apoderado", apoderado.telefono)

    def clean_rut_menor(self):
        valor = limpiar_rut(self.cleaned_data.get("rut_menor"))
        if not rut_valido(valor):
            raise forms.ValidationError(
                "Ese RUT no es válido: revisa el número y el dígito verificador.")
        return valor

    def clean_rut_apoderado(self):
        valor = limpiar_rut(self.cleaned_data.get("rut_apoderado"))
        if not rut_valido(valor):
            raise forms.ValidationError(
                "Ese RUT no es válido: revisa el número y el dígito verificador.")
        return valor

    def clean_nombre_apoderado(self):
        nombre = (self.cleaned_data.get("nombre_apoderado") or "").strip()
        if len(nombre) < 5:
            raise forms.ValidationError("Escribe el nombre completo del adulto.")
        return nombre

    def clean(self):
        datos = super().clean()
        rut = datos.get("rut_apoderado")
        if rut:
            # Se busca —sin crear todavía— para que el modelo pueda comparar
            # el RUT del niño con el del adulto al validar.
            apoderado = Solicitante.objects.filter(rut=rut).first()
            if apoderado is None:
                apoderado = Solicitante(rut=rut, nombre=datos.get("nombre_apoderado", ""),
                                        telefono=datos.get("telefono_apoderado", ""))
            self._apoderado = apoderado
            self.instance.apoderado = apoderado if apoderado.pk else None
            if not apoderado.pk and limpiar_rut(datos.get("rut_menor")) == rut:
                self.add_error("rut_menor", "Es el mismo RUT del adulto que lo inscribe.")
        return datos

    def save(self, commit=True):
        apoderado = self._apoderado
        if not apoderado.pk:
            apoderado.save()
        elif not apoderado.telefono and self.cleaned_data.get("telefono_apoderado"):
            apoderado.telefono = self.cleaned_data["telefono_apoderado"]
            apoderado.save(update_fields=["telefono"])
        inscripcion = super().save(commit=False)
        inscripcion.apoderado = apoderado
        if not inscripcion.pk:
            inscripcion.codigo = proximo_codigo(InscripcionRegalo, "REG", ancho=4)
            inscripcion.registrado_por = self.usuario
        if commit:
            inscripcion.save()
        return inscripcion

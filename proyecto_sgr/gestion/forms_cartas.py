"""Formulario del tubo de cartas de oficina de partes."""

from django import forms
from django.contrib.auth.models import User

from comun.utilidades import proximo_codigo
from gestion.modelos_cartas import Carta

FECHA = forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")


class CartaForm(forms.ModelForm):
    """
    Ingreso y seguimiento de una carta.

    La delegación no está en el formulario: es la activa al ingresarla y no
    cambia después. El encargado se elige entre las personas activas de esa
    delegación.
    """

    class Meta:
        model = Carta
        fields = [
            "fecha", "numero", "dirigida_a", "remitente", "tema",
            "fecha_actividad", "responsable", "estado", "derivada_a",
            "pronunciamiento", "observacion",
        ]
        widgets = {
            "fecha": FECHA,
            "fecha_actividad": FECHA,
            "dirigida_a": forms.TextInput(attrs={"placeholder": "Por ejemplo: Delegado municipal"}),
            "remitente": forms.TextInput(attrs={"placeholder": "Junta de vecinos, club, vecino o vecina"}),
            "numero": forms.TextInput(attrs={"placeholder": "Opcional"}),
            "tema": forms.Textarea(attrs={"rows": 3, "ancho": True,
                                          "placeholder": "Qué pide o informa la carta"}),
            "derivada_a": forms.TextInput(attrs={"placeholder": "Por ejemplo: Patentes, Tránsito"}),
            "pronunciamiento": forms.Textarea(attrs={"rows": 3, "ancho": True,
                                                     "placeholder": "Qué se respondió o resolvió"}),
            "observacion": forms.Textarea(attrs={"rows": 2, "ancho": True,
                                                 "placeholder": "Opcional"}),
        }

    def __init__(self, *args, delegacion=None, usuario=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.usuario = usuario
        if delegacion is not None and not self.instance.pk:
            self.instance.delegacion = delegacion
        dele = delegacion if not self.instance.pk else self.instance.delegacion

        for campo in ("fecha", "fecha_actividad"):
            self.fields[campo].input_formats = ["%Y-%m-%d"]

        gente = User.objects.none()
        if dele is not None:
            gente = (
                User.objects
                .filter(is_active=True, perfil__activo=True, perfil__delegacion=dele)
                .order_by("first_name", "last_name")
            )
        self.fields["responsable"].queryset = gente
        self.fields["responsable"].empty_label = "Elige a quién la sigue"
        self.fields["responsable"].label_from_instance = (
            lambda u: u.get_full_name() or u.get_username()
        )
        if not self.instance.pk and usuario is not None and gente.filter(pk=usuario.pk).exists():
            self.initial.setdefault("responsable", usuario.pk)

    def clean_tema(self):
        texto = (self.cleaned_data.get("tema") or "").strip()
        if len(texto) < 10:
            raise forms.ValidationError(
                "Escribe de qué trata la carta: al menos 10 caracteres "
                f"(escribiste {len(texto)})."
            )
        return texto

    def save(self, commit=True):
        carta = super().save(commit=False)
        if not carta.pk:
            carta.codigo = proximo_codigo(Carta, "CTA", ancho=3)
            if self.usuario is not None and self.usuario.is_authenticated:
                carta.registrada_por = self.usuario
        if commit:
            carta.save()
        return carta

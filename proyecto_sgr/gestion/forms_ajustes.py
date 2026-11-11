"""
Formularios de felicitaciones, reclamos y ausencias.

Los dos limitan a quién se puede elegir: solo personas activas de las
delegaciones que el perfil autoriza. La lista llega desde la vista, que es la
que conoce el alcance; si el formulario ofreciera a todo el municipio, un
delegado podría restarle puntos a alguien de otra delegación.
"""

from django import forms
from django.contrib.auth.models import User

from comun.utilidades import proximo_codigo
from gestion.modelos_ajustes import Ausencia, Reconocimiento
from gestion.models import Periodo
from organizacion.models import Delegacion

FECHA = forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")


def _gente(permitidas):
    """Las personas activas con perfil, dentro del alcance."""
    consulta = User.objects.filter(is_active=True, perfil__activo=True)
    if permitidas is not None:
        consulta = consulta.filter(perfil__delegacion_id__in=permitidas)
    return consulta.select_related("perfil__delegacion").order_by(
        "first_name", "last_name"
    )


def _rotulo_persona(usuario):
    nombre = usuario.get_full_name() or usuario.get_username()
    perfil = getattr(usuario, "perfil", None)
    if perfil is not None and perfil.delegacion_id:
        return f"{nombre} · {perfil.delegacion.nombre}"
    return nombre


class ReconocimientoForm(forms.ModelForm):
    """Ingreso de una felicitación o de un reclamo."""

    class Meta:
        model = Reconocimiento
        fields = [
            "tipo", "funcionario", "periodo", "fecha", "medio",
            "presentado_por", "situacion", "respaldo", "informado_a",
        ]
        widgets = {
            "fecha": FECHA,
            "presentado_por": forms.TextInput(attrs={
                "placeholder": "Por ejemplo: JJVV Villa El Indio o el nombre de la vecina",
            }),
            "situacion": forms.Textarea(attrs={
                "rows": 3, "ancho": True,
                "placeholder": "Qué pasó, en pocas líneas",
            }),
            "respaldo": forms.TextInput(attrs={
                "placeholder": "Asunto y fecha del correo, captura o página del libro",
                "ancho": True,
            }),
            "informado_a": forms.TextInput(attrs={
                "placeholder": "Opcional",
            }),
        }

    def __init__(self, *args, permitidas=None, usuario=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.usuario = usuario
        self.fields["fecha"].input_formats = ["%Y-%m-%d"]

        self.fields["tipo"].choices = (
            [("", "Elige felicitación o reclamo")] + list(Reconocimiento.Tipo.choices))
        self.fields["medio"].choices = (
            [("", "Elige por dónde llegó")] + list(Reconocimiento.Medio.choices))
        self.fields["funcionario"].queryset = _gente(permitidas)
        self.fields["funcionario"].empty_label = "Elige a la persona"
        self.fields["funcionario"].label_from_instance = _rotulo_persona

        periodos = Periodo.objects.filter(activo=True).exclude(
            estado=Periodo.Estado.CERRADO
        ).order_by("-inicio")
        self.fields["periodo"].queryset = periodos
        self.fields["periodo"].empty_label = "Elige el período"
        if not self.instance.pk and not self.initial.get("periodo"):
            abierto = periodos.filter(estado=Periodo.Estado.ABIERTO).first()
            if abierto is not None:
                self.initial["periodo"] = abierto.pk

    def clean_situacion(self):
        texto = (self.cleaned_data.get("situacion") or "").strip()
        if len(texto) < 15:
            raise forms.ValidationError(
                "Describe la situación: es lo que se lee cuando alguien "
                "pregunta por qué cambió el resultado. Al menos 15 caracteres "
                f"(escribiste {len(texto)})."
            )
        return texto

    def clean_respaldo(self):
        texto = (self.cleaned_data.get("respaldo") or "").strip()
        if len(texto) < 5:
            raise forms.ValidationError(
                "La matriz solo acepta lo que consta por escrito. Indica dónde "
                "está el escrito."
            )
        return texto

    def clean(self):
        datos = super().clean()
        # La delegación no se elige: es la de la persona. Se pone antes de
        # validar el modelo, que es cuando Django corre su clean().
        funcionario = datos.get("funcionario")
        perfil = getattr(funcionario, "perfil", None) if funcionario else None
        if perfil is not None:
            self.instance.delegacion_id = perfil.delegacion_id
        return datos

    def save(self, commit=True):
        registro = super().save(commit=False)
        if not registro.pk:
            prefijo = "REC" if registro.tipo == Reconocimiento.Tipo.RECLAMO else "FEL"
            registro.codigo = proximo_codigo(Reconocimiento, prefijo, ancho=3)
            if self.usuario is not None and self.usuario.is_authenticated:
                registro.registrado_por = self.usuario
        if commit:
            registro.save()
        return registro


class AusenciaForm(forms.ModelForm):
    """Ingreso de una ausencia, de una persona o de toda la delegación."""

    class Meta:
        model = Ausencia
        fields = ["delegacion", "funcionario", "tipo", "desde", "hasta", "observacion"]
        widgets = {
            "desde": FECHA,
            "hasta": FECHA,
            "observacion": forms.TextInput(attrs={
                "placeholder": "Opcional. Sin diagnósticos.",
                "ancho": True,
            }),
        }

    def __init__(self, *args, permitidas=None, usuario=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.usuario = usuario
        for campo in ("desde", "hasta"):
            self.fields[campo].input_formats = ["%Y-%m-%d"]

        delegaciones = Delegacion.objects.filter(activo=True).order_by("nombre")
        if permitidas is not None:
            delegaciones = delegaciones.filter(pk__in=permitidas)
        self.fields["delegacion"].queryset = delegaciones
        self.fields["delegacion"].empty_label = "Elige la delegación"
        if not self.instance.pk and delegaciones.count() == 1:
            self.initial.setdefault("delegacion", delegaciones.first().pk)

        self.fields["tipo"].choices = (
            [("", "Elige el tipo de ausencia")] + list(Ausencia.Tipo.choices))
        self.fields["funcionario"].queryset = _gente(permitidas)
        self.fields["funcionario"].required = False
        self.fields["funcionario"].empty_label = "Toda la delegación"
        self.fields["funcionario"].label_from_instance = _rotulo_persona

    def save(self, commit=True):
        registro = super().save(commit=False)
        if not registro.pk:
            registro.codigo = proximo_codigo(Ausencia, "AUS", ancho=3)
            if self.usuario is not None and self.usuario.is_authenticated:
                registro.registrado_por = self.usuario
        if commit:
            registro.save()
        return registro

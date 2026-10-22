"""Formularios de la agenda: ingreso, cambio de estado y reasignación."""

from django import forms
from django.contrib.auth.models import User

from catalogos.models import Item
from comun.utilidades import proximo_codigo
from gestion.modelos_agenda import Compromiso


class CompromisoForm(forms.ModelForm):
    """
    Ingreso de un compromiso.

    La delegación, el período y el responsable original **no** están en el
    formulario: se ponen en la vista. Si viajaran en el formulario, bastaría
    con cambiarlos a mano para ingresar un compromiso en otra delegación o en
    un período cerrado.

    El responsable sí se elige, porque el punto del módulo es justamente que
    un compromiso puede quedar a nombre de otra persona de la delegación. Lo
    que se limita es *entre quiénes*: solo personas activas de esa delegación.
    """

    class Meta:
        model = Compromiso
        fields = [
            "solicitante", "territorio", "descripcion",
            "responsable", "apoyo", "vencimiento",
            "item", "requiere_validacion",
        ]
        widgets = {
            "solicitante": forms.TextInput(attrs={
                "placeholder": "Junta de vecinos, persona u unidad que lo pidió",
                "ancho": True,
            }),
            "territorio": forms.TextInput(attrs={
                "placeholder": "Por ejemplo: Unidad vecinal 3 · San Juan",
            }),
            "descripcion": forms.Textarea(attrs={
                "rows": 4, "ancho": True,
                "placeholder": "Qué se comprometió exactamente",
            }),
            "apoyo": forms.TextInput(attrs={
                "placeholder": "Quién más participa. Opcional.",
            }),
            "vencimiento": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        }

    def __init__(self, *args, perfil=None, periodo=None, delegacion=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.perfil = perfil
        self.periodo = periodo
        self.delegacion = delegacion or getattr(perfil, "delegacion", None)

        # Igual que en el formulario de actividad: se le ponen al objeto antes
        # de validar, no al guardar. Django valida el modelo en
        # ``_post_clean()``, y ``Compromiso.clean()`` necesita el período para
        # comprobar que no esté cerrado. Puestos en ``save()``, esa
        # comprobación se saltaría sola.
        if self.periodo is not None:
            self.instance.periodo = self.periodo
        if self.delegacion is not None:
            self.instance.delegacion = self.delegacion

        self.fields["vencimiento"].input_formats = ["%Y-%m-%d"]
        self.fields["responsable"].queryset = self._gente_de_la_delegacion()
        self.fields["responsable"].empty_label = "Elige al responsable"
        self.fields["responsable"].label_from_instance = (
            lambda u: u.get_full_name() or u.get_username()
        )
        self.fields["item"].queryset = Item.objects.filter(activo=True)
        self.fields["item"].empty_label = "No alimenta ninguna meta"
        self.fields["item"].required = False

        if self.periodo is not None:
            self.fields["vencimiento"].help_text = (
                "El período «%s» va del %s al %s. El vencimiento puede caer "
                "después: un compromiso con plazo largo sigue siendo de este "
                "período." % (
                    self.periodo.nombre,
                    self.periodo.inicio.strftime("%d-%m-%Y"),
                    self.periodo.termino.strftime("%d-%m-%Y"),
                )
            )

    def _gente_de_la_delegacion(self):
        """Las personas activas de la delegación, para elegir responsable."""
        if self.delegacion is None:
            return User.objects.none()
        return (
            User.objects
            .filter(is_active=True, perfil__activo=True,
                    perfil__delegacion=self.delegacion)
            .order_by("first_name", "last_name")
            .distinct()
        )

    def clean_descripcion(self):
        texto = (self.cleaned_data["descripcion"] or "").strip()
        if len(texto) < 20:
            raise forms.ValidationError(
                "La descripción es contra lo que se cierra el compromiso. "
                f"Escríbela con lo que hace falta para saber si se cumplió. Debe tener al menos 20 caracteres (escribiste {len(texto)})."
            )
        return texto

    def save(self, commit=True):
        compromiso = super().save(commit=False)
        if not compromiso.pk:
            compromiso.codigo = proximo_codigo(Compromiso, "CMP", ancho=4)
            # Se escribe una sola vez y no vuelve a cambiar: después de una
            # reasignación es lo único que dice de quién venía (AGE-06).
            compromiso.responsable_original = compromiso.responsable
        if commit:
            compromiso.save()
        return compromiso


class TransicionForm(forms.Form):
    """La observación con que se registra un cambio de estado."""

    observacion = forms.CharField(
        label="Observación",
        required=False,
        widget=forms.Textarea(attrs={
            "class": "input", "rows": 3,
            "placeholder": "Qué se hizo o por qué cambia de estado",
        }),
        help_text="Queda en el historial del compromiso, junto al antes y el después.",
    )

    def __init__(self, *args, exige_observacion=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.exige_observacion = exige_observacion
        if exige_observacion:
            self.fields["observacion"].required = True
            self.fields["observacion"].help_text = (
                "Obligatoria en este paso: anular cierra el compromiso sin "
                "cumplirlo, y tiene que quedar escrito por qué."
            )

    def clean_observacion(self):
        texto = (self.cleaned_data.get("observacion") or "").strip()
        if self.exige_observacion and len(texto) < 15:
            raise forms.ValidationError(
                "Explica el motivo. Una palabra no le sirve a quien lea el "
                f"historial dentro de tres meses. Debe tener al menos 15 caracteres (escribiste {len(texto)})."
            )
        return texto


class ReasignarForm(forms.Form):
    """
    El cambio de responsable, con su motivo.

    El motivo es obligatorio: una reasignación sin explicación deja la agenda
    con un responsable nuevo y sin saber por qué dejó de ser del anterior, que
    es justo lo que el caso AGE-06 pide poder auditar.
    """

    responsable = forms.ModelChoiceField(
        label="Nuevo responsable",
        queryset=User.objects.none(),
        empty_label="Elige a quién pasa",
    )
    motivo = forms.CharField(
        label="Por qué se reasigna",
        widget=forms.Textarea(attrs={
            "class": "input", "rows": 3,
            "placeholder": "Por ejemplo: el responsable está con licencia hasta fin de mes",
        }),
    )

    def __init__(self, *args, compromiso=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.compromiso = compromiso
        if compromiso is not None:
            self.fields["responsable"].queryset = (
                User.objects
                .filter(is_active=True, perfil__activo=True,
                        perfil__delegacion=compromiso.delegacion)
                .exclude(pk=compromiso.responsable_id)
                .order_by("first_name", "last_name")
                .distinct()
            )
            self.fields["responsable"].label_from_instance = (
                lambda u: u.get_full_name() or u.get_username()
            )

    def clean_motivo(self):
        texto = (self.cleaned_data["motivo"] or "").strip()
        if len(texto) < 15:
            raise forms.ValidationError(
                f"Anota el motivo con algo que se entienda después. Debe tener al menos 15 caracteres (escribiste {len(texto)})."
            )
        return texto

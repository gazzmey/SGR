"""
Formularios de ítems, tipos de atención y subatenciones.

Sobre la meta y el ponderador del ítem: son valores **sugeridos**, los que se
proponen al asignar el ítem a un cargo. El peso que usa el cálculo se define
por período y cargo en ``MetaPeriodo``, y la regla del 100 % vive allí, donde
de verdad importa: los ponderadores de cada cargo suman 100 % en cada
período. Los ítems del catálogo no se suman entre sí, así que aquí no se
exige ningún total.
"""

from django import forms

from catalogos.models import Item, SubAtencion, TipoAtencion
from comun.nombres import NombreSinRepetir
from comun.utilidades import proximo_codigo


class _Base(NombreSinRepetir, forms.ModelForm):
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


def _fijar_nombre_si_hay_atenciones(form, cuantas, que):
    """
    DEF-02: el nombre de un tipo o subtipo con atenciones registradas ya no
    se cambia. Las atenciones guardan el vínculo, no una copia del nombre;
    si el nombre cambiara, las anteriores se leerían con un nombre que no
    existía cuando se registraron. La descripción sí se puede corregir.

    El campo queda deshabilitado: el navegador no lo envía y, si alguien lo
    envía igual, Django usa el valor guardado.
    """
    if not cuantas:
        return
    campo = form.fields["nombre"]
    campo.disabled = True
    campo.help_text = (
        f"Ya {'hay 1 atención registrada' if cuantas == 1 else f'hay {cuantas} atenciones registradas'} "
        f"con {que}: el nombre no se cambia para no alterar cómo se leen. Puedes corregir la "
        "descripción; si cambió el sentido, crea uno nuevo y desactiva este cuando cierre el período."
    )


# =========================================================================
# Ítems
# =========================================================================


class ItemForm(_Base):
    prefijo = "ITM"

    class Meta:
        model = Item
        fields = [
            "codigo", "nombre", "area", "descripcion",
            "medicion", "unidad", "requiere_evidencia", "evidencia_requerida",
        ]
        widgets = {
            "nombre": forms.TextInput(attrs={
                "placeholder": "Por ejemplo: Atenciones de orientación social",
            }),
            "descripcion": forms.Textarea(attrs={
                "rows": 4, "ancho": True,
                "placeholder": "Qué cuenta como registro válido para este ítem",
            }),
            "evidencia_requerida": forms.TextInput(attrs={
                "placeholder": "Por ejemplo: acta firmada y fotografía", "ancho": True,
            }),
        }
        labels = {"area": "Área", "medicion": "Tipo (cómo se mide)"}

    def clean_descripcion(self):
        texto = (self.cleaned_data.get("descripcion") or "").strip()
        if len(texto) < 20:
            raise forms.ValidationError(
                "Explica qué cuenta como registro válido. Es lo que evita "
                f"discusiones al cerrar el período. Debe tener al menos 20 caracteres (escribiste {len(texto)})."
            )
        return texto

    def clean_evidencia_requerida(self):
        return (self.cleaned_data.get("evidencia_requerida") or "").strip()

    def clean(self):
        datos = super().clean()
        if datos.get("requiere_evidencia") and not datos.get("evidencia_requerida"):
            self.add_error("evidencia_requerida",
                           "Si la meta requiere evidencia, indica cuál: es lo que el "
                           "verificador va a exigir.")
        return datos


# =========================================================================
# Tipos de atención
# =========================================================================


class TipoAtencionForm(_Base):
    prefijo = "TAT"

    class Meta:
        model = TipoAtencion
        fields = ["codigo", "nombre", "area", "descripcion"]
        widgets = {
            "nombre": forms.TextInput(attrs={
                "placeholder": "Por ejemplo: Orientación social",
            }),
            "descripcion": forms.Textarea(attrs={
                "rows": 4, "ancho": True,
                "placeholder": "Qué requerimientos entran en esta clasificación",
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        campo = self.fields["descripcion"]
        campo.required = True
        campo.help_text = "Mínimo 20 caracteres: qué requerimientos entran en esta clasificación."
        campo.error_messages["required"] = (
            "La descripción es obligatoria y debe tener al menos 20 caracteres."
        )
        if self.instance.pk:
            from atencion.models import Atencion

            _fijar_nombre_si_hay_atenciones(
                self, Atencion.objects.filter(subatencion__tipo_atencion=self.instance).count(),
                "este tipo")

    def clean_descripcion(self):
        texto = (self.cleaned_data.get("descripcion") or "").strip()
        if len(texto) < 20:
            raise forms.ValidationError(
                f"La descripción debe tener al menos 20 caracteres; la que escribiste tiene {len(texto)}."
            )
        return texto


# =========================================================================
# Subatenciones
# =========================================================================


class SubAtencionForm(_Base):
    prefijo = "SAT"

    class Meta:
        model = SubAtencion
        fields = [
            "codigo", "tipo_atencion", "nombre",
            "descripcion", "documento",
        ]
        widgets = {
            "nombre": forms.TextInput(attrs={
                "placeholder": "Por ejemplo: Informe social para postulación",
            }),
            "descripcion": forms.Textarea(attrs={
                "rows": 4, "ancho": True,
                "placeholder": "Qué incluye, qué requisitos tiene y cómo se resuelve",
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Solo tipos activos, más el que ya tenga el registro que se edita.
        consulta = TipoAtencion.objects.filter(activo=True)
        actual = getattr(self.instance, "tipo_atencion_id", None)
        if actual:
            from django.db.models import Q

            consulta = TipoAtencion.objects.filter(Q(activo=True) | Q(pk=actual))
        self.fields["tipo_atencion"].queryset = consulta
        self.fields["tipo_atencion"].empty_label = "Elige el tipo al que pertenece"
        campo = self.fields["descripcion"]
        campo.required = True
        campo.help_text = "Mínimo 20 caracteres: qué incluye, qué requisitos tiene y cómo se resuelve."
        campo.error_messages["required"] = "La descripción es obligatoria y debe tener al menos 20 caracteres."
        if self.instance.pk:
            _fijar_nombre_si_hay_atenciones(self, self.instance.atenciones.count(), "este subtipo")

    def clean_descripcion(self):
        texto = (self.cleaned_data.get("descripcion") or "").strip()
        if len(texto) < 20:
            raise forms.ValidationError(
                f"La descripción debe tener al menos 20 caracteres; la que escribiste tiene {len(texto)}."
            )
        return texto


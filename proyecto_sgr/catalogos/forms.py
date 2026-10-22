"""
Formularios de ítems, tipos de atención y subatenciones.

La regla interesante de este archivo es la de los ponderadores: los ítems
activos tienen que sumar 100 %. No se impone con una restricción de base de
datos porque mientras se configura el período la suma pasa necesariamente por
valores intermedios; se avisa al guardar y se muestra cuánto falta.
"""

from django import forms

from catalogos.models import Item, SubAtencion, TipoAtencion
from comun.utilidades import proximo_codigo, suma_ponderadores


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
# Ítems
# =========================================================================


class ItemForm(_Base):
    prefijo = "ITM"

    class Meta:
        model = Item
        fields = [
            "codigo", "nombre", "area", "descripcion",
            "unidad", "meta", "ponderador",
        ]
        widgets = {
            "nombre": forms.TextInput(attrs={
                "placeholder": "Por ejemplo: Atenciones de orientación social",
            }),
            "descripcion": forms.Textarea(attrs={
                "rows": 4, "ancho": True,
                "placeholder": "Qué cuenta como registro válido para este ítem",
            }),
            "meta": forms.NumberInput(attrs={"min": 1, "step": 1}),
            "ponderador": forms.NumberInput(attrs={"min": 0, "max": 100, "step": 1}),
        }

    def clean_descripcion(self):
        texto = (self.cleaned_data.get("descripcion") or "").strip()
        if len(texto) < 20:
            raise forms.ValidationError(
                "Explica qué cuenta como registro válido. Es lo que evita "
                f"discusiones al cerrar el período. Debe tener al menos 20 caracteres (escribiste {len(texto)})."
            )
        return texto

    def clean_meta(self):
        """
        La meta tiene que ser mayor que cero.

        El validador del modelo ya lo exige —vale desde el administrador y
        desde cualquier script—; aquí se repite el mensaje para que explique
        el porqué en la pantalla donde se escribe el número.
        """
        meta = self.cleaned_data.get("meta")
        if meta is not None and meta < 1:
            raise forms.ValidationError(
                "La meta tiene que ser mayor que cero: con meta cero no se "
                "puede calcular el cumplimiento."
            )
        return meta

    def clean_ponderador(self):
        valor = self.cleaned_data.get("ponderador") or 0
        if valor > 100:
            raise forms.ValidationError("Un ponderador no puede pasar de 100 %.")
        return valor

    def clean(self):
        """
        Avisa si los ítems activos se pasan del 100 %.

        Pasarse es un error y no se guarda: el resultado del período se
        calcularía sobre una base que no es 100. Quedarse corto, en cambio,
        es un estado normal mientras se configura, así que solo se informa
        en el listado.
        """
        datos = super().clean()
        ponderador = datos.get("ponderador") or 0
        otros = suma_ponderadores(Item, excluir_pk=self.instance.pk)
        total = otros + ponderador
        if total > 100:
            self.add_error("ponderador", forms.ValidationError(
                "Los demás ítems activos ya suman %(otros)d %%. Con este "
                "quedarían en %(total)d %%, y el máximo es 100 %%. Puedes "
                "usar hasta %(libre)d %%.",
                params={"otros": otros, "total": total, "libre": 100 - otros},
            ))
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

    def clean_descripcion(self):
        texto = (self.cleaned_data.get("descripcion") or "").strip()
        if len(texto) < 20:
            raise forms.ValidationError(
                f"La descripción debe tener al menos 20 caracteres; la que escribiste tiene {len(texto)}."
            )
        return texto


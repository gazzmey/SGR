"""Formularios de períodos, cargos y metas."""

from django import forms
from django.db import models

from catalogos.models import Item
from comun.utilidades import proximo_codigo
from gestion.models import Cargo, MetaPeriodo, Periodo
from gestion.reglas import ReglaCalculo


class _Base(forms.ModelForm):
    """El código se asigna solo y no se escribe a mano."""

    prefijo = ""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "codigo" in self.fields:
            self.fields["codigo"].disabled = True
            self.fields["codigo"].required = False
            if not self.instance.pk:
                self.initial["codigo"] = proximo_codigo(self._meta.model, self.prefijo)
            self.fields["codigo"].help_text = (
                "Asignado al crear. No se puede cambiar: lo usan los informes "
                "y la auditoría."
            )

    def save(self, commit=True):
        objeto = super().save(commit=False)
        if not objeto.pk and not objeto.codigo.startswith(f"{self.prefijo}-"):
            objeto.codigo = proximo_codigo(self._meta.model, self.prefijo)
        if commit:
            objeto.save()
            self.save_m2m()
        return objeto


class PeriodoForm(_Base):
    prefijo = "PER"

    class Meta:
        model = Periodo
        fields = ["codigo", "nombre", "inicio", "termino", "observacion"]
        widgets = {
            "nombre": forms.TextInput(attrs={"placeholder": "Por ejemplo: Jul – Sep 2026"}),
            "inicio": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "termino": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "observacion": forms.Textarea(attrs={
                "rows": 3, "ancho": True,
                "placeholder": "Opcional. Queda en el historial del período.",
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # El navegador entrega las fechas en ISO; sin esto, al editar se
        # muestran en otro formato y el campo aparece vacío.
        for campo in ("inicio", "termino"):
            self.fields[campo].input_formats = ["%Y-%m-%d"]

    def clean_nombre(self):
        nombre = (self.cleaned_data["nombre"] or "").strip()
        if len(nombre) < 4:
            raise forms.ValidationError("Ponle un nombre reconocible en un informe.")
        return nombre


class CargoForm(_Base):
    prefijo = "CAR"

    class Meta:
        model = Cargo
        fields = ["codigo", "nombre", "descripcion"]
        widgets = {
            "nombre": forms.TextInput(attrs={"placeholder": "Por ejemplo: Encargado territorial"}),
            "descripcion": forms.Textarea(attrs={
                "rows": 3, "ancho": True,
                "placeholder": "Qué hace quien ocupa el cargo y con qué se le mide",
            }),
        }

    def clean_descripcion(self):
        texto = (self.cleaned_data.get("descripcion") or "").strip()
        if len(texto) < 20:
            raise forms.ValidationError(
                "Describe el cargo: es lo que explica por qué se le mide con "
                f"unos ítems y no con otros. Debe tener al menos 20 caracteres (escribiste {len(texto)})."
            )
        return texto


class MetaPeriodoForm(forms.ModelForm):
    """
    Una meta es el cruce de período, cargo e ítem.

    Al crear desde el listado filtrado, el período y el cargo llegan
    preseleccionados: así se configura un cargo completo sin volver a
    elegirlos en cada fila.
    """

    class Meta:
        model = MetaPeriodo
        fields = ["periodo", "cargo", "item", "meta", "ponderador"]
        widgets = {
            "meta": forms.NumberInput(attrs={"min": 1, "step": 1}),
            "ponderador": forms.NumberInput(attrs={"min": 0, "max": 100, "step": 1}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        editando = self.instance.pk is not None

        # Al crear solo se ofrecen períodos no cerrados: los cerrados
        # conservan las reglas con las que se midió.
        #
        # Al editar, en cambio, el período de esta meta tiene que seguir
        # apareciendo aunque esté cerrado. Si no aparece, el selector sale
        # vacío, la validación reclama el campo obligatorio, y «arreglarlo»
        # eligiendo otro período **mueve la meta de un período a otro**:
        # el cerrado pierde una de las reglas con que se midió y el abierto
        # gana una que nunca tuvo. Los dos resultados quedan mal, y sin
        # ningún aviso.
        disponibles = Periodo.objects.filter(activo=True).exclude(
            estado=Periodo.Estado.CERRADO,
        )
        if editando and self.instance.periodo_id:
            disponibles = Periodo.objects.filter(
                models.Q(pk=self.instance.periodo_id)
                | models.Q(activo=True, estado__in=[
                    Periodo.Estado.BORRADOR, Periodo.Estado.ABIERTO,
                ])
            )
        self.fields["periodo"].queryset = disponibles.distinct()

        # Igual con el cargo y el ítem: si se desactivaron después de crear
        # la meta, tienen que seguir viéndose en la ficha que ya los usa.
        self.fields["cargo"].queryset = self._con_el_actual(
            Cargo, getattr(self.instance, "cargo_id", None))
        self.fields["item"].queryset = self._con_el_actual(
            Item, getattr(self.instance, "item_id", None))

        for nombre in ("periodo", "cargo", "item"):
            self.fields[nombre].empty_label = "Elige una opción"

        # Período, cargo e ítem son la identidad de la meta, no datos suyos:
        # son justamente las tres cosas que la restricción de unicidad usa
        # para distinguirla. Cambiarlos no edita esta meta, la convierte en
        # otra, y deja a las actividades ya registradas apuntando a una
        # configuración distinta de aquella con la que se midieron. Al
        # editar quedan bloqueados.
        #
        # ``disabled`` no es solo visual: Django ignora lo que venga en el
        # envío y vuelve a usar el valor guardado, así que mandar otro a mano
        # tampoco sirve.
        if editando:
            for nombre in ("periodo", "cargo", "item"):
                self.fields[nombre].disabled = True
            self.fields["item"].help_text = (
                "El período, el cargo y el ítem no se cambian después de "
                "crear la meta: son lo que la identifica. Para medir otra "
                "combinación, crea una meta nueva."
            )

    @staticmethod
    def _con_el_actual(modelo, pk_actual):
        """Los activos, más el que ya tenga guardado este registro."""
        if pk_actual:
            return modelo.objects.filter(
                models.Q(activo=True) | models.Q(pk=pk_actual)
            ).distinct()
        return modelo.objects.filter(activo=True)

    def clean(self):
        """
        Evita el choque con la restricción de unicidad.

        La base tiene una restricción sobre (período, cargo, ítem). Si se
        deja que salte ella, la persona ve un error de integridad; aquí se
        explica en palabras antes de llegar a eso.
        """
        datos = super().clean()
        periodo, cargo, item = datos.get("periodo"), datos.get("cargo"), datos.get("item")
        if periodo and cargo and item:
            repetida = (
                MetaPeriodo.objects
                .filter(periodo=periodo, cargo=cargo, item=item)
                .exclude(pk=self.instance.pk)
                .exists()
            )
            if repetida:
                self.add_error("item", forms.ValidationError(
                    "«%(item)s» ya tiene meta para %(cargo)s en %(periodo)s. "
                    "Edita la que existe en vez de crear otra.",
                    params={"item": item.nombre, "cargo": cargo.nombre,
                            "periodo": periodo.nombre},
                ))
        return datos


class ReglaCalculoForm(forms.ModelForm):
    """
    Los parámetros del cálculo, configurables desde pantalla.

    Es el formulario que hace cierto el requisito RNF-015: cambiar un umbral
    no exige editar código ni volver a desplegar. Y es el que obliga a decir
    quién aprobó la regla cuando se la marca como aprobada, porque un número
    sin respaldo no se puede defender cuando alguien pregunte de dónde salió.
    """

    class Meta:
        model = ReglaCalculo
        fields = [
            "nombre", "periodo", "tope_aporte", "umbral_realizado",
            "umbral_ambar", "convencion_dias",
            "dias_aviso_vencimiento", "dias_sin_registrar",
            "dias_evidencia_espera",
            "aprobada", "aprobada_por", "observacion",
        ]
        widgets = {
            "nombre": forms.TextInput(attrs={
                "placeholder": "Por ejemplo: Propuesta del plan de pruebas",
            }),
            "tope_aporte": forms.NumberInput(attrs={"min": 100, "max": 300, "step": 5}),
            "umbral_realizado": forms.NumberInput(attrs={"min": 1, "max": 100, "step": 1}),
            "umbral_ambar": forms.NumberInput(attrs={"min": 1, "max": 100, "step": 1}),
            "aprobada_por": forms.TextInput(attrs={
                "placeholder": "Nombre y documento donde consta",
                "ancho": True,
            }),
            "observacion": forms.Textarea(attrs={
                "rows": 3, "ancho": True,
                "placeholder": "De dónde sale cada valor",
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Un período cerrado no se reconfigura, pero si esta regla ya es la
        # suya tiene que seguir apareciendo en el selector: si no, editar
        # cualquier otro campo borraría el vínculo sin avisar.
        disponibles = Periodo.objects.filter(activo=True).exclude(
            estado=Periodo.Estado.CERRADO,
        )
        actual = self.instance.periodo_id
        if actual:
            disponibles = Periodo.objects.filter(
                models.Q(pk=actual) | models.Q(
                    activo=True, estado__in=[
                        Periodo.Estado.BORRADOR, Periodo.Estado.ABIERTO,
                    ],
                )
            )
        self.fields["periodo"].queryset = disponibles.distinct()
        self.fields["periodo"].empty_label = "Regla general del sistema"

    def clean_nombre(self):
        nombre = (self.cleaned_data["nombre"] or "").strip()
        if len(nombre) < 5:
            raise forms.ValidationError(
                "Ponle un nombre que se entienda en un informe."
            )
        return nombre

"""
Formulario de ingreso de atención ciudadana.

Es el formulario más interesante de la entrega porque toca tres cosas a la
vez: crea o reutiliza el solicitante, obliga a que la subatención pertenezca
al tipo elegido, y exige documento de respaldo cuando la subatención lo pide.

Las tres se comprueban en el servidor. El navegador ayuda —carga las
subatenciones del tipo, muestra el aviso del documento— pero no decide: si
alguien envía el formulario a mano con una subatención de otro tipo, el
servidor lo rechaza igual.
"""

from django import forms
from django.db import transaction
from django.urls import reverse_lazy

from atencion.models import Atencion, Solicitante, limpiar_rut, rut_valido
from catalogos.models import SubAtencion, TipoAtencion

# Lista fija en esta entrega. Cuando exista el mantenedor de territorios
# saldrá de la base de datos, igual que los tipos de atención.
TERRITORIOS = [
    "Unidad vecinal 1 · El Mirador",
    "Unidad vecinal 2 · Los Aromos",
    "Unidad vecinal 3 · San Juan",
    "Unidad vecinal 4 · Villa Esperanza",
    "Unidad vecinal 5 · El Milagro Alto",
    "Unidad vecinal 6 · Cisternas",
]


class AtencionForm(forms.ModelForm):
    """Registra una atención y, si hace falta, la ficha de quien consulta."""

    # --- quién consulta --------------------------------------------------
    rut = forms.CharField(
        label="RUT", max_length=12,
        widget=forms.TextInput(attrs={
            "class": "input mono",
            "placeholder": "12.345.678-5",
            "autocomplete": "off",
            # El valor es la dirección de la consulta: lo lee sgr-app.js para
            # buscar la ficha. Con reverse_lazy se resuelve al dibujar la
            # página, no al importar este archivo.
            "data-buscar-rut": reverse_lazy("atencion:buscar_solicitante"),
        }),
        help_text="Con dígito verificador. Si la persona ya fue atendida, se reutiliza su ficha.",
    )
    nombre = forms.CharField(
        label="Nombre y apellido", max_length=120,
        widget=forms.TextInput(attrs={
            "class": "input",
            "placeholder": "Nombre de quien consulta",
            "autocomplete": "off",
            "data-rut-nombre": "1",
        }),
    )
    telefono = forms.CharField(
        label="Teléfono", max_length=20, required=False,
        widget=forms.TextInput(attrs={
            "class": "input",
            "inputmode": "tel",
            "placeholder": "9 1234 5678",
            "data-rut-telefono": "1",
        }),
        help_text="Para avisarle cuando su requerimiento se resuelva.",
    )
    territorio = forms.ChoiceField(
        label="Territorio",
        choices=[("", "Elige el territorio")] + [(t, t) for t in TERRITORIOS],
        widget=forms.Select(attrs={"class": "input", "data-rut-territorio": "1"}),
    )

    # --- qué se atendió --------------------------------------------------
    tipo = forms.ModelChoiceField(
        label="Tipo de atención",
        queryset=TipoAtencion.objects.none(),
        empty_label="Elige un tipo",
        widget=forms.Select(attrs={"class": "input", "data-tipo-atencion": "1"}),
        help_text="Solo se ofrecen los tipos activos.",
    )

    class Meta:
        model = Atencion
        fields = ["subatencion", "detalle", "documento"]
        widgets = {
            "subatencion": forms.Select(attrs={
                "class": "input", "data-subatencion": "1",
            }),
            "detalle": forms.Textarea(attrs={
                "class": "input", "rows": 3,
                "placeholder": "Qué pidió la persona y qué se le respondió",
            }),
            "documento": forms.TextInput(attrs={
                "class": "input",
                "placeholder": "Nombre o número del documento",
            }),
        }
        labels = {"detalle": "Detalle del requerimiento"}
        help_texts = {
            "detalle": (
                "Es lo que se lee cuando alguien revisa el caso meses después. "
                "Sé concreto."
            ),
        }

    def __init__(self, *args, delegacion=None, funcionario=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.delegacion = delegacion
        self.funcionario = funcionario

        self.fields["tipo"].queryset = TipoAtencion.objects.filter(activo=True)
        # El selector de subatención ofrece todas las activas: el navegador
        # muestra solo las del tipo elegido, pero el campo tiene que aceptar
        # cualquiera de ellas para que la validación la haga clean().
        self.fields["subatencion"].queryset = (
            SubAtencion.objects
            .filter(activo=True, tipo_atencion__activo=True)
            .select_related("tipo_atencion")
        )
        self.fields["subatencion"].empty_label = "Elige primero un tipo"
        self.fields["documento"].required = False

    # --- validación ------------------------------------------------------

    def clean_rut(self):
        valor = limpiar_rut(self.cleaned_data["rut"])
        if not rut_valido(valor):
            raise forms.ValidationError(
                "Ese RUT no es válido: revisa el número y el dígito verificador."
            )
        return valor

    def clean_nombre(self):
        nombre = (self.cleaned_data["nombre"] or "").strip()
        if len(nombre) < 5:
            raise forms.ValidationError("Escribe el nombre completo de quien consulta.")
        return nombre

    def clean_detalle(self):
        detalle = (self.cleaned_data["detalle"] or "").strip()
        if len(detalle) < 20:
            raise forms.ValidationError(
                "Describe el requerimiento con más detalle: este texto es el "
                f"respaldo de la atención. Debe tener al menos 20 caracteres (escribiste {len(detalle)})."
            )
        return detalle

    def clean(self):
        datos = super().clean()
        tipo = datos.get("tipo")
        subatencion = datos.get("subatencion")

        # Que la subatención sea del tipo elegido. En pantalla es imposible
        # equivocarse porque el selector se recarga; esto cubre el envío
        # directo del formulario.
        if tipo and subatencion and subatencion.tipo_atencion_id != tipo.pk:
            self.add_error("subatencion", forms.ValidationError(
                "«%(sub)s» pertenece a «%(suyo)s», no a «%(elegido)s».",
                params={
                    "sub": subatencion.nombre,
                    "suyo": subatencion.tipo_atencion.nombre,
                    "elegido": tipo.nombre,
                },
            ))

        # El documento obligatorio NO se comprueba aquí: la regla está en
        # Atencion.clean(), y Django la ejecuta por su cuenta en _post_clean()
        # —después de este método— dejando el error en el campo «documento».
        # Repetirla aquí mostraría el mismo aviso dos veces.

        if self.delegacion is None:
            raise forms.ValidationError(
                "No hay una delegación activa en tu sesión, así que la "
                "atención no sabría a dónde asociarse. Elige una en la "
                "cabecera antes de registrar."
            )

        return datos

    # --- guardado --------------------------------------------------------

    @transaction.atomic
    def save(self, commit=True):
        """
        Guarda la ficha del solicitante y la atención en una transacción.

        Si algo fallara a medio camino, no queda un solicitante creado sin su
        atención.
        """
        solicitante = self._solicitante()

        atencion = super().save(commit=False)
        atencion.solicitante = solicitante
        atencion.delegacion = self.delegacion
        atencion.funcionario = self.funcionario

        if commit:
            atencion.save()
        self.solicitante = solicitante
        self.era_nuevo = self._era_nuevo
        return atencion

    def _solicitante(self):
        """
        Busca la ficha por RUT y la crea si no existe.

        Cuando ya existe se actualizan los datos con lo que el funcionario
        confirmó en pantalla —la gente cambia de teléfono— pero nunca se
        vacía un dato guardado con un campo en blanco.
        """
        rut = self.cleaned_data["rut"]
        solicitante = Solicitante.objects.filter(rut=rut).first()
        self._era_nuevo = solicitante is None

        if solicitante is None:
            return Solicitante.objects.create(
                rut=rut,
                nombre=self.cleaned_data["nombre"],
                telefono=self.cleaned_data.get("telefono", ""),
                territorio=self.cleaned_data.get("territorio", ""),
            )

        cambios = []
        for campo in ("nombre", "telefono", "territorio"):
            nuevo = (self.cleaned_data.get(campo) or "").strip()
            if nuevo and nuevo != getattr(solicitante, campo):
                setattr(solicitante, campo, nuevo)
                cambios.append(campo)
        if cambios:
            solicitante.save(update_fields=cambios)
        return solicitante

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

from atencion.models import Atencion, CasoSocial, Solicitante, limpiar_rut, rut_valido
from catalogos.models import SubAtencion, TipoAtencion



def repartir_nombre(nombre):
    """
    «Nombre y apellido» escrito en una línea, repartido en nombres y apellidos.

    Con cuatro palabras o más, las dos últimas son los apellidos; con dos o
    tres, la última. En la ficha del vecino se corrige si hace falta.
    """
    partes = (nombre or "").split()
    if len(partes) >= 4:
        return " ".join(partes[:-2]), " ".join(partes[-2:])
    if len(partes) >= 2:
        return " ".join(partes[:-1]), partes[-1]
    return (nombre or "").strip(), ""


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
    # Desde la Evaluación 3 el territorio sale del catálogo: los de la
    # delegación activa. Si la delegación todavía no tiene territorios, el
    # campo no es obligatorio, para no detener la atención.
    territorio = forms.ModelChoiceField(
        label="Territorio",
        queryset=None, required=False,
        empty_label="Elige el territorio",
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

        from organizacion.models import Territorio

        territorios = Territorio.objects.filter(activo=True, delegacion=delegacion) if delegacion else Territorio.objects.none()
        self.fields["territorio"].queryset = territorios
        self.fields["territorio"].required = territorios.exists()
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

        nombres, apellidos = repartir_nombre(self.cleaned_data["nombre"])
        territorio = self.cleaned_data.get("territorio")
        if solicitante is None:
            return Solicitante.objects.create(
                rut=rut,
                nombres=nombres,
                apellidos=apellidos,
                telefono=self.cleaned_data.get("telefono", ""),
                territorio=territorio,
            )

        cambios = []
        if self.cleaned_data["nombre"].strip() != solicitante.nombre:
            solicitante.nombres, solicitante.apellidos = nombres, apellidos
            cambios += ["nombres", "apellidos"]
        telefono = (self.cleaned_data.get("telefono") or "").strip()
        if telefono and telefono != solicitante.telefono:
            solicitante.telefono = telefono
            cambios.append("telefono")
        if territorio is not None and territorio.pk != solicitante.territorio_id:
            solicitante.territorio = territorio
            cambios.append("territorio")
        if cambios:
            solicitante.save(update_fields=cambios)
        return solicitante


class CasoSocialForm(forms.ModelForm):
    """Las fechas de un caso social y lo que pasó con su informe."""

    class Meta:
        model = CasoSocial
        fields = [
            "responsable", "ingreso", "requiere_visita", "visita_programada",
            "visita_realizada", "informe_entregado", "devoluciones",
            "lleva_beneficio", "beneficio_entregado", "observacion",
        ]
        widgets = {
            campo: forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")
            for campo in ("ingreso", "visita_programada", "visita_realizada",
                          "informe_entregado", "beneficio_entregado")
        }
        widgets["devoluciones"] = forms.NumberInput(attrs={"min": 0, "max": 9, "step": 1})
        widgets["observacion"] = forms.Textarea(attrs={
            "rows": 3, "ancho": True,
            "placeholder": "Lo que haga falta para entender el caso. Sin datos de salud.",
        })

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from django.contrib.auth.models import User

        for nombre, campo in self.fields.items():
            if isinstance(campo, forms.DateField):
                campo.input_formats = ["%Y-%m-%d"]
        delegacion_id = self.instance.atencion.delegacion_id
        self.fields["responsable"].queryset = (
            User.objects
            .filter(is_active=True, perfil__activo=True, perfil__delegacion_id=delegacion_id)
            .order_by("first_name", "last_name")
        )
        self.fields["responsable"].label_from_instance = (
            lambda u: u.get_full_name() or u.get_username()
        )

    def clean(self):
        datos = super().clean()
        # Esta pantalla corrige el ingreso pero no muestra la fecha de
        # atención: si el ingreso se adelanta, la atención no puede quedar
        # después de él, así que se adelanta con él.
        ingreso = datos.get("ingreso")
        if ingreso and self.instance.fecha_atencion and ingreso < self.instance.fecha_atencion:
            self.instance.fecha_atencion = ingreso
        return datos

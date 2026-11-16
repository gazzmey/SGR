"""
Formularios de vecinos, juntas de vecinos, participaciones y gestiones
sociales (Evaluación 3).

Todos son ``ModelForm`` y validan en el servidor. Las reglas que dependen de
una sola entidad viven en el ``clean()`` del modelo —valen también desde
Django Admin—; aquí quedan las que dependen de quién edita (el alcance de
delegaciones) y las de los campos que no son del modelo.
"""

from django import forms
from django.db import transaction
from django.db.models import Q

from atencion.models import (
    Atencion, CasoSocial, JuntaVecinos, ParticipacionJunta, Solicitante,
)
from catalogos.models import SubAtencion, TipoAtencion
from comun.formularios import ConAlcance, ConCodigo, activos_mas, fecha, nombre_de_usuario
from comun.rut import limpiar_rut, rut_valido
from comun.utilidades import proximo_codigo

TELEFONO_VALIDO = set("0123456789 +()-")


# =========================================================================
# Vecinos
# =========================================================================


class VecinoForm(ConAlcance, forms.ModelForm):
    class Meta:
        model = Solicitante
        fields = ["rut", "nombres", "apellidos", "telefono", "correo", "direccion", "territorio"]
        widgets = {
            "rut": forms.TextInput(attrs={"placeholder": "12.345.678-5", "class": "mono"}),
            "nombres": forms.TextInput(attrs={"placeholder": "Por ejemplo: Rosa Elena"}),
            "apellidos": forms.TextInput(attrs={"placeholder": "Por ejemplo: Tapia Godoy"}),
            "telefono": forms.TextInput(attrs={"placeholder": "9 1234 5678", "inputmode": "tel"}),
            "correo": forms.EmailInput(attrs={"placeholder": "nombre@ejemplo.cl"}),
            "direccion": forms.TextInput(attrs={"placeholder": "Calle, número y referencia", "ancho": True}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["apellidos"].required = True
        self.fields["territorio"].required = True
        self.fields["territorio"].queryset = self.territorios(
            getattr(self.instance, "territorio_id", None))
        self.fields["territorio"].label_from_instance = (
            lambda t: f"{t.nombre} · {t.delegacion.nombre}")
        self.fields["territorio"].empty_label = "Elige el territorio donde vive"

    def clean_rut(self):
        valor = limpiar_rut(self.cleaned_data.get("rut"))
        if not rut_valido(valor):
            raise forms.ValidationError(
                "Ese RUT no es válido: revisa el número y el dígito verificador.")
        otro = Solicitante.objects.filter(rut=valor).exclude(pk=self.instance.pk).first()
        if otro is not None:
            raise forms.ValidationError(
                "Ya hay un vecino con ese RUT: %s. Edita esa ficha en vez de crear otra."
                % otro.nombre)
        return valor

    def clean_nombres(self):
        valor = (self.cleaned_data.get("nombres") or "").strip()
        if len(valor) < 2:
            raise forms.ValidationError("Escribe al menos un nombre.")
        return valor

    def clean_apellidos(self):
        valor = (self.cleaned_data.get("apellidos") or "").strip()
        if len(valor) < 2:
            raise forms.ValidationError("Escribe al menos un apellido.")
        return valor

    def clean_telefono(self):
        valor = (self.cleaned_data.get("telefono") or "").strip()
        if valor and not set(valor) <= TELEFONO_VALIDO:
            raise forms.ValidationError("El teléfono solo admite números, espacios y los signos + ( ) -")
        if valor and sum(c.isdigit() for c in valor) < 8:
            raise forms.ValidationError("El teléfono parece incompleto: tiene menos de 8 dígitos.")
        return valor

    def clean_direccion(self):
        valor = (self.cleaned_data.get("direccion") or "").strip()
        if valor and len(valor) < 5:
            raise forms.ValidationError("La dirección parece incompleta.")
        return valor


# =========================================================================
# Juntas de vecinos
# =========================================================================


class JuntaForm(ConAlcance, ConCodigo):
    prefijo = "JV"

    class Meta:
        model = JuntaVecinos
        fields = ["codigo", "nombre", "delegacion", "territorio", "direccion", "fecha_constitucion"]
        widgets = {
            "nombre": forms.TextInput(attrs={"placeholder": "Por ejemplo: Junta de Vecinos Villa El Sol"}),
            "direccion": forms.TextInput(attrs={"placeholder": "Dirección de la sede", "ancho": True}),
            "fecha_constitucion": fecha(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["delegacion"].queryset = self.delegaciones(
            getattr(self.instance, "delegacion_id", None))
        self.fields["territorio"].queryset = self.territorios(
            getattr(self.instance, "territorio_id", None))
        self.fields["territorio"].label_from_instance = (
            lambda t: f"{t.nombre} · {t.delegacion.nombre}")
        for campo in ("delegacion", "territorio"):
            self.fields[campo].empty_label = "Elige una opción"

    def clean_nombre(self):
        valor = (self.cleaned_data.get("nombre") or "").strip()
        if len(valor) < 5:
            raise forms.ValidationError("El nombre debe tener al menos 5 caracteres.")
        return valor

    def clean_direccion(self):
        valor = (self.cleaned_data.get("direccion") or "").strip()
        if len(valor) < 5:
            raise forms.ValidationError("La dirección parece incompleta.")
        return valor


# =========================================================================
# Participaciones
# =========================================================================


class ParticipacionForm(ConAlcance, ConCodigo):
    prefijo = "PJ"
    ancho = 3

    class Meta:
        model = ParticipacionJunta
        fields = ["codigo", "vecino", "junta", "dirigente", "cargo", "fecha_incorporacion"]
        widgets = {"fecha_incorporacion": fecha()}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        vecinos = Solicitante.objects.select_related("territorio")
        juntas = JuntaVecinos.objects.select_related("territorio")
        if self.permitidas is not None:
            vecinos = vecinos.filter(territorio__delegacion_id__in=self.permitidas)
            juntas = juntas.filter(delegacion_id__in=self.permitidas)
        self.fields["vecino"].queryset = activos_mas(
            vecinos, getattr(self.instance, "vecino_id", None)).order_by("apellidos", "nombres")
        self.fields["vecino"].label_from_instance = (
            lambda v: "%s · %s" % (v.nombre, v.territorio.nombre if v.territorio_id else "sin territorio"))
        self.fields["junta"].queryset = activos_mas(juntas, getattr(self.instance, "junta_id", None))
        self.fields["junta"].label_from_instance = (
            lambda j: f"{j.nombre} · {j.territorio.nombre}")
        for campo in ("vecino", "junta"):
            self.fields[campo].empty_label = "Elige una opción"
        # La persona y la junta son la identidad de la participación.
        if self.instance.pk:
            for campo in ("vecino", "junta"):
                self.fields[campo].disabled = True


# =========================================================================
# Gestiones sociales
# =========================================================================


class GestionSocialForm(ConAlcance, forms.ModelForm):
    """
    La gestión social completa, en un formulario.

    Una gestión social es un ``CasoSocial`` sobre una ``Atencion``: quién
    consultó (el beneficiario), qué tipo y subtipo de atención y en qué
    delegación. Al crear, el formulario guarda las dos en una transacción;
    al editar, actualiza las dos. La delegación no cambia después de creada.
    """

    beneficiario = forms.ModelChoiceField(
        label="Beneficiario", queryset=Solicitante.objects.none(),
        help_text="El vecino atendido. Si no está, créalo antes en Vecinos.",
    )
    tipo = forms.ModelChoiceField(label="Tipo de atención", queryset=TipoAtencion.objects.none())
    subtipo = forms.ModelChoiceField(
        label="Subtipo de atención", queryset=SubAtencion.objects.none(),
        help_text="Tiene que pertenecer al tipo elegido.",
    )
    delegacion = forms.ModelChoiceField(label="Delegación", queryset=None)
    detalle = forms.CharField(
        label="Qué pidió la persona", widget=forms.Textarea(attrs={"rows": 3, "ancho": True}),
        help_text="Lo que se lee al revisar el caso meses después.",
    )
    documento = forms.CharField(
        label="Documento de respaldo", max_length=120, required=False,
        help_text="Obligatorio si el subtipo lo exige.",
    )

    class Meta:
        model = CasoSocial
        fields = [
            "fecha_atencion", "ingreso", "responsable", "asignacion",
            "requiere_visita", "visita_programada", "visita_realizada",
            "informe_entregado", "devoluciones", "lleva_beneficio", "beneficio_entregado",
            "actuaciones", "derivacion", "resultado", "observacion",
        ]
        widgets = {
            campo: fecha() for campo in (
                "fecha_atencion", "ingreso", "visita_programada", "visita_realizada",
                "informe_entregado", "beneficio_entregado")
        }
        widgets.update({
            "devoluciones": forms.NumberInput(attrs={"min": 0, "max": 9, "step": 1}),
            "actuaciones": forms.Textarea(attrs={"rows": 3, "ancho": True}),
            "resultado": forms.Textarea(attrs={"rows": 3, "ancho": True}),
            "observacion": forms.Textarea(attrs={
                "rows": 2, "ancho": True,
                "placeholder": "Lo que haga falta para entender el caso. Sin datos de salud.",
            }),
        })

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        instancia = self.instance
        atencion = instancia.atencion if instancia.pk else None

        vecinos = Solicitante.objects.all()
        if self.permitidas is not None:
            vecinos = vecinos.filter(
                Q(territorio__delegacion_id__in=self.permitidas)
                | Q(atenciones__delegacion_id__in=self.permitidas))
        self.fields["beneficiario"].queryset = activos_mas(
            vecinos, atencion.solicitante_id if atencion else None).distinct().order_by("apellidos", "nombres")
        self.fields["beneficiario"].label_from_instance = lambda v: f"{v.nombre} · {v.rut}"
        self.fields["tipo"].queryset = activos_mas(
            TipoAtencion.objects.all(),
            atencion.subatencion.tipo_atencion_id if atencion else None)
        self.fields["subtipo"].queryset = activos_mas(
            SubAtencion.objects.select_related("tipo_atencion"),
            atencion.subatencion_id if atencion else None)
        self.fields["subtipo"].label_from_instance = (
            lambda s: f"{s.nombre} · {s.tipo_atencion.nombre}")
        self.fields["delegacion"].queryset = self.delegaciones(
            atencion.delegacion_id if atencion else None)

        self.fields["responsable"].queryset = self.personas(getattr(instancia, "responsable_id", None))
        self.fields["responsable"].label_from_instance = nombre_de_usuario
        from gestion.models import MetaPeriodo

        self.fields["asignacion"].queryset = activos_mas(
            MetaPeriodo.objects.exclude(periodo__estado="cerrado")
            .select_related("item", "cargo", "periodo", "funcionario"),
            getattr(instancia, "asignacion_id", None))
        self.fields["asignacion"].empty_label = "Sin asignación de meta"
        for campo in ("beneficiario", "tipo", "subtipo", "delegacion", "responsable"):
            self.fields[campo].empty_label = "Elige una opción"

        if atencion is not None:
            self.initial.update({
                "beneficiario": atencion.solicitante_id,
                "tipo": atencion.subatencion.tipo_atencion_id,
                "subtipo": atencion.subatencion_id,
                "delegacion": atencion.delegacion_id,
                "detalle": atencion.detalle,
                "documento": atencion.documento,
            })
            self.fields["delegacion"].disabled = True
            self.fields["delegacion"].help_text = "No cambia después de creada."

    def clean_detalle(self):
        valor = (self.cleaned_data.get("detalle") or "").strip()
        if len(valor) < 20:
            raise forms.ValidationError(
                f"Describe el requerimiento: al menos 20 caracteres (escribiste {len(valor)}).")
        return valor

    def clean(self):
        datos = super().clean()
        tipo, subtipo = datos.get("tipo"), datos.get("subtipo")
        if tipo and subtipo and subtipo.tipo_atencion_id != tipo.pk:
            self.add_error("subtipo", "«%s» pertenece a «%s», no a «%s»." % (
                subtipo.nombre, subtipo.tipo_atencion.nombre, tipo.nombre))
        if subtipo and subtipo.documento and not (datos.get("documento") or "").strip():
            self.add_error("documento", "«%s» exige documento de respaldo: indica cuál." % subtipo.nombre)
        delegacion, responsable = datos.get("delegacion"), datos.get("responsable")
        if delegacion and responsable:
            perfil = getattr(responsable, "perfil", None)
            if perfil is None or not perfil.delegaciones_visibles().filter(pk=delegacion.pk).exists():
                self.add_error("responsable", "%s no trabaja en %s ni tiene alcance sobre ella." % (
                    nombre_de_usuario(responsable), delegacion.nombre))
        beneficiario = datos.get("beneficiario")
        if beneficiario and not beneficiario.activo and (
                not self.instance.pk or self.instance.atencion.solicitante_id != beneficiario.pk):
            self.add_error("beneficiario", "Ese vecino está inactivo.")
        return datos

    @transaction.atomic
    def save(self, commit=True):
        caso = super().save(commit=False)
        datos = self.cleaned_data
        if caso.pk:
            atencion = caso.atencion
        else:
            atencion = Atencion(delegacion=datos["delegacion"], funcionario=self.usuario)
            caso.codigo = proximo_codigo(CasoSocial, "CSO", ancho=3)
        atencion.solicitante = datos["beneficiario"]
        atencion.subatencion = datos["subtipo"]
        atencion.detalle = datos["detalle"]
        atencion.documento = (datos.get("documento") or "").strip()
        atencion.save()
        caso.atencion = atencion
        caso.save()
        return caso

"""
Formularios de hitos y de actividades y evidencias como registros
completos (Evaluación 3).

«Mis actividades» y «Validar evidencias» son flujos de trabajo: cada
funcionario registra lo suyo y otra persona lo valida. Estos formularios son
el CRUD de las entidades: permiten registrar a nombre de cualquier
funcionario del alcance, con todos los antecedentes que pide el enunciado.
La validación (aprobar o rechazar) sigue siendo del verificador: el estado
no se edita a mano.
"""

from django import forms
from django.db.models import Q

from atencion.models import CasoSocial, Solicitante
from comun import relleno as R
from comun.formularios import ConAlcance, ConCodigo, activos_mas, fecha, nombre_de_usuario
from gestion.modelos_actividad import Actividad, Evidencia
from gestion.models import Hito, MetaPeriodo, Periodo


# =========================================================================
# Hitos
# =========================================================================


class HitoForm(ConAlcance, ConCodigo):
    prefijo = "HIT"

    class Meta:
        model = Hito
        fields = ["codigo", "nombre", "descripcion", "periodicidad", "fecha_inicio",
                  "fecha_termino", "delegacion", "territorio", "responsables"]
        widgets = {
            "nombre": forms.TextInput(attrs={"placeholder": "Por ejemplo: Operativo de limpieza de microbasurales"}),
            "descripcion": forms.Textarea(attrs={"rows": 3, "ancho": True}),
            "fecha_inicio": fecha(),
            "fecha_termino": fecha(),
            "responsables": forms.CheckboxSelectMultiple,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        actuales = list(self.instance.responsables.values_list("pk", flat=True)) if self.instance.pk else []
        self.fields["delegacion"].queryset = self.delegaciones(getattr(self.instance, "delegacion_id", None))
        self.fields["territorio"].queryset = self.territorios(getattr(self.instance, "territorio_id", None))
        self.fields["territorio"].label_from_instance = lambda t: f"{t.nombre} · {t.delegacion.nombre}"
        self.fields["territorio"].empty_label = "Sin territorio (toda la delegación)"
        self.fields["delegacion"].empty_label = "Elige la delegación"
        self.fields["responsables"].queryset = self.personas(*actuales)
        self.rotular_personas(self.fields["responsables"])

        # Relleno inteligente: el territorio trae su delegación, y la
        # delegación limita los territorios que se ofrecen.
        R.datos_de_opciones(self.fields["territorio"], R.datos_territorio)
        R.filtra(self.fields["territorio"], "delegacion")
        R.rellena(self.fields["territorio"], {"delegacion": "delegacion"}, "según el territorio")

    def relleno(self, request):
        from comun.contexto import delegacion_activa

        self.proponer("delegacion", delegacion_activa(request))

    def clean_nombre(self):
        valor = (self.cleaned_data.get("nombre") or "").strip()
        if len(valor) < 5:
            raise forms.ValidationError("El nombre debe tener al menos 5 caracteres.")
        return valor

    def clean_descripcion(self):
        valor = (self.cleaned_data.get("descripcion") or "").strip()
        if len(valor) < 15:
            raise forms.ValidationError(
                f"Describe el hito: al menos 15 caracteres (escribiste {len(valor)}).")
        return valor

    def clean(self):
        datos = super().clean()
        delegacion = datos.get("delegacion")
        responsables = datos.get("responsables")
        if delegacion is not None and responsables is not None:
            motivo = Hito.motivo_responsables(list(responsables), delegacion)
            if motivo:
                self.add_error("responsables", motivo)
        return datos


# =========================================================================
# Actividades
# =========================================================================


def _rotulo_asignacion(meta):
    return "%s · %s · %s" % (meta.item.nombre, meta.destinatario, meta.periodo.nombre)


class ActividadRegistroForm(ConAlcance, ConCodigo):
    prefijo = "ACT"
    ancho = 4

    class Meta:
        model = Actividad
        fields = [
            "codigo", "funcionario", "delegacion", "asignacion", "fecha", "cantidad",
            "tipo", "accion", "detalle", "origen", "solicitante", "territorio", "hito",
            "responsable", "fecha_compromiso", "apoyo", "avance", "resultado",
        ]
        widgets = {
            "fecha": fecha(),
            "fecha_compromiso": fecha(),
            "detalle": forms.Textarea(attrs={"rows": 3, "ancho": True}),
            "resultado": forms.Textarea(attrs={"rows": 2, "ancho": True}),
            "accion": forms.TextInput(attrs={"placeholder": "En una línea: qué se hizo", "ancho": True}),
            "cantidad": forms.NumberInput(attrs={"min": 1, "step": 1}),
            "avance": forms.NumberInput(attrs={"min": 0, "max": 100, "step": 5}),
        }
        labels = {"accion": "Descripción", "detalle": "Detalle"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        inst = self.instance
        self.fields["funcionario"].queryset = self.personas(getattr(inst, "funcionario_id", None))
        self.fields["responsable"].queryset = self.personas(getattr(inst, "responsable_id", None))
        self.rotular_personas(self.fields["funcionario"], self.fields["responsable"])
        self.fields["delegacion"].queryset = self.delegaciones(getattr(inst, "delegacion_id", None))
        self.fields["territorio"].queryset = self.territorios(getattr(inst, "territorio_id", None))
        self.fields["territorio"].label_from_instance = lambda t: f"{t.nombre} · {t.delegacion.nombre}"

        asignaciones = (MetaPeriodo.objects.filter(activo=True, periodo__estado=Periodo.Estado.ABIERTO)
                        .select_related("item", "cargo", "periodo", "funcionario"))
        if getattr(inst, "asignacion_id", None):
            asignaciones = MetaPeriodo.objects.filter(
                Q(pk__in=asignaciones.values("pk")) | Q(pk=inst.asignacion_id)
            ).select_related("item", "cargo", "periodo", "funcionario")
        self.fields["asignacion"].queryset = asignaciones
        self.fields["asignacion"].label_from_instance = _rotulo_asignacion
        self.fields["asignacion"].required = True
        self.fields["asignacion"].help_text = (
            "La meta a la que suma, de un trimestre abierto. Tiene que medir al "
            "funcionario: la suya o la de su cargo."
        )

        hitos = Hito.objects.all()
        vecinos = Solicitante.objects.all()
        if self.permitidas is not None:
            hitos = hitos.filter(delegacion_id__in=self.permitidas)
        self.fields["hito"].queryset = activos_mas(hitos, getattr(inst, "hito_id", None))
        self.fields["solicitante"].queryset = activos_mas(
            vecinos, getattr(inst, "solicitante_id", None)).order_by("apellidos", "nombres")
        self.fields["solicitante"].label_from_instance = lambda v: f"{v.nombre} · {v.rut}"
        for campo, vacio in (("hito", "Sin hito"), ("solicitante", "Sin solicitante"),
                             ("territorio", "Sin territorio"), ("responsable", "Quien la registra")):
            self.fields[campo].empty_label = vacio
        for campo in ("funcionario", "delegacion", "asignacion"):
            self.fields[campo].empty_label = "Elige una opción"

        # Con la actividad aprobada, lo que decide el puntaje ya fue validado
        # por otra persona y no se toca. Se puede seguir completando el resto.
        if inst.pk and inst.estado == Actividad.Estado.APROBADA:
            for campo in Actividad.CAMPOS_DEL_CALCULO + ["delegacion"]:
                self.fields[campo].disabled = True
                self.fields[campo].help_text = "Aprobada: no se cambia. Anúlala si hay que corregirla."
        self._preparar_relleno(asignaciones)

    def _preparar_relleno(self, asignaciones):
        """
        Lo que el formulario completa solo mientras se llena.

        * El funcionario se busca escribiendo y trae su delegación.
        * La asignación se limita a las que miden a ese funcionario —la suya
          o la de su cargo, con la regla de ``calculo.metas_de``—; si es una
          sola, queda elegida.
        * El vecino se busca por nombre o RUT y trae su territorio.
        * El territorio y el hito se limitan a la delegación, y el hito
          trae su territorio.
        """
        f = self.fields
        self._recientes = {"solicitante": set(), "asignacion": set()}

        R.datos_de_opciones(f["funcionario"], R.datos_persona)
        R.buscador(f["funcionario"], "Escribe el nombre o el correo")
        R.rellena(f["funcionario"], {"delegacion": "delegacion"}, "según el funcionario")

        mide = R.quienes_mide(asignaciones)
        R.datos_de_opciones(f["asignacion"], lambda a: {
            "mide": mide.get(a.pk, ()),
            "reciente": a.pk in self._recientes["asignacion"],
        })
        R.filtra(f["asignacion"], "funcionario", dato="mide", lista=True, autoelige=True,
                 aviso="Solo las metas que miden a esa persona en el trimestre abierto.",
                 vacio="Esa persona no tiene metas asignadas en el trimestre abierto.")

        R.datos_de_opciones(f["solicitante"], lambda v: dict(
            R.datos_vecino(v), reciente=v.pk in self._recientes["solicitante"],
            origen=Actividad.Origen.COMUNIDAD))
        R.buscador(f["solicitante"], "Escribe el nombre o el RUT del vecino")
        R.rellena(f["solicitante"], {"territorio": "territorio", "origen": "origen"}, "según el vecino")

        R.datos_de_opciones(f["territorio"], R.datos_territorio)
        R.filtra(f["territorio"], "delegacion", vacio="Esa delegación no tiene territorios activos.")

        R.datos_de_opciones(f["hito"], lambda h: {
            "delegacion": h.delegacion_id, "territorio": h.territorio_id})
        R.filtra(f["hito"], "delegacion", vacio="Esa delegación no tiene hitos activos.")
        R.rellena(f["hito"], {"territorio": "territorio"}, "según el hito")

        R.datos_de_opciones(f["responsable"], R.datos_persona)

    def relleno(self, request):
        """Quien registra, su delegación activa y la fecha de hoy."""
        from comun.contexto import delegacion_activa

        self._recientes["solicitante"] = R.vecinos_recientes(request.user)
        self._recientes["asignacion"] = R.asignaciones_recientes(request.user)
        # Quien registra se propone como funcionario solo si a esa persona
        # la miden metas (tiene cargo): si no, el formulario espera a que se
        # elija a quién se le registra.
        perfil = getattr(request.user, "perfil", None)
        if perfil is not None and perfil.cargo_asignado_id:
            self.proponer("funcionario", request.user)
        self.proponer("delegacion", delegacion_activa(request))
        if not self.is_bound and not self.instance.pk:
            self.initial.setdefault("fecha", R.hoy())
            # El origen trae «planificada» por omisión: es una propuesta, y
            # cambia a «solicitud de la comunidad» al elegir un vecino.
            if not self.initial.get("origen"):
                self.fields["origen"].widget.attrs["data-propuesto"] = "1"

    def clean_accion(self):
        valor = (self.cleaned_data.get("accion") or "").strip()
        if len(valor) < 5:
            raise forms.ValidationError("Describe la actividad en al menos 5 caracteres.")
        return valor

    def clean_detalle(self):
        valor = (self.cleaned_data.get("detalle") or "").strip()
        if len(valor) < 15:
            raise forms.ValidationError(
                f"El detalle es lo que lee el verificador: al menos 15 caracteres (escribiste {len(valor)}).")
        return valor

    def clean(self):
        datos = super().clean()
        funcionario, delegacion = datos.get("funcionario"), datos.get("delegacion")
        if funcionario and delegacion:
            perfil = getattr(funcionario, "perfil", None)
            if perfil is None or not perfil.delegaciones_visibles().filter(pk=delegacion.pk).exists():
                self.add_error("delegacion", "%s no trabaja en %s ni tiene alcance sobre ella." % (
                    nombre_de_usuario(funcionario), delegacion.nombre))
        asignacion = datos.get("asignacion")
        if asignacion is not None:
            # El modelo lo vuelve a comprobar; aquí se adelanta para que
            # período e ítem estén puestos cuando el modelo valide las fechas.
            self.instance.item_id = asignacion.item_id
            self.instance.periodo_id = asignacion.periodo_id
        return datos


# =========================================================================
# Evidencias
# =========================================================================


class EvidenciaRegistroForm(ConAlcance, ConCodigo):
    """
    Una evidencia con su registro de origen: una actividad **o** una
    gestión social. Puede guardar solo una referencia ficticia; los archivos
    se suben desde «Mis actividades».
    """

    prefijo = "EVI"
    ancho = 4

    ORIGENES = [("actividad", "Una actividad"), ("caso", "Una gestión social")]
    origen = forms.ChoiceField(label="Respalda", choices=ORIGENES, widget=forms.RadioSelect,
                               initial="actividad")

    class Meta:
        model = Evidencia
        fields = ["codigo", "origen", "actividad", "caso", "tipo", "descripcion",
                  "referencia", "observacion"]
        widgets = {
            "descripcion": forms.TextInput(attrs={"placeholder": "Qué es el documento y qué acredita", "ancho": True}),
            "referencia": forms.TextInput(attrs={"placeholder": "Folio, número de acta o ruta del archivo"}),
            "observacion": forms.Textarea(attrs={"rows": 2, "ancho": True}),
        }
        labels = {"referencia": "Ubicación o referencia"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        inst = self.instance
        actividades = (Actividad.objects.exclude(estado=Actividad.Estado.ANULADA)
                       .select_related("funcionario"))
        casos = (CasoSocial.objects.exclude(estado=CasoSocial.Estado.ANULADO)
                 .select_related("atencion__solicitante"))
        if self.permitidas is not None:
            actividades = actividades.filter(delegacion_id__in=self.permitidas)
            casos = casos.filter(atencion__delegacion_id__in=self.permitidas)
        self.fields["actividad"].queryset = actividades.order_by("-fecha")
        self.fields["actividad"].label_from_instance = (
            lambda a: f"{a.codigo} · {a.accion} · {nombre_de_usuario(a.funcionario)}")
        self.fields["caso"].queryset = casos.order_by("-ingreso")
        self.fields["caso"].label_from_instance = (
            lambda c: f"{c.codigo} · {c.atencion.solicitante.nombre}")
        self.fields["actividad"].empty_label = "Elige la actividad"
        self.fields["caso"].empty_label = "Elige la gestión social"
        self.fields["referencia"].required = True

        # Relleno inteligente: se busca escribiendo, y primero aparecen las
        # actividades que todavía esperan su evidencia.
        esperan = set(actividades.filter(
            estado__in=[Actividad.Estado.BORRADOR, Actividad.Estado.RECHAZADA]
        ).values_list("pk", flat=True)[:200])
        R.datos_de_opciones(self.fields["actividad"], lambda a: {
            "detalle": f"{a.fecha:%d-%m-%Y} · {a.get_estado_display()}",
            "reciente": a.pk in esperan,
        })
        R.buscador(self.fields["actividad"], "Escribe el código, la descripción o el funcionario")
        self.fields["actividad"].widget.attrs["data-recientes"] = "Esperan evidencia"
        R.datos_de_opciones(self.fields["caso"], lambda c: {
            "detalle": f"{R.rut_legible(c.atencion.solicitante.rut)} · {c.get_estado_display()}",
            "busca": c.atencion.solicitante.rut,
        })
        R.buscador(self.fields["caso"], "Escribe el código, el nombre o el RUT")
        R.muestra_si(self.fields["actividad"], "origen", "actividad")
        R.muestra_si(self.fields["caso"], "origen", "caso")
        if inst.pk:
            self.initial["origen"] = "actividad" if inst.actividad_id else "caso"
            for campo in ("origen", "actividad", "caso"):
                self.fields[campo].disabled = True
            self.fields["origen"].help_text = "El registro de origen no cambia: identifica a la evidencia."

    def clean_descripcion(self):
        valor = (self.cleaned_data.get("descripcion") or "").strip()
        if len(valor) < 10:
            raise forms.ValidationError("Explica qué respalda: al menos 10 caracteres.")
        return valor

    def clean(self):
        datos = super().clean()
        if self.instance.pk:
            return datos
        origen = datos.get("origen")
        if origen == "actividad":
            datos["caso"] = None
            if not datos.get("actividad"):
                self.add_error("actividad", "Elige la actividad que respalda.")
        elif origen == "caso":
            datos["actividad"] = None
            if not datos.get("caso"):
                self.add_error("caso", "Elige la gestión social que respalda.")
        self.instance.actividad = datos.get("actividad")
        self.instance.caso = datos.get("caso")
        return datos

    def save(self, commit=True):
        evidencia = super().save(commit=False)
        if not evidencia.pk:
            evidencia.autor = self.usuario
        if commit:
            evidencia.save()
            actividad = evidencia.actividad
            if actividad is not None and actividad.estado in {
                    Actividad.Estado.BORRADOR, Actividad.Estado.RECHAZADA}:
                actividad.estado = Actividad.Estado.PENDIENTE
                actividad.save(update_fields=["estado"])
        return evidencia

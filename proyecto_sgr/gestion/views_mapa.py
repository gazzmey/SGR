"""
Las pantallas del mapa de presencia territorial.

Toda la lógica está en ``gestion/mapa.py``; aquí solo se comprueba quién
entra, se leen los filtros y se arma la página. El mapa se dibuja en el
navegador con los mismos datos que la tabla de abajo, que se escribe en el
servidor: si el JavaScript no carga, la tabla sigue diciendo lo mismo.

Además del mapa hay dos operaciones:

``ubicar``
    Guarda el centro de un territorio elegido con un clic en el mapa. Es la
    misma validación del campo «Ubicación en el mapa» de la ficha, así que
    no hay dos reglas distintas para lo mismo.
``salida``
    La hoja de ruta de una salida a terreno armada en el mapa: las paradas
    en orden, con lo que conviene saber de cada una, para imprimir. Quien
    puede crear hitos la deja además planificada: un hito por parada.
"""

from datetime import timedelta

from django import forms
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from comun.auditoria import registrar
from comun.entidades import puede
from comun.formularios import nombre_de_usuario
from comun.models import EventoAuditoria
from comun.permisos import redirect_al_login
from comun.resultado import anunciar
from comun.utilidades import proximo_codigo
from gestion import mapa as M
from gestion.modelos_actividad import Actividad
from gestion.modelos_hitos import Hito
from organizacion.forms import leer_ubicacion
from organizacion.models import Territorio

#: El orden de la tabla: primero lo que más necesita que alguien vaya.
_GRAVEDAD = {"rojo": 0, "ambar": 1, "verde": 2, "gris": 3}

#: Una salida a terreno de un día no tiene más paradas que esto.
MAXIMO_PARADAS = 12


def _orden(fila):
    dias = fila["dias"]
    return (_GRAVEDAD[fila["semaforo"]], -(dias if dias is not None else 10 ** 6), fila["nombre"])


def _modo_o_403(request):
    modo = M.modo_de(request.user)
    if modo is None:
        messages.error(
            request,
            "No tienes permiso para entrar ahí. Si crees que es un error, "
            "pídele al administrador que revise tu rol.",
        )
        raise PermissionDenied("El mapa de presencia necesita ver el tablero o registrar actividades.")
    return modo


def mapa(request):
    if not request.user.is_authenticated:
        return redirect_al_login(request)
    modo = _modo_o_403(request)

    delegaciones = M.delegaciones_de(request.user)
    filtros = M.Filtros(request, delegaciones)
    datos = M.calcular(request.user, filtros, modo)
    filas = sorted(datos["territorios"], key=_orden)
    puede_ubicar = puede(request.user, "territorio", "change")

    # Lo que viaja al navegador: lo mismo que la tabla, sin nada más.
    para_el_mapa = {
        "modo": modo,
        "presencia": filtros.presencia,
        "presencia_texto": filtros.como_texto(),
        "referencia": filtros.referencia.strftime("%d-%m-%Y"),
        "periodo": filtros.periodo.nombre if filtros.periodo else "",
        "umbral": {"verde": M.VERDE_HASTA, "ambar": M.AMBAR_HASTA},
        "comparacion": ({"nombre": filtros.anterior.nombre, "texto": filtros.comparacion_texto()}
                        if filtros.anterior is not None else None),
        "ubicar": ({"url": reverse("gestion:mapa_ubicar", args=[0]), "csrf": get_token(request)}
                   if puede_ubicar else None),
        "salida": reverse("gestion:mapa_salida"),
        "territorios": filas,
    }

    return render(request, "gestion/mapa.html", {
        "menu": "mapa",
        "modo": modo,
        "personal": modo == M.PERSONAL,
        "filtros": filtros,
        "periodo": filtros.periodo,
        "periodos": filtros.periodos,
        "delegaciones": filtros.delegaciones,
        "origenes": Actividad.Origen.choices,
        "tipos": Actividad.Tipo.choices,
        "presencias": list(M.PRESENCIA.items()),
        "filas": filas,
        "olvidados": [f for f in filas if f["semaforo"] == "rojo"][:5],
        "resumen": datos["resumen"],
        "ubicados": datos["ubicados"],
        "sin_ubicar": datos["sin_ubicar"],
        "sin_reconocer": datos["sin_reconocer"],
        "para_el_mapa": para_el_mapa,
        "puede_ubicar": puede_ubicar,
        "comparacion": filtros.comparacion_texto(),
        "verde_hasta": M.VERDE_HASTA,
        "ambar_hasta": M.AMBAR_HASTA,
    })


# =========================================================================
# Ubicar un territorio con un clic
# =========================================================================


@require_POST
def ubicar(request, pk):
    """
    Guarda la ubicación de un territorio. Responde JSON: la llama el mapa.

    Pide el mismo permiso que editar la ficha del territorio y respeta el
    alcance: un territorio de otra delegación responde como si no existiera.
    """
    if not request.user.is_authenticated:
        return JsonResponse({"ok": False, "error": "Tu sesión terminó. Vuelve a ingresar."}, status=403)
    if not puede(request.user, "territorio", "change"):
        return JsonResponse({"ok": False, "error": "No tienes permiso para ubicar territorios."}, status=403)

    territorio = (Territorio.objects.select_related("delegacion")
                  .filter(pk=pk, delegacion__in=M.delegaciones_de(request.user)).first())
    if territorio is None:
        return JsonResponse({"ok": False, "error": "Ese territorio no existe."}, status=404)

    try:
        punto = leer_ubicacion("%s, %s" % (request.POST.get("lat", ""), request.POST.get("lng", "")))
    except ValidationError as error:
        return JsonResponse({"ok": False, "error": " ".join(error.messages)}, status=400)
    if punto is None:
        return JsonResponse({"ok": False, "error": "Haz clic en el mapa para elegir el lugar."}, status=400)

    antes = territorio.ubicacion_texto or "sin ubicar"
    territorio.latitud, territorio.longitud = punto
    territorio.save(update_fields=["latitud", "longitud"])
    registrar(request, EventoAuditoria.Accion.EDITAR, entidad="Territorio", objeto=territorio,
              antes="ubicación: %s" % antes, despues="ubicación: %s" % territorio.ubicacion_texto,
              detalle="Ubicado desde el mapa de presencia.")
    anunciar(request, "Ubicación guardada",
             "%s quedó en el mapa, en %s." % (territorio.nombre, territorio.ubicacion_texto))
    return JsonResponse({"ok": True, "texto": territorio.ubicacion_texto})


# =========================================================================
# Salida a terreno
# =========================================================================


class SalidaForm(forms.Form):
    """Lo que hace falta para dejar la salida planificada como hitos."""

    nombre = forms.CharField(
        label="Nombre de la salida", max_length=60, required=False,
        widget=forms.TextInput(attrs={"placeholder": "Por ejemplo: Recorrido por Las Compañías"}),
        help_text="Opcional. Si lo dejas en blanco, se llama «Salida a terreno» y la fecha.",
    )
    fecha = forms.DateField(
        label="Fecha de la salida", input_formats=["%Y-%m-%d"],
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
    )
    responsables = forms.ModelMultipleChoiceField(
        label="Quiénes van", queryset=get_user_model().objects.none(),
        widget=forms.CheckboxSelectMultiple,
        help_text="Al menos una persona que trabaje en la delegación de cada parada.",
    )

    def __init__(self, *args, paradas=(), usuario=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.paradas = list(paradas)
        delegaciones = {t.delegacion_id for t in self.paradas}
        Usuario = get_user_model()
        self.fields["responsables"].queryset = (
            Usuario.objects.filter(is_active=True, perfil__activo=True)
            .filter(Q(perfil__delegacion_id__in=delegaciones)
                    | Q(perfil__delegaciones_autorizadas__in=delegaciones))
            .distinct().order_by("first_name", "last_name")
        )
        self.fields["responsables"].label_from_instance = nombre_de_usuario
        if not self.is_bound:
            self.initial["fecha"] = timezone.localdate() + timedelta(days=1)
            if usuario is not None and self.fields["responsables"].queryset.filter(pk=usuario.pk).exists():
                self.initial["responsables"] = [usuario.pk]

    def clean_fecha(self):
        fecha = self.cleaned_data["fecha"]
        if fecha < timezone.localdate():
            raise forms.ValidationError("Una salida se planifica para hoy o más adelante, no para una fecha pasada.")
        return fecha

    def clean(self):
        datos = super().clean()
        responsables = list(datos.get("responsables") or [])
        if responsables:
            vistas = set()
            for t in self.paradas:
                if t.delegacion_id in vistas:
                    continue
                vistas.add(t.delegacion_id)
                motivo = Hito.motivo_responsables(responsables, t.delegacion)
                if motivo:
                    self.add_error("responsables", motivo)
                    break
        return datos


def _paradas(request):
    """Los territorios pedidos, en el orden pedido, dentro del alcance."""
    crudos = request.POST.getlist("t") if request.method == "POST" else request.GET.getlist("t")
    if len(crudos) == 1 and "," in crudos[0]:
        crudos = crudos[0].split(",")
    ids = []
    for valor in crudos:
        valor = valor.strip()
        if valor.isdigit() and int(valor) not in ids:
            ids.append(int(valor))
    ids = ids[:MAXIMO_PARADAS]
    encontrados = {t.pk: t for t in Territorio.objects.select_related("delegacion").filter(
        pk__in=ids, activo=True, delegacion__in=M.delegaciones_de(request.user))}
    return [encontrados[i] for i in ids if i in encontrados], len(ids)


def salida(request):
    if not request.user.is_authenticated:
        return redirect_al_login(request)
    modo = _modo_o_403(request)

    paradas, pedidas = _paradas(request)
    if not paradas:
        anunciar(request, "Elige al menos un territorio",
                 "Toca «Armar una salida» en el mapa y elige los territorios que quieres visitar.",
                 icono="info")
        return redirect("gestion:mapa")

    puede_guardar = puede(request.user, "hito", "add")
    formulario = SalidaForm(request.POST if request.method == "POST" else None,
                            paradas=paradas, usuario=request.user)
    if request.method == "POST":
        if not puede_guardar:
            raise PermissionDenied("Para planificar la salida como hitos hace falta poder crear hitos.")
        if formulario.is_valid():
            hitos = _planificar(request, paradas, formulario.cleaned_data)
            anunciar(
                request, "Salida planificada",
                "Quedó como %d hito%s del %s, uno por parada. Ya aparece%s en el mapa."
                % (len(hitos), "" if len(hitos) == 1 else "s",
                   formulario.cleaned_data["fecha"].strftime("%d-%m-%Y"),
                   "" if len(hitos) == 1 else "n"),
                acciones=[("Ver los hitos", reverse("gestion:hitos")),
                          ("Volver al mapa", reverse("gestion:mapa"))],
            )
            return redirect("gestion:mapa")

    # Lo mismo que muestra el mapa, para cada parada.
    filtros = M.Filtros(request, M.delegaciones_de(request.user))
    filas = {f["id"]: f for f in M.calcular(request.user, filtros, modo)["territorios"]}
    abiertos = M.compromisos_abiertos(filtros, request.user, modo, paradas)
    hoy = timezone.localdate()

    detalle, total, anterior = [], 0.0, None
    for numero, t in enumerate(paradas, start=1):
        tramo = None
        if t.tiene_ubicacion and anterior is not None and anterior.tiene_ubicacion:
            tramo = M.distancia_km((anterior.latitud, anterior.longitud), (t.latitud, t.longitud))
            total += tramo
        detalle.append({
            "numero": numero,
            "t": t,
            "fila": filas.get(t.pk),
            "tramo": tramo,
            "compromisos": [{"c": c, "vencido": c.vencimiento and c.vencimiento < hoy}
                            for c in abiertos.get(t.pk, [])],
        })
        anterior = t

    return render(request, "gestion/salida.html", {
        "menu": "mapa",
        "personal": modo == M.PERSONAL,
        "paradas": detalle,
        "omitidas": pedidas - len(paradas),
        "total_km": total,
        "ids": ",".join(str(t.pk) for t in paradas),
        "form": formulario,
        "puede_guardar": puede_guardar,
        "maximo": MAXIMO_PARADAS,
    })


@transaction.atomic
def _planificar(request, paradas, datos):
    """Un hito por parada, con la misma fecha, los mismos responsables y la ruta completa en la descripción."""
    fecha = datos["fecha"]
    nombre = (datos.get("nombre") or "").strip() or "Salida a terreno del %s" % fecha.strftime("%d-%m")
    ruta = " → ".join(t.nombre.rsplit("·", 1)[-1].strip() for t in paradas)
    hitos = []
    for numero, t in enumerate(paradas, start=1):
        corto = t.nombre.rsplit("·", 1)[-1].strip()
        hito = Hito(
            codigo=proximo_codigo(Hito, "HIT"),
            nombre=("%s · %d de %d · %s" % (nombre, numero, len(paradas), corto))[:120],
            descripcion=("Parada %d de %d de la salida a terreno del %s: %s. "
                         "Planificada desde el mapa de presencia."
                         % (numero, len(paradas), fecha.strftime("%d-%m-%Y"), ruta)),
            periodicidad=Hito.Periodicidad.UNICA,
            fecha_inicio=fecha, fecha_termino=fecha,
            delegacion=t.delegacion, territorio=t,
        )
        hito.full_clean(exclude=["codigo"])
        hito.save()
        hito.responsables.set(datos["responsables"])
        registrar(request, EventoAuditoria.Accion.CREAR, entidad="Hito", objeto=hito,
                  despues=hito.nombre, detalle="Salida a terreno armada en el mapa de presencia.")
        hitos.append(hito)
    return hitos

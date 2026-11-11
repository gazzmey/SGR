"""
Los casos sociales: el seguimiento de una atención con sus plazos.

Son las hojas G SOC de la matriz SGR. Abre y lleva un caso quien registra
atención ciudadana; lo consulta también quien conduce la delegación. El
alcance es el de siempre: solo los casos de las delegaciones que el perfil
autoriza, y uno de otra delegación responde «no existe».
"""

from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html
from django.views.decorators.http import require_POST

from atencion import plazos
from atencion.forms import CasoSocialForm
from atencion.models import Atencion, CasoSocial
from comun import concurrencia, observaciones, permisos as P
from comun.mantenedor import Columna, Filtro, ListaMantenedor, auditar
from comun.permisos import redirect_al_login, tiene_permiso
from comun.resultado import anunciar
from comun.utilidades import proximo_codigo
from gestion import reglas as R


def puede_ver(usuario):
    return tiene_permiso(usuario, P.REGISTRAR_ATENCION) or tiene_permiso(usuario, P.VER_TABLERO)


def _visibles(usuario):
    """Los identificadores de delegación que esa persona puede ver."""
    perfil = P.perfil_de(usuario)
    if perfil is None:
        return None
    return list(perfil.delegaciones_visibles().values_list("pk", flat=True))


def _regla():
    from gestion.views_actividad import periodo_abierto

    return R.vigente(periodo_abierto())


def _nombre(usuario):
    return usuario.get_full_name() or usuario.get_username()


# =========================================================================
# El listado
# =========================================================================


class CasosLista(ListaMantenedor):
    model = CasoSocial
    campo_delegacion = "atencion__delegacion_id"
    menu = "casos"
    titulo = "Casos sociales"
    bajada = (
        "El seguimiento de cada atención social hasta su cierre: visita, "
        "informe y beneficio, con el plazo de cada paso."
    )
    singular = "caso"
    plural = "casos"
    genero = "el"
    placeholder = "Código, solicitante, subatención u observación"
    busca = ["codigo", "atencion__solicitante__nombre",
             "atencion__subatencion__nombre", "observacion"]
    orden_inicial = "-ingreso"
    url_lista = "atencion:casos"
    url_detalle = "atencion:caso"

    filtros = [
        Filtro("situacion", "Situación",
               [("abiertos", "Abiertos"), ("cerrados", "Cerrados")],
               consulta=lambda v: Q(), vacio="Todos"),
        Filtro("quien", "Profesional", [("mios", "Los míos")],
               consulta=lambda v: Q(), vacio="Toda la delegación"),
    ]

    columnas = [
        Columna("codigo", "Código", clase="mono"),
        Columna("solicitante", "Caso", orden="atencion__solicitante__nombre", clase="w",
                celda=lambda o: format_html(
                    '<a class="link" href="{}">{}</a><span class="t2">{}</span>',
                    reverse("atencion:caso", args=[o.pk]),
                    o.atencion.solicitante.nombre, o.atencion.subatencion.nombre),
                valor=lambda o: o.atencion.solicitante.nombre),
        Columna("ingreso", "Ingreso",
                valor=lambda o: o.ingreso.strftime("%d-%m-%Y")),
        Columna("responsable", "Profesional", orden="responsable__first_name",
                valor=lambda o: _nombre(o.responsable)),
        Columna("paso", "Paso", orden="",
                celda=lambda o: format_html('{}<span class="t2">{}</span>',
                                            o.siguiente_paso, o._detalle_paso),
                valor=lambda o: o.siguiente_paso),
        Columna("plazos", "Plazos", orden="",
                celda=lambda o: format_html('<span class="chip {}">{}</span>',
                                            o._situacion[2], o._situacion[1]),
                valor=lambda o: o._situacion[1]),
    ]

    excel_columnas = [
        Columna("codigo", "Código"),
        Columna("solicitante", "Solicitante", valor=lambda o: o.atencion.solicitante.nombre),
        Columna("subatencion", "Subatención", valor=lambda o: o.atencion.subatencion.nombre),
        Columna("delegacion", "Delegación", valor=lambda o: o.atencion.delegacion.nombre),
        Columna("responsable", "Profesional", valor=lambda o: _nombre(o.responsable)),
        Columna("ingreso", "Ingreso", valor=lambda o: o.ingreso.strftime("%d-%m-%Y")),
        Columna("visita_programada", "Visita programada",
                valor=lambda o: o.visita_programada.strftime("%d-%m-%Y") if o.visita_programada else ""),
        Columna("visita_realizada", "Visita realizada",
                valor=lambda o: o.visita_realizada.strftime("%d-%m-%Y") if o.visita_realizada else ""),
        Columna("informe_entregado", "Informe",
                valor=lambda o: o.informe_entregado.strftime("%d-%m-%Y") if o.informe_entregado else ""),
        Columna("beneficio_entregado", "Beneficio",
                valor=lambda o: o.beneficio_entregado.strftime("%d-%m-%Y") if o.beneficio_entregado else ""),
        Columna("devoluciones", "Devoluciones del informe"),
        Columna("plazos", "Plazos", valor=lambda o: o._situacion[1]),
    ]

    nota = (
        "<b>El caso lleva el reloj; la meta la llevan las actividades.</b> La "
        "visita, el informe y la entrega del beneficio se siguen registrando "
        "en Mis actividades con su evidencia, que es lo que cuenta para el "
        "resultado. Aquí se ve cuánto tardó cada paso contra los plazos de la "
        "matriz."
    )

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_al_login(request)
        if not puede_ver(request.user):
            raise PermissionDenied("Los casos los ven quienes atienden y quienes conducen la delegación.")
        return super().dispatch(request, *args, **kwargs)

    def base_queryset(self):
        consulta = CasoSocial.objects.select_related(
            "atencion__solicitante", "atencion__subatencion", "atencion__delegacion",
            "responsable")
        situacion = self.request.GET.get("situacion")
        abiertos = (Q(lleva_beneficio=True, beneficio_entregado__isnull=True)
                    | Q(lleva_beneficio=False, informe_entregado__isnull=True))
        if situacion == "abiertos":
            consulta = consulta.filter(abiertos)
        elif situacion == "cerrados":
            consulta = consulta.exclude(abiertos)
        if self.request.GET.get("quien") == "mios":
            consulta = consulta.filter(responsable=self.request.user)
        return consulta

    @staticmethod
    def _situar(casos, regla, hoy):
        """Cuelga de cada caso su situación y el detalle de su paso pendiente."""
        for caso in casos:
            caso._situacion = plazos.situacion(caso, regla, hoy)
            pendientes = [t for t in plazos.tramos(caso, regla, hoy)
                          if t.fin is None and t.inicio is not None and t.clave != "total"]
            caso._detalle_paso = pendientes[0].detalle if pendientes else ""

    def paginate_queryset(self, queryset, page_size):
        # La situación se calcula con fechas, no en la base, así que se
        # resuelve aquí sobre la página ya cortada: las columnas la leen al
        # dibujarse y no se calcula para casos que no se muestran.
        resultado = super().paginate_queryset(queryset, page_size)
        pagina = resultado[1]
        self._situar(pagina.object_list, _regla(), timezone.localdate())
        return resultado

    def get_context_data(self, **kwargs):
        regla = _regla()
        contexto = super().get_context_data(**kwargs)
        todos = list(self.limitar(self.base_queryset_sin_filtros()))
        contexto.update({
            "antes_del_listado": "atencion/_resumen_casos.html",
            "tiempos": plazos.resumen(todos, regla, timezone.localdate()),
            "regla": regla,
        })
        return contexto

    def base_queryset_sin_filtros(self):
        return CasoSocial.objects.all()

    def _exportar(self):
        filas = list(self.get_queryset())
        self._situar(filas, _regla(), timezone.localdate())
        from comun.excel import libro_de_listado

        return libro_de_listado(
            titulo="Casos sociales", filtro=self.describir_filtros() or "sin filtros",
            columnas=self.excel_columnas, filas=filas, archivo="SGR_casos_sociales",
        )


# =========================================================================
# Abrir y llevar un caso
# =========================================================================


@require_POST
def caso_abrir(request, atencion_pk):
    """Abre el seguimiento de una atención. Si ya lo tiene, lleva a él."""
    if not request.user.is_authenticated:
        return redirect_al_login(request)
    if not tiene_permiso(request.user, P.REGISTRAR_ATENCION):
        raise PermissionDenied("No tienes permiso para abrir casos.")

    consulta = Atencion.objects.select_related("funcionario", "delegacion")
    visibles = _visibles(request.user)
    if visibles is not None:
        consulta = consulta.filter(delegacion_id__in=visibles)
    atencion = get_object_or_404(consulta, pk=atencion_pk)

    existente = CasoSocial.objects.filter(atencion=atencion).first()
    if existente is not None:
        return redirect("atencion:caso", pk=existente.pk)

    responsable = atencion.funcionario
    perfil = getattr(responsable, "perfil", None)
    if not responsable.is_active or perfil is None or perfil.delegacion_id != atencion.delegacion_id:
        responsable = request.user

    caso = CasoSocial.objects.create(
        atencion=atencion,
        codigo=proximo_codigo(CasoSocial, "CSO", ancho=3),
        responsable=responsable,
        ingreso=timezone.localtime(atencion.registrada).date(),
    )
    auditar(request, "crear", caso, entidad="Caso social",
            despues=f"atención Nº {atencion.pk}")
    anunciar(request, "Caso abierto",
             f"{caso.codigo} queda a cargo de {_nombre(responsable)}. Desde hoy "
             "corre el plazo para programar la visita.")
    return redirect("atencion:caso", pk=caso.pk)


def caso_detalle(request, pk):
    """La ficha del caso: sus fechas, que se corrigen aquí, y sus plazos."""
    if not request.user.is_authenticated:
        return redirect_al_login(request)
    if not puede_ver(request.user):
        raise PermissionDenied("No tienes permiso para ver casos.")

    consulta = CasoSocial.objects.select_related(
        "atencion__solicitante", "atencion__subatencion__tipo_atencion",
        "atencion__delegacion", "atencion__funcionario", "responsable")
    visibles = _visibles(request.user)
    if visibles is not None:
        consulta = consulta.filter(atencion__delegacion_id__in=visibles)
    caso = get_object_or_404(consulta, pk=pk)

    puede_editar = tiene_permiso(request.user, P.REGISTRAR_ATENCION)
    huella = concurrencia.huella(caso)
    formulario = CasoSocialForm(request.POST or None, instance=caso)
    conflicto, cambios = False, []

    if request.method == "POST":
        if not puede_editar:
            raise PermissionDenied("Puedes consultar el caso, pero no modificarlo.")
        if concurrencia.hay_conflicto(request, caso):
            # Otra persona guardó fechas mientras este formulario estaba
            # abierto (HU-23): no se pisa, se muestra la diferencia.
            conflicto, cambios = True, concurrencia.diferencias(formulario)
        elif formulario.is_valid():
            cambios = ", ".join(formulario.changed_data[:6])
            formulario.save()
            auditar(request, "editar", caso, entidad="Caso social", despues=cambios)
            anunciar(request, "Caso actualizado",
                     f"{caso.codigo}: {caso.siguiente_paso.lower()}."
                     if not caso.cerrado else f"{caso.codigo} quedó cerrado.")
            return redirect("atencion:caso", pk=caso.pk)

    regla = _regla()
    hoy = timezone.localdate()
    return render(request, "atencion/caso.html", {
        "menu": "casos",
        "caso": caso,
        "form": formulario,
        "huella": huella,
        "campo_huella": concurrencia.CAMPO,
        "conflicto": conflicto,
        "conflicto_cambios": cambios,
        "hilo": observaciones.hilo(request, "caso", caso),
        "puede_editar": puede_editar,
        "tramos": plazos.tramos(caso, regla, hoy),
        "situacion": plazos.situacion(caso, regla, hoy),
        "regla": regla,
    })

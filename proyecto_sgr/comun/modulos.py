"""
Las tarjetas de módulos de «Mi panel».

Cada módulo del sistema se presenta como una tarjeta: una banda con el color
de su área, el nombre de la pantalla, su estado para quien mira —«3 sin
evidencia», «Sin vencidos»— y unos pocos datos. Es la pantalla de entrada:
lo que hay que atender salta a la vista antes de abrir nada.

Qué tarjetas ve cada persona
----------------------------
Las mismas que el menú de la izquierda, con las mismas condiciones de
permiso. Que el panel muestre una tarjeta no da acceso a nada: la vista de
destino vuelve a comprobar el permiso, como siempre.

Por qué un estado que falla no tumba el panel
---------------------------------------------
El panel es lo primero que se abre al entrar. Si el recuento de una tarjeta
fallara —un dato inesperado, una tabla a medio migrar— la persona se quedaría
sin poder entrar a ningún módulo. Así que cada estado se calcula aparte y,
si falla, esa tarjeta se muestra sin estado. Es el mismo criterio de la
auditoría y de las versiones: anotar no puede impedir trabajar.
"""

from dataclasses import dataclass, field
from datetime import date

from django.urls import reverse
from django.utils.safestring import mark_safe

from comun import permisos as P

# =========================================================================
# Áreas y su color
# =========================================================================

#: clave → (nombre, clase de color). Los nombres son los de las secciones
#: del menú lateral; los colores salen de la paleta del SGR (sgr.css): rojo
#: institucional, bordó, ocre, granate, grafito y tinta.
AREAS = {
    "gestion": ("Mi gestión", "a-rojo"),
    "comunidad": ("Comunidad", "a-bordo"),
    "supervision": ("Supervisión", "a-ocre"),
    "periodo": ("Período", "a-granate"),
    "configuracion": ("Configuración", "a-grafito"),
    "administracion": ("Administración", "a-tinta"),
}

# Los íconos son los del menú lateral, para que la tarjeta y el menú se
# reconozcan como lo mismo.
ICONOS = {
    "resultado": '<path d="M4 19.5h16"/><path d="M7 19.5v-6M12 19.5V7M17 19.5v-9"/>',
    "actividades": '<path d="M8 5.5h11M8 12h11M8 18.5h11"/><path d="M4 5.5h.01M4 12h.01M4 18.5h.01"/>',
    "agenda": '<rect x="3.5" y="5" width="17" height="15" rx="2"/><path d="M8 3.5v3M16 3.5v3M3.5 10h17"/><path d="m9 14.5 1.8 1.8L15 12.5"/>',
    "observaciones": '<path d="M20 11.5a7.5 7.5 0 0 1-11 6.6L4 19.5l1.4-4.4A7.5 7.5 0 1 1 20 11.5z"/>',
    "cartas": '<rect x="3.5" y="5.5" width="17" height="13" rx="2"/><path d="m4 7 8 6 8-6"/>',
    "atencion": '<path d="M8 10.5h8M8 14h5"/><path d="M4.5 5.5h15a1.5 1.5 0 0 1 1.5 1.5v9a1.5 1.5 0 0 1-1.5 1.5H9l-4.5 3.5V18H4.5A1.5 1.5 0 0 1 3 16.5V7a1.5 1.5 0 0 1 1.5-1.5z"/>',
    "casos": '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>',
    "regalos": '<rect x="3.5" y="9" width="17" height="11.5" rx="1.5"/><path d="M3.5 13h17M12 9v11.5"/><path d="M12 9c-1.5-3.5-5.5-4-5.5-1.5S10 9 12 9zM12 9c1.5-3.5 5.5-4 5.5-1.5S14 9 12 9z"/>',
    "validar": '<path d="m5 12.5 4.5 4.5L19 7.5"/><path d="M3 19.5h18"/>',
    "alertas": '<path d="M18 8.5a6 6 0 1 0-12 0c0 5-2 6.5-2 6.5h16s-2-1.5-2-6.5z"/><path d="M13.7 19a2 2 0 0 1-3.4 0"/>',
    "tablero": '<rect x="3.5" y="4" width="17" height="16" rx="2"/><path d="M8 16V9.5M12 16v-4M16 16v-7"/>',
    "reconocimientos": '<path d="M4.5 5.5h15a1.5 1.5 0 0 1 1.5 1.5v9a1.5 1.5 0 0 1-1.5 1.5H9l-4.5 3.5V18H4.5A1.5 1.5 0 0 1 3 16.5V7a1.5 1.5 0 0 1 1.5-1.5z"/><path d="M12 9v4.5M9.75 11.25h4.5"/>',
    "ausencias": '<rect x="3.5" y="5" width="17" height="15" rx="2"/><path d="M8 3.5v3M16 3.5v3M3.5 10h17"/><path d="M9 15h6"/>',
    "informes": '<path d="M6 3.5h8l4.5 4.5v12.5H6z"/><path d="M14 3.5V8h4.5"/><path d="M9 17v-3.5M12 17v-6M15 17v-2"/>',
    "periodos": '<rect x="3.5" y="5" width="17" height="15" rx="2"/><path d="M3.5 10h17M8 3.5v3M16 3.5v3"/>',
    "cargos": '<path d="M7 20.5v-2a3 3 0 0 1 3-3h4a3 3 0 0 1 3 3v2"/><circle cx="12" cy="8" r="3.5"/>',
    "metas": '<circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="3.5"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2"/>',
    "reglas": '<path d="M5 7h14M5 12h14M5 17h9"/><circle cx="9" cy="7" r="2.2"/><circle cx="15" cy="12" r="2.2"/><circle cx="17" cy="17" r="2.2"/>',
    "historial": '<path d="M3.5 12a8.5 8.5 0 1 0 2.5-6"/><path d="M3.5 4.5V9H8"/><path d="M12 7.5V12l3 2"/>',
    "campanas": '<rect x="3.5" y="9" width="17" height="11.5" rx="1.5"/><path d="M3.5 13h17M12 9v11.5"/>',
    "items": '<path d="M4 19.5h16"/><path d="M7 19.5V9M12 19.5V4.5M17 19.5v-7"/>',
    "tipos": '<rect x="3.5" y="4.5" width="17" height="15" rx="2"/><path d="M3.5 9.5h17M8.5 4.5v15"/>',
    "delegaciones": '<path d="M3 21h18M5 21V8.5l7-4.5 7 4.5V21"/><path d="M10 21v-5h4v5"/><path d="M9 11h.01M15 11h.01"/>',
    "usuarios": '<circle cx="12" cy="8" r="3.8"/><path d="M4.5 20c.7-4 3.6-6 7.5-6s6.8 2 7.5 6"/>',
    "roles": '<path d="M12 3 4.5 6v5.5c0 4.6 3.2 8.1 7.5 9.5 4.3-1.4 7.5-4.9 7.5-9.5V6z"/><path d="M12 9.5v5M9.5 12h5"/>',
    "auditoria": '<path d="M6 3.5h8l4.5 4.5v12.5H6z"/><path d="M14 3.5V8h4.5"/><path d="M9 13h6M9 16.5h4"/>',
}

#: Los íconos chicos de los datos del pie.
ICONOS_DATO = {
    "periodo": '<rect x="3.5" y="5" width="17" height="15" rx="2"/><path d="M3.5 10h17M8 3.5v3M16 3.5v3"/>',
    "delegacion": '<path d="M12 21s-6.5-5.6-6.5-11a6.5 6.5 0 1 1 13 0c0 5.4-6.5 11-6.5 11z"/><circle cx="12" cy="10" r="2.3"/>',
    "cuenta": '<path d="M5 12.5 9.5 17 19 7.5"/>',
    "reloj": '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>',
    "persona": '<circle cx="12" cy="8" r="3.8"/><path d="M4.5 20c.7-4 3.6-6 7.5-6s6.8 2 7.5 6"/>',
}


# =========================================================================
# Las piezas
# =========================================================================


@dataclass
class Estado:
    """La píldora de estado: un texto corto y su tono (ok, warn, bad, line)."""

    texto: str
    tono: str = "line"


@dataclass
class Dato:
    texto: str
    icono: str = "cuenta"

    @property
    def svg(self):
        return mark_safe(ICONOS_DATO.get(self.icono, ICONOS_DATO["cuenta"]))


@dataclass
class Tarjeta:
    clave: str
    area: str
    titulo: str
    tipo: str
    descripcion: str
    url: str
    nuevo: bool = False
    estado: Estado | None = None
    datos: list = field(default_factory=list)

    @property
    def area_nombre(self):
        return AREAS[self.area][0]

    @property
    def area_clase(self):
        return AREAS[self.area][1]

    @property
    def icono(self):
        return mark_safe(ICONOS[self.clave])


# =========================================================================
# Los estados: un recuento cada uno, y nada más
# =========================================================================


def _periodo():
    from gestion.views_actividad import periodo_abierto

    return periodo_abierto()


def _mi_resultado(ctx):
    from gestion import calculo as C

    if ctx["perfil"] is None or ctx["periodo"] is None:
        return None, []
    res = C.de_perfil(ctx["perfil"], ctx["periodo"])
    datos = [Dato(ctx["periodo"].codigo, "periodo"),
             Dato(f"Día {res.dias_transcurridos} de {res.dias_totales}", "reloj")]
    if not res.definido:
        return Estado("Sin metas para medir", "line"), datos
    tono = {"verde": "ok", "ambar": "warn", "rojo": "bad"}.get(res.semaforo_clase, "line")
    avance = f"{res.avance:.1f}".replace(".", ",")
    return Estado(f"{avance} % · {res.semaforo_texto}", tono), datos


def _actividades(ctx):
    from gestion.modelos_actividad import Actividad

    if ctx["periodo"] is None:
        return Estado("No hay un período abierto", "line"), []
    mias = Actividad.objects.filter(funcionario=ctx["usuario"], periodo=ctx["periodo"])
    sin_evidencia = mias.filter(estado=Actividad.Estado.BORRADOR).count()
    rechazadas = mias.filter(estado=Actividad.Estado.RECHAZADA).count()
    aprobadas = mias.filter(estado=Actividad.Estado.APROBADA).count()
    datos = [Dato(f"{aprobadas} aprobada{'' if aprobadas == 1 else 's'}", "cuenta"),
             Dato(ctx["periodo"].codigo, "periodo")]
    if rechazadas:
        return Estado(f"{rechazadas} rechazada{'' if rechazadas == 1 else 's'} por corregir", "bad"), datos
    if sin_evidencia:
        return Estado(f"{sin_evidencia} sin evidencia", "warn"), datos
    return Estado("Todo con evidencia", "ok"), datos


def _agenda(ctx):
    from gestion.modelos_agenda import Compromiso

    if ctx["activa"] is None:
        return None, []
    abiertos = Compromiso.objects.filter(
        delegacion=ctx["activa"], estado__in=Compromiso.ABIERTOS)
    vencidos = abiertos.filter(vencimiento__lt=ctx["hoy"]).count()
    total = abiertos.count()
    datos = [Dato(f"{total} abierto{'' if total == 1 else 's'}", "cuenta"),
             Dato(ctx["activa"].codigo, "delegacion")]
    if vencidos:
        return Estado(f"{vencidos} vencido{'' if vencidos == 1 else 's'}", "bad"), datos
    return Estado("Sin vencidos", "ok"), datos


def _cartas(ctx):
    from gestion.modelos_cartas import Carta

    if ctx["activa"] is None:
        return None, []
    en_proceso = Carta.objects.filter(
        delegacion=ctx["activa"], activo=True, estado=Carta.Estado.EN_PROCESO).count()
    datos = [Dato(ctx["activa"].codigo, "delegacion")]
    if en_proceso:
        return Estado(f"{en_proceso} en proceso", "warn"), datos
    return Estado("Ninguna esperando respuesta", "ok"), datos


def _atencion(ctx):
    from atencion.models import Atencion

    if ctx["activa"] is None:
        return None, []
    de_aqui = Atencion.objects.filter(delegacion=ctx["activa"])
    hoy = de_aqui.filter(registrada__date=ctx["hoy"]).count()
    mes = de_aqui.filter(registrada__date__gte=ctx["hoy"].replace(day=1)).count()
    return (Estado(f"{hoy} registrada{'' if hoy == 1 else 's'} hoy", "line"),
            [Dato(f"{mes} este mes", "cuenta"), Dato(ctx["activa"].codigo, "delegacion")])


def _casos(ctx):
    from atencion import plazos
    from atencion.models import CasoSocial
    from gestion import reglas as R

    if ctx["activa"] is None:
        return None, []
    regla = R.vigente(ctx["periodo"])
    abiertos = [c for c in CasoSocial.objects.filter(atencion__delegacion=ctx["activa"])
                .select_related("atencion") if not c.cerrado]
    vencidos = sum(1 for c in abiertos if plazos.situacion(c, regla)[0] == "vencido")
    datos = [Dato(f"{len(abiertos)} abierto{'' if len(abiertos) == 1 else 's'}", "cuenta"),
             Dato(ctx["activa"].codigo, "delegacion")]
    if vencidos:
        return Estado(f"{vencidos} con un plazo vencido", "bad"), datos
    return Estado("Abiertos al día", "ok"), datos


def _validar(ctx):
    from gestion.modelos_actividad import Evidencia

    pendientes = Evidencia.objects.filter(decision=Evidencia.Decision.PENDIENTE)
    if ctx["visibles"] is not None:
        pendientes = pendientes.filter(actividad__delegacion_id__in=ctx["visibles"])
    cuantas = pendientes.count()
    if cuantas:
        return Estado(f"{cuantas} esperando decisión", "warn"), []
    return Estado("Nada pendiente", "ok"), []


def _periodos(ctx):
    if ctx["periodo"] is None:
        return Estado("Ningún período abierto", "warn"), []
    p = ctx["periodo"]
    return (Estado(f"{p.codigo} abierto", "ok"),
            [Dato(f"Hasta el {p.termino:%d-%m-%Y}", "periodo")])


def _reglas(ctx):
    from gestion import reglas as R

    regla = R.vigente(ctx["periodo"])
    if not regla.pk or regla.es_propuesta:
        return Estado("Propuesta, sin aprobar", "warn"), []
    return Estado("Aprobada", "ok"), []


def _historial(ctx):
    from gestion.modelos_versiones import VersionParametro

    cuantas = VersionParametro.objects.count()
    if not cuantas:
        return None, [Dato("Sin cambios todavía", "reloj")]
    return None, [Dato(f"{cuantas} versi{'ón' if cuantas == 1 else 'ones'}", "cuenta")]


def _contar(modelo, texto, **filtro):
    def calcular(ctx):
        cuantos = modelo().objects.filter(**filtro).count()
        return None, [Dato(texto % cuantos, "cuenta")]
    return calcular


def _auditoria(ctx):
    from comun.models import EventoAuditoria

    hoy = EventoAuditoria.objects.filter(cuando__date=ctx["hoy"]).count()
    return None, [Dato(f"{hoy} evento{'' if hoy == 1 else 's'} hoy", "reloj")]


def _modelo(ruta):
    def cargar():
        from django.apps import apps

        return apps.get_model(ruta)
    return cargar


# =========================================================================
# El catálogo de módulos
# =========================================================================

#: (clave, área, título, tipo, descripción, url, permiso, estado, nuevo)
#: ``permiso`` recibe la función ``tiene`` y dice si la persona ve la tarjeta:
#: es la misma condición que usa el menú en base.html.
MODULOS = (
    ("resultado", "gestion", "Mi resultado", "Consulta",
     "Tu cumplimiento por ítem frente a lo esperado a la fecha.",
     "gestion:mi_resultado", lambda t: True, _mi_resultado, False),
    ("actividades", "gestion", "Mis actividades", "Registro",
     "Lo que hiciste, con su evidencia, para que cuente en tu meta.",
     "gestion:actividades", lambda t: t(P.REGISTRAR_ACTIVIDAD), _actividades, False),

    ("agenda", "comunidad", "Agenda de compromisos", "Registro",
     "Lo comprometido con la comunidad, con plazo y responsable.",
     "gestion:agenda", lambda t: True, _agenda, False),
    ("observaciones", "comunidad", "Observaciones", "Consulta",
     "Consultas y comentarios en compromisos, casos y cartas.",
     "comun:observaciones", lambda t: True, None, True),
    ("cartas", "comunidad", "Tubo de cartas", "Registro",
     "Las cartas de oficina de partes y en qué quedó cada una.",
     "gestion:cartas", lambda t: t(P.REGISTRAR_ATENCION) or t(P.VER_TABLERO), _cartas, False),
    ("atencion", "comunidad", "Atención ciudadana", "Registro",
     "Registra a quien vino a la delegación y qué se le entregó.",
     "atencion:ingreso", lambda t: t(P.REGISTRAR_ATENCION), _atencion, False),
    ("casos", "comunidad", "Casos sociales", "Seguimiento",
     "Visita, informe y beneficio, con el plazo de cada paso.",
     "atencion:casos", lambda t: t(P.REGISTRAR_ATENCION) or t(P.VER_TABLERO), _casos, False),
    ("regalos", "comunidad", "Regalos para niños", "Registro",
     "Inscripción por RUT en cada campaña, sin duplicados.",
     "atencion:regalos", lambda t: t(P.REGISTRAR_ATENCION) or t(P.VER_TABLERO), None, False),

    ("validar", "supervision", "Validar evidencias", "Revisión",
     "Aprueba o rechaza con motivo lo que registró el equipo.",
     "gestion:validar", lambda t: t(P.VALIDAR_EVIDENCIA), _validar, False),
    ("alertas", "supervision", "Alertas", "Seguimiento",
     "Lo que necesita atención: vencimientos, evidencias, registros.",
     "gestion:alertas", lambda t: t(P.VER_TABLERO), None, False),
    ("tablero", "supervision", "Tablero de delegación", "Consulta",
     "El resultado de cada persona y el indicador de la agenda.",
     "gestion:tablero", lambda t: t(P.VER_TABLERO), None, False),
    ("reconocimientos", "supervision", "Felicitaciones y reclamos", "Registro",
     "Lo que escribió la comunidad; suma o resta al resultado.",
     "gestion:reconocimientos", lambda t: t(P.REGISTRAR_AJUSTE), None, False),
    ("ausencias", "supervision", "Ausencias", "Registro",
     "Licencias y vacaciones, que bajan el avance esperado.",
     "gestion:ausencias", lambda t: t(P.REGISTRAR_AJUSTE), None, False),
    ("informes", "supervision", "Informes", "Consulta",
     "Seis informes consolidados, incluido el de brechas por cargo.",
     "gestion:informes", lambda t: t(P.VER_INFORMES), None, False),

    ("periodos", "periodo", "Períodos", "Configuración",
     "Abrir, cerrar y reabrir el período que se mide.",
     "gestion:periodos", lambda t: t(P.CONFIGURAR_PERIODO), _periodos, False),
    ("cargos", "periodo", "Cargos", "Configuración",
     "Las funciones de cada cargo, que deciden sus metas.",
     "gestion:cargos", lambda t: t(P.DEFINIR_META), None, False),
    ("metas", "periodo", "Metas y ponderadores", "Configuración",
     "Cuánto se pide y cuánto pesa cada ítem, por cargo.",
     "gestion:metas", lambda t: t(P.DEFINIR_META), None, False),
    ("reglas", "periodo", "Reglas de cálculo", "Configuración",
     "Tope, umbrales y plazos, sin tocar código.",
     "gestion:reglas", lambda t: t(P.CONFIGURAR_PERIODO), _reglas, False),
    ("historial", "periodo", "Historial de parámetros", "Consulta",
     "Cada versión de ítems, metas y reglas, con su autor.",
     "gestion:historial", lambda t: t(P.CONFIGURAR_PERIODO), _historial, True),
    ("campanas", "periodo", "Campañas de regalos", "Configuración",
     "Navidad, Día del Niño y Aniversario, con sus fechas.",
     "atencion:campanas", lambda t: t(P.CONFIGURAR_PERIODO), None, False),
    ("items", "configuracion", "Ítems y metas", "Catálogo",
     "Lo que se mide y cómo se mide.",
     "catalogos:items", lambda t: t(P.GESTIONAR_CATALOGO),
     _contar(_modelo("catalogos.Item"), "%d activos", activo=True), False),
    ("tipos", "configuracion", "Tipos de atención", "Catálogo",
     "Cómo se clasifica lo que se atiende, con sus subatenciones.",
     "catalogos:tipos", lambda t: t(P.GESTIONAR_CATALOGO),
     _contar(_modelo("catalogos.TipoAtencion"), "%d activos", activo=True), False),

    ("delegaciones", "administracion", "Delegaciones", "Administración",
     "Las unidades territoriales y sus datos de contacto.",
     "organizacion:delegaciones", lambda t: t(P.GESTIONAR_USUARIO),
     _contar(_modelo("organizacion.Delegacion"), "%d activas", activo=True), False),
    ("usuarios", "administracion", "Usuarios", "Administración",
     "Quién entra, con qué rol y a qué delegaciones.",
     "organizacion:usuarios", lambda t: t(P.GESTIONAR_USUARIO),
     _contar(_modelo("organizacion.PerfilUsuario"), "%d con acceso", activo=True), False),
    ("roles", "administracion", "Roles", "Administración",
     "Qué puede hacer cada rol, y sobre qué delegaciones.",
     "organizacion:roles", lambda t: t(P.GESTIONAR_USUARIO),
     _contar(_modelo("organizacion.Rol"), "%d definidos", activo=True), False),
    ("auditoria", "administracion", "Auditoría", "Consulta",
     "Las operaciones críticas: quién, qué y cuándo.",
     "gestion:auditoria", lambda t: t(P.VER_AUDITORIA), _auditoria, False),
)


def tarjetas_de(request, activa):
    """Las tarjetas que ve esta persona, en el orden del menú."""
    usuario = request.user
    perfil = P.perfil_de(usuario)
    visibles = None
    if perfil is not None:
        visibles = list(perfil.delegaciones_visibles().values_list("pk", flat=True))

    def tiene(permiso):
        return P.tiene_permiso(usuario, permiso)

    ctx = {
        "usuario": usuario, "perfil": perfil, "activa": activa,
        "visibles": visibles, "periodo": _periodo(), "hoy": date.today(),
    }

    tarjetas = []
    for clave, area, titulo, tipo, descripcion, url, permiso, estado, nuevo in MODULOS:
        if not permiso(tiene):
            continue
        tarjeta = Tarjeta(clave=clave, area=area, titulo=titulo, tipo=tipo,
                          descripcion=descripcion, url=reverse(url), nuevo=nuevo)
        if estado is not None:
            try:
                tarjeta.estado, tarjeta.datos = estado(ctx)
            except Exception:  # noqa: BLE001 — ver la explicación del módulo
                tarjeta.estado, tarjeta.datos = None, []
        tarjetas.append(tarjeta)
    return tarjetas

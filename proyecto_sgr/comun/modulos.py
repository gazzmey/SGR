"""
Lo que muestra «Mi panel».

El panel responde tres preguntas, en este orden:

    Para atender      qué necesita acción hoy: lo vencido, lo rechazado,
                      lo que espera una decisión. Solo eso.
    Tu avance         cómo va la persona frente a lo esperado a la fecha;
                      quien supervisa ve, en cambio, cómo van sus
                      delegaciones.
    Tus módulos       a dónde ir, agrupado por las mismas áreas del menú,
                      con una línea de qué hace cada pantalla.

El color se reserva para dos cosas: la banda de cada área y el punto rojo o
ámbar de lo que hay que atender. El resto es blanco y papel, para que la
pantalla se lea sin cansar.

Qué ve cada persona
-------------------
Los módulos y los pendientes siguen los mismos permisos que el menú. Que el
panel muestre algo no da acceso a nada: la vista de destino vuelve a
comprobar el permiso, como siempre.

Por qué un recuento que falla no tumba el panel
-----------------------------------------------
El panel es lo primero que se abre al entrar. Si un recuento fallara —un
dato inesperado, una tabla a medio migrar— la persona se quedaría sin poder
entrar a ningún módulo. Así que cada parte se calcula aparte y, si falla, se
omite. Es el mismo criterio de la auditoría y de las versiones: informar no
puede impedir trabajar.
"""

from dataclasses import dataclass, field
from datetime import date

from django.urls import reverse
from django.utils.safestring import mark_safe

from comun import permisos as P

# =========================================================================
# Áreas y módulos
# =========================================================================

#: clave → (nombre, clase de color, ícono). Los nombres son los de las
#: secciones del menú lateral; los colores salen de la paleta del SGR
#: (sgr.css): rojo institucional, bordó, ocre, granate, grafito y tinta.
AREAS = {
    "gestion": ("Mi gestión", "a-rojo", "resultado"),
    "comunidad": ("Comunidad", "a-bordo", "agenda"),
    "supervision": ("Supervisión", "a-ocre", "tablero"),
    "periodo": ("Período", "a-granate", "periodos"),
    "configuracion": ("Configuración", "a-grafito", "items"),
    "administracion": ("Administración", "a-tinta", "delegaciones"),
}

# Los íconos son los del menú lateral, para que el panel y el menú se
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
    "subatenciones": '<path d="M5 4v10a3 3 0 0 0 3 3h11"/><path d="m15.5 13.5 3.5 3.5-3.5 3.5"/>',
    "delegaciones": '<path d="M3 21h18M5 21V8.5l7-4.5 7 4.5V21"/><path d="M10 21v-5h4v5"/><path d="M9 11h.01M15 11h.01"/>',
    "usuarios": '<circle cx="12" cy="8" r="3.8"/><path d="M4.5 20c.7-4 3.6-6 7.5-6s6.8 2 7.5 6"/>',
    "roles": '<path d="M12 3 4.5 6v5.5c0 4.6 3.2 8.1 7.5 9.5 4.3-1.4 7.5-4.9 7.5-9.5V6z"/><path d="M12 9.5v5M9.5 12h5"/>',
    "auditoria": '<path d="M6 3.5h8l4.5 4.5v12.5H6z"/><path d="M14 3.5V8h4.5"/><path d="M9 13h6M9 16.5h4"/>',
}


def _todos(t):
    return True


#: (clave, área, título, qué hace, url, permiso, nuevo). ``permiso`` recibe
#: la función ``tiene`` y repite la condición del menú en base.html.
MODULOS = (
    ("resultado", "gestion", "Mi resultado",
     "Tu cumplimiento por ítem frente a lo esperado.",
     "gestion:mi_resultado", _todos, False),
    ("actividades", "gestion", "Mis actividades",
     "Lo que hiciste, con su evidencia.",
     "gestion:actividades", lambda t: t(P.REGISTRAR_ACTIVIDAD), False),

    ("agenda", "comunidad", "Agenda de compromisos",
     "Lo comprometido con la comunidad, con plazo.",
     "gestion:agenda", _todos, False),
    ("observaciones", "comunidad", "Observaciones",
     "Consultas en compromisos, casos y cartas.",
     "comun:observaciones", _todos, True),
    ("cartas", "comunidad", "Tubo de cartas",
     "Las cartas de oficina de partes.",
     "gestion:cartas", lambda t: t(P.REGISTRAR_ATENCION) or t(P.VER_TABLERO), False),
    ("atencion", "comunidad", "Atención ciudadana",
     "Quién vino y qué se le entregó.",
     "atencion:ingreso", lambda t: t(P.REGISTRAR_ATENCION), False),
    ("casos", "comunidad", "Casos sociales",
     "Visita, informe y beneficio, con plazos.",
     "atencion:casos", lambda t: t(P.REGISTRAR_ATENCION) or t(P.VER_TABLERO), False),
    ("regalos", "comunidad", "Regalos para niños",
     "Inscripción por RUT en cada campaña.",
     "atencion:regalos", lambda t: t(P.REGISTRAR_ATENCION) or t(P.VER_TABLERO), False),

    ("validar", "supervision", "Validar evidencias",
     "Aprueba o rechaza con motivo lo registrado.",
     "gestion:validar", lambda t: t(P.VALIDAR_EVIDENCIA), False),
    ("alertas", "supervision", "Alertas",
     "Vencimientos, evidencias y registros que esperan.",
     "gestion:alertas", lambda t: t(P.VER_TABLERO), False),
    ("tablero", "supervision", "Tablero de delegación",
     "El resultado de cada persona y de la agenda.",
     "gestion:tablero", lambda t: t(P.VER_TABLERO), False),
    ("reconocimientos", "supervision", "Felicitaciones y reclamos",
     "Suman o restan al resultado.",
     "gestion:reconocimientos", lambda t: t(P.REGISTRAR_AJUSTE), False),
    ("ausencias", "supervision", "Ausencias",
     "Bajan el avance esperado.",
     "gestion:ausencias", lambda t: t(P.REGISTRAR_AJUSTE), False),
    ("informes", "supervision", "Informes",
     "Seis informes, incluido el de brechas.",
     "gestion:informes", lambda t: t(P.VER_INFORMES), False),

    ("periodos", "periodo", "Períodos",
     "Abrir, cerrar y reabrir.",
     "gestion:periodos", lambda t: t(P.CONFIGURAR_PERIODO), False),
    ("cargos", "periodo", "Cargos",
     "Las funciones que deciden las metas.",
     "gestion:cargos", lambda t: t(P.DEFINIR_META), False),
    ("metas", "periodo", "Metas y ponderadores",
     "Cuánto se pide y cuánto pesa.",
     "gestion:metas", lambda t: t(P.DEFINIR_META), False),
    ("reglas", "periodo", "Reglas de cálculo",
     "Tope, umbrales y plazos.",
     "gestion:reglas", lambda t: t(P.CONFIGURAR_PERIODO), False),
    ("historial", "periodo", "Historial de parámetros",
     "Cada versión, con su autor.",
     "gestion:historial", lambda t: t(P.CONFIGURAR_PERIODO), True),
    ("campanas", "periodo", "Campañas de regalos",
     "Navidad, Día del Niño, Aniversario.",
     "atencion:campanas", lambda t: t(P.CONFIGURAR_PERIODO), False),

    ("items", "configuracion", "Ítems y metas",
     "Lo que se mide y cómo se mide.",
     "catalogos:items", lambda t: t(P.GESTIONAR_CATALOGO), False),
    ("tipos", "configuracion", "Tipos de atención",
     "Cómo se clasifica lo que se atiende.",
     "catalogos:tipos", lambda t: t(P.GESTIONAR_CATALOGO), False),
    ("subatenciones", "configuracion", "Subatenciones",
     "El detalle de cada tipo de atención.",
     "catalogos:subatenciones", lambda t: t(P.GESTIONAR_CATALOGO), False),

    ("delegaciones", "administracion", "Delegaciones",
     "Las unidades territoriales.",
     "organizacion:delegaciones", lambda t: t(P.GESTIONAR_USUARIO), False),
    ("usuarios", "administracion", "Usuarios",
     "Quién entra, con qué rol y dónde.",
     "organizacion:usuarios", lambda t: t(P.GESTIONAR_USUARIO), False),
    ("roles", "administracion", "Roles",
     "Qué puede hacer cada rol.",
     "organizacion:roles", lambda t: t(P.GESTIONAR_USUARIO), False),
    ("auditoria", "administracion", "Auditoría",
     "Quién hizo qué y cuándo.",
     "gestion:auditoria", lambda t: t(P.VER_AUDITORIA), False),
)


@dataclass
class Modulo:
    clave: str
    titulo: str
    descripcion: str
    url: str
    nuevo: bool = False

    @property
    def icono(self):
        return mark_safe(ICONOS[self.clave])


@dataclass
class Area:
    clave: str
    nombre: str
    clase: str
    icono_clave: str
    modulos: list = field(default_factory=list)

    @property
    def icono(self):
        return mark_safe(ICONOS[self.icono_clave])


def areas_de(usuario):
    """Las áreas con los módulos que esta persona puede abrir, en el orden del menú."""
    def tiene(permiso):
        return P.tiene_permiso(usuario, permiso)

    areas = {}
    for clave, area, titulo, descripcion, url, permiso, nuevo in MODULOS:
        if not permiso(tiene):
            continue
        if area not in areas:
            nombre, clase, icono = AREAS[area]
            areas[area] = Area(clave=area, nombre=nombre, clase=clase, icono_clave=icono)
        areas[area].modulos.append(
            Modulo(clave=clave, titulo=titulo, descripcion=descripcion,
                   url=reverse(url), nuevo=nuevo))
    return [areas[a] for a in AREAS if a in areas]


# =========================================================================
# Para atender
# =========================================================================


@dataclass
class Pendiente:
    """Una fila de «Para atender». ``tono`` es bad (rojo) o warn (ámbar)."""

    tono: str
    titulo: str
    detalle: str
    url: str


def _plural(n, singular, plural=None):
    return singular if n == 1 else (plural or singular + "s")


def _compromisos(ctx):
    from gestion.modelos_agenda import Compromiso

    if ctx["activa"] is None:
        return []
    vencidos = Compromiso.objects.filter(
        delegacion=ctx["activa"], estado__in=Compromiso.ABIERTOS,
        vencimiento__lt=ctx["hoy"]).order_by("vencimiento")
    if not ctx["supervisa"]:
        vencidos = vencidos.filter(responsable=ctx["usuario"])
    lista = list(vencidos[:20])
    if not lista:
        return []
    primero = lista[0]
    if len(lista) == 1:
        return [Pendiente(
            "bad", "Compromiso vencido",
            f"{primero.codigo}, {primero.solicitante}. Venció el {primero.vencimiento:%d-%m-%Y}.",
            reverse("gestion:compromiso_detalle", args=[primero.pk]))]
    return [Pendiente(
        "bad", f"{len(lista)} compromisos vencidos",
        f"El más antiguo es {primero.codigo}, que venció el {primero.vencimiento:%d-%m-%Y}.",
        reverse("gestion:agenda") + "?plazo=vencidos" + ("" if ctx["supervisa"] else "&quien=mios"))]


_TITULO_TRAMO = {
    "programar": "Visita social sin programar a tiempo",
    "visita": "Visita social con atraso",
    "informe": "Informe social atrasado",
    "beneficio": "Beneficio sin entregar a tiempo",
    "total": "Caso social fuera de plazo",
}


def _casos(ctx):
    from atencion import plazos
    from atencion.models import CasoSocial
    from gestion import reglas as R

    if ctx["activa"] is None or not (ctx["tiene"](P.REGISTRAR_ATENCION) or ctx["supervisa"]):
        return []
    casos = (CasoSocial.objects.filter(atencion__delegacion=ctx["activa"])
             .select_related("atencion__subatencion"))
    if not ctx["supervisa"]:
        casos = casos.filter(responsable=ctx["usuario"])
    regla = R.vigente(ctx["periodo"])
    vencidos = []
    for caso in casos:
        if caso.cerrado:
            continue
        tramo = next((t for t in plazos.tramos(caso, regla, ctx["hoy"])
                      if t.estado == "vencido"), None)
        if tramo is not None:
            vencidos.append((caso, tramo))
    if not vencidos:
        return []
    if len(vencidos) == 1:
        caso, tramo = vencidos[0]
        return [Pendiente(
            "bad", _TITULO_TRAMO.get(tramo.clave, "Caso social con plazo vencido"),
            f"{caso.codigo}, {caso.atencion.subatencion.nombre}. {tramo.detalle}.",
            reverse("atencion:caso", args=[caso.pk]))]
    return [Pendiente(
        "bad", f"{len(vencidos)} casos sociales con un plazo vencido",
        "Cada uno dice en su ficha qué paso se atrasó.",
        reverse("atencion:casos") + "?situacion=abiertos")]


def _cartas(ctx):
    from gestion.modelos_cartas import Carta

    if ctx["activa"] is None or not (ctx["tiene"](P.REGISTRAR_ATENCION) or ctx["supervisa"]):
        return []
    cartas = Carta.objects.filter(
        delegacion=ctx["activa"], activo=True,
        estado=Carta.Estado.EN_PROCESO).order_by("fecha")
    if not ctx["supervisa"]:
        cartas = cartas.filter(responsable=ctx["usuario"])
    lista = list(cartas[:20])
    if not lista:
        return []
    primera = lista[0]
    if len(lista) == 1:
        return [Pendiente(
            "warn", "Carta esperando respuesta",
            f"{primera.codigo}, {primera.remitente}. Llegó el {primera.fecha:%d-%m-%Y}.",
            reverse("gestion:carta_detalle", args=[primera.pk]))]
    return [Pendiente(
        "warn", f"{len(lista)} cartas esperando respuesta",
        f"La más antigua es {primera.codigo}, que llegó el {primera.fecha:%d-%m-%Y}.",
        reverse("gestion:cartas") + "?situacion=en_proceso")]


def _actividades(ctx):
    from gestion.modelos_actividad import Actividad

    if ctx["periodo"] is None or not ctx["tiene"](P.REGISTRAR_ACTIVIDAD):
        return []
    mias = Actividad.objects.filter(funcionario=ctx["usuario"], periodo=ctx["periodo"])
    salida = []
    rechazadas = list(mias.filter(estado=Actividad.Estado.RECHAZADA).order_by("fecha")[:20])
    if len(rechazadas) == 1:
        a = rechazadas[0]
        salida.append(Pendiente(
            "bad", "Actividad rechazada",
            f"{a.codigo}, {a.accion}. Corrige la evidencia para que cuente.",
            reverse("gestion:actividad_detalle", args=[a.pk])))
    elif rechazadas:
        salida.append(Pendiente(
            "bad", f"{len(rechazadas)} actividades rechazadas",
            "Corrige su evidencia para que cuenten en tu meta.",
            reverse("gestion:actividades") + "?situacion=rechazada"))
    sin_evidencia = mias.filter(estado=Actividad.Estado.BORRADOR).count()
    if sin_evidencia:
        salida.append(Pendiente(
            "warn", f"{sin_evidencia} {_plural(sin_evidencia, 'actividad', 'actividades')} sin evidencia",
            "Mientras no tengan evidencia no se validan ni cuentan.",
            reverse("gestion:actividades") + "?situacion=borrador"))
    return salida


def _evidencias(ctx):
    from gestion.modelos_actividad import Evidencia

    if not ctx["tiene"](P.VALIDAR_EVIDENCIA):
        return []
    pendientes = Evidencia.objects.filter(decision=Evidencia.Decision.PENDIENTE)
    if ctx["visibles"] is not None:
        pendientes = pendientes.filter(actividad__delegacion_id__in=ctx["visibles"])
    cuantas = pendientes.count()
    if not cuantas:
        return []
    return [Pendiente(
        "warn", f"{cuantas} {_plural(cuantas, 'evidencia')} esperando tu decisión",
        "Aprobar o rechazar con motivo decide si cada actividad cuenta.",
        reverse("gestion:validar"))]


def _configuracion(ctx):
    from gestion import reglas as R

    if not ctx["tiene"](P.CONFIGURAR_PERIODO):
        return []
    if ctx["periodo"] is None:
        return [Pendiente(
            "warn", "No hay un período abierto",
            "Sin período abierto nadie puede registrar actividades.",
            reverse("gestion:periodos"))]
    regla = R.vigente(ctx["periodo"])
    if regla.pk and regla.es_propuesta:
        return [Pendiente(
            "warn", "La regla de cálculo sigue como propuesta",
            "Mientras no se apruebe, los resultados se rotulan como propuesta.",
            reverse("gestion:regla_detalle", args=[regla.pk]))]
    return []


PENDIENTES = (_actividades, _compromisos, _casos, _cartas, _evidencias, _configuracion)


def pendientes_de(ctx):
    """Lo que necesita acción, lo rojo primero."""
    salida = []
    for calcular in PENDIENTES:
        try:
            salida.extend(calcular(ctx))
        except Exception:  # noqa: BLE001 — ver la explicación del módulo
            continue
    return sorted(salida, key=lambda p: 0 if p.tono == "bad" else 1)


# =========================================================================
# Tu avance, o el de tus delegaciones
# =========================================================================


def _pct(valor):
    return f"{valor:.1f}".replace(".", ",") + " %"


def avance_de(ctx):
    """
    Un dict para la tarjeta de la derecha, o None si no hay nada que mostrar.

    Quien tiene metas ve su avance. Quien supervisa y no tiene metas propias
    ve el de su delegación, o cuántas de sus delegaciones van al día.
    """
    from gestion import calculo as C

    periodo = ctx["periodo"]
    if periodo is None:
        return None

    if ctx["perfil"] is not None:
        res = C.de_perfil(ctx["perfil"], periodo)
        if res.definido:
            faltan = sorted((f for f in res.items
                             if not f.meta_invalida and not f.alcanzado),
                            key=lambda f: f.cumplimiento)[:3]
            return {
                "tipo": "persona",
                "titulo": "Tu avance",
                "cifra": _pct(res.avance),
                "barra": min(100.0, res.avance),
                "marca": min(100.0, res.esperado or 0),
                "estado": res.semaforo_texto,
                "tono": {"verde": "ok", "ambar": "warn", "rojo": "bad"}.get(res.semaforo_clase, ""),
                "nota": f"La raya marca lo esperado a hoy: {_pct(res.esperado or 0)}.",
                "lista_titulo": "Donde más te falta" if faltan else "",
                "lista": [(f.item.nombre, _pct(f.cumplimiento)) for f in faltan],
                "vacio": "" if faltan else "Todos tus ítems llegaron al umbral.",
                "enlace": ("Ver mi resultado", reverse("gestion:mi_resultado")),
            }

    if not ctx["supervisa"]:
        return None
    from organizacion.models import Delegacion

    delegaciones = Delegacion.objects.filter(activo=True)
    if ctx["visibles"] is not None:
        delegaciones = delegaciones.filter(pk__in=ctx["visibles"])
    resultados = [C.de_delegacion(d, periodo) for d in delegaciones.order_by("nombre")]
    medidas = [r for r in resultados if r.promedio is not None]
    enlace = ("Ver el tablero", reverse("gestion:tablero"))

    if len(resultados) == 1:
        r = resultados[0]
        if r.promedio is None:
            return None
        return {
            "tipo": "delegacion",
            "titulo": "Tu delegación",
            "cifra": _pct(r.promedio),
            "barra": min(100.0, r.promedio),
            "marca": min(100.0, r.esperado or 0),
            "estado": r.semaforo_texto,
            "tono": {"verde": "ok", "ambar": "warn", "rojo": "bad"}.get(r.semaforo_clase, ""),
            "nota": (f"Promedio de {len(r.medidas)} {_plural(len(r.medidas), 'persona')} medidas. "
                     f"La raya marca lo esperado a hoy: {_pct(r.esperado or 0)}."),
            "lista_titulo": "", "lista": [], "vacio": "",
            "enlace": enlace,
        }

    if not medidas:
        return None
    al_dia = sum(1 for r in medidas if r.semaforo_clase == "verde")
    atrasadas = len(medidas) - al_dia
    sin_medir = len(resultados) - len(medidas)
    nota = "Delegaciones al día según su promedio frente a lo esperado."
    if sin_medir:
        nota += (f" {_plural(sin_medir, 'La otra', 'Las otras')} {sin_medir} "
                 f"todavía no {_plural(sin_medir, 'tiene', 'tienen')} personas medidas.")
    peores = sorted((r for r in medidas if r.semaforo_clase != "verde"),
                    key=lambda r: r.promedio)[:3]
    return {
        "tipo": "delegaciones",
        "titulo": "Las delegaciones",
        "cifra": f"{al_dia} de {len(medidas)}",
        "barra": al_dia * 100 / len(medidas),
        "marca": None,
        "estado": (f"{atrasadas} {_plural(atrasadas, 'atrasada')}" if atrasadas else "Todas al día"),
        "tono": "warn" if atrasadas else "ok",
        "nota": nota,
        "lista_titulo": "Las más atrasadas" if peores else "",
        "lista": [(r.delegacion.nombre, _pct(r.promedio)) for r in peores],
        "vacio": "",
        "enlace": enlace,
    }


# =========================================================================
# El período
# =========================================================================


def periodo_de(ctx):
    from gestion import calculo as C
    from gestion import reglas as R

    periodo = ctx["periodo"]
    if periodo is None:
        return None
    regla = R.vigente(periodo)
    total = C.dias_del_periodo(periodo, regla)
    corridos = C.dias_corridos(periodo, regla, ctx["hoy"])
    faltan = max(0, (periodo.termino - ctx["hoy"]).days)
    return {
        "nombre": periodo.nombre,
        "dia": corridos,
        "total": total,
        "barra": min(100.0, corridos * 100 / total) if total else 0,
        "cierra": periodo.termino,
        "faltan": faltan,
    }


# =========================================================================
# Todo junto, para la vista
# =========================================================================


def panel_de(request, activa):
    from gestion.views_actividad import periodo_abierto

    usuario = request.user
    perfil = P.perfil_de(usuario)
    visibles = None
    if perfil is not None:
        visibles = list(perfil.delegaciones_visibles().values_list("pk", flat=True))

    def tiene(permiso):
        return P.tiene_permiso(usuario, permiso)

    ctx = {
        "usuario": usuario, "perfil": perfil, "activa": activa,
        "visibles": visibles, "periodo": periodo_abierto(), "hoy": date.today(),
        "tiene": tiene, "supervisa": tiene(P.VER_TABLERO),
    }

    def seguro(funcion):
        try:
            return funcion(ctx)
        except Exception:  # noqa: BLE001 — ver la explicación del módulo
            return None

    return {
        "areas": areas_de(usuario),
        "pendientes": pendientes_de(ctx),
        "avance": seguro(avance_de),
        "periodo_panel": seguro(periodo_de),
    }

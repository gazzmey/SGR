"""
Mapa de presencia territorial.

Responde una pregunta: **¿dónde ha estado la delegación y dónde no?** Cada
territorio aparece con la fecha de la última actividad registrada en él, un
color según cuánto hace de eso y lo que hay abierto ahí: compromisos de la
agenda, gestiones sociales, juntas de vecinos e hitos.

Qué no muestra, a propósito
---------------------------
* **Ninguna casa.** El punto del mapa es el centro aproximado del territorio
  y lo escribe quien administra los territorios. No hay coordenadas de
  vecinos ni direcciones en ninguna parte de esta pantalla: todo lo que sale
  de aquí son conteos por territorio.
* **Ningún juicio sobre personas.** El color habla del territorio («hace 40
  días que nadie va»), no de quién debería haber ido. Es el mismo criterio
  del tablero (RF-031).

Dos formas de verlo
-------------------
``completo``
    Quien supervisa (tablero, validación, configuración, usuarios) o quien
    tiene el permiso de Django de ver territorios y actividades. Ve toda la
    actividad de las delegaciones que su perfil autoriza, con los nombres de
    quienes más fueron a cada territorio.
``personal``
    Quien solo registra sus actividades. Ve los mismos territorios, pero los
    números son **solo los suyos**: sus actividades, sus compromisos, sus
    casos. No aparece el nombre de nadie más.

Sin ninguno de los dos, la vista responde 403.

El alcance es el de siempre: las delegaciones que el perfil autoriza. Un
``?delegacion=`` fuera de ellas no se ignora en silencio, se rechaza.
"""

import re
import unicodedata
from collections import Counter, defaultdict
from datetime import timedelta
from urllib.parse import urlencode

from django.core.exceptions import PermissionDenied
from django.db.models import Count, Max, Q
from django.urls import reverse
from django.utils import timezone

from atencion.models import CasoSocial
from atencion.modelos_comunidad import JuntaVecinos
from comun import permisos as P
from comun.entidades import puede
from comun.formularios import nombre_de_usuario
from gestion import tablero as T
from gestion.modelos_actividad import Actividad
from gestion.modelos_agenda import Compromiso
from gestion.modelos_hitos import Hito
from gestion.models import Periodo
from organizacion.models import Delegacion, Territorio

COMPLETO = "completo"
PERSONAL = "personal"

#: Días desde la última presencia. Hasta 15, verde; hasta 30, ámbar; más,
#: o nunca, rojo. Un territorio desactivado va en gris.
VERDE_HASTA = 15
AMBAR_HASTA = 30

SEMAFORO = {
    "verde": "Presencia reciente",
    "ambar": "Hace tiempo",
    "rojo": "Sin presencia",
    "gris": "Territorio desactivado",
}

PRESENCIA = {
    "registrada": "Todo lo registrado",
    "verificada": "Solo lo verificado",
}

#: Lo que abre la vista completa por acción de negocio.
_SUPERVISION = (P.VER_TABLERO, P.VALIDAR_EVIDENCIA, P.CONFIGURAR_PERIODO, P.GESTIONAR_USUARIO)


# =========================================================================
# Quién entra y qué ve
# =========================================================================


def modo_de(usuario):
    """``completo``, ``personal`` o None si no puede abrir el mapa."""
    if not getattr(usuario, "is_authenticated", False):
        return None
    if usuario.is_superuser:
        return COMPLETO
    if any(P.tiene_permiso(usuario, clave) for clave in _SUPERVISION):
        return COMPLETO
    if puede(usuario, "territorio", "view") and puede(usuario, "actividad", "view"):
        return COMPLETO
    if P.tiene_permiso(usuario, P.REGISTRAR_ACTIVIDAD):
        return PERSONAL
    return None


def delegaciones_de(usuario):
    """Las delegaciones que puede mirar en el mapa."""
    if getattr(usuario, "is_superuser", False):
        return Delegacion.objects.filter(activo=True).order_by("nombre")
    perfil = P.perfil_de(usuario)
    if perfil is None:
        return Delegacion.objects.none()
    return perfil.delegaciones_visibles().order_by("nombre")


class Filtros:
    """Lo que se eligió arriba de la pantalla, ya comprobado."""

    def __init__(self, request, delegaciones):
        pedido = request.GET
        self.periodos = list(T.periodos_visibles())
        self.periodo = T.periodo_elegido(request)
        self.delegaciones = list(delegaciones)

        self.delegacion = None
        elegida = (pedido.get("delegacion") or "").strip()
        if elegida:
            self.delegacion = next((d for d in self.delegaciones if str(d.pk) == elegida), None)
            if self.delegacion is None:
                raise PermissionDenied("Esa delegación no está entre las que tu perfil autoriza.")

        self.presencia = "verificada" if pedido.get("presencia") == "verificada" else "registrada"
        self.origen = pedido.get("origen") if pedido.get("origen") in Actividad.Origen.values else ""
        self.tipo = pedido.get("tipo") if pedido.get("tipo") in Actividad.Tipo.values else ""

        hoy = timezone.localdate()
        if self.periodo is not None and self.periodo.termino < hoy:
            self.referencia = self.periodo.termino
        else:
            self.referencia = hoy
        self.hoy = hoy
        self._comparacion()

    def _comparacion(self):
        """
        Con qué se compara: el trimestre anterior, **a la misma altura**.

        Si el trimestre elegido está en curso, comparar sus 46 días con los
        91 del anterior completo haría que todo pareciera bajar. Se cuenta el
        anterior solo hasta el mismo día del trimestre: el día 46 contra el
        día 46. Con el trimestre ya cerrado, se comparan los dos completos.
        """
        self.anterior = self.corte = None
        self.misma_altura = False
        if self.periodo is None:
            return
        self.anterior = (Periodo.objects.filter(activo=True, termino__lt=self.periodo.inicio)
                         .order_by("-termino").first())
        if self.anterior is None:
            return
        if self.periodo.termino >= self.hoy:
            transcurridos = max(0, (self.hoy - self.periodo.inicio).days)
            self.corte = min(self.anterior.termino, self.anterior.inicio + timedelta(days=transcurridos))
            self.misma_altura = True
        else:
            self.corte = self.anterior.termino

    def comparacion_texto(self):
        if self.anterior is None:
            return ""
        if self.misma_altura:
            return "%s hasta el %s, a la misma altura del trimestre" % (
                self.anterior.nombre, self.corte.strftime("%d-%m-%Y"))
        return "%s completo" % self.anterior.nombre

    @property
    def ids(self):
        if self.delegacion is not None:
            return [self.delegacion.pk]
        return [d.pk for d in self.delegaciones]

    @property
    def activos(self):
        """Cuántos filtros de actividad cambian lo que se cuenta."""
        return sum(1 for valor in (self.origen, self.tipo) if valor) + (self.presencia == "verificada")

    def como_texto(self):
        partes = [PRESENCIA[self.presencia].lower()]
        if self.origen:
            partes.append(Actividad.Origen(self.origen).label.lower())
        if self.tipo:
            partes.append("tipo " + Actividad.Tipo(self.tipo).label.lower())
        return ", ".join(partes)


# =========================================================================
# Cómo se reconoce un territorio escrito a mano
# =========================================================================


def normalizar(texto):
    """«Unidad vecinal 3 · San Juan» → «unidad vecinal 3 san juan»."""
    texto = unicodedata.normalize("NFKD", texto or "")
    texto = "".join(c for c in texto if not unicodedata.combining(c)).lower()
    return re.sub(r"[^a-z0-9ñ]+", " ", texto).strip()


def _reconocedor(territorios):
    """
    Un diccionario (delegación, texto normalizado) → territorio.

    La agenda guarda el territorio como texto libre. Se reconoce por el
    nombre completo, por el código y por la parte que va después del «·»
    («San Juan» en «Unidad vecinal 3 · San Juan»), esta última solo si no
    se repite dentro de la delegación: ante la duda, no se adivina.
    """
    exactos, cortos = {}, defaultdict(set)
    for t in territorios:
        exactos[(t.delegacion_id, normalizar(t.nombre))] = t.pk
        exactos[(t.delegacion_id, normalizar(t.codigo))] = t.pk
        if "·" in t.nombre:
            corto = normalizar(t.nombre.rsplit("·", 1)[1])
            if len(corto) >= 4:
                cortos[(t.delegacion_id, corto)].add(t.pk)
    for clave, encontrados in cortos.items():
        if len(encontrados) == 1 and clave not in exactos:
            exactos[clave] = next(iter(encontrados))
    return exactos


# =========================================================================
# Los datos de cada territorio
# =========================================================================


def _actividades(filtros, usuario, modo, ids_territorios):
    consulta = (Actividad.objects
                .filter(territorio_id__in=ids_territorios)
                .exclude(estado=Actividad.Estado.ANULADA))
    if filtros.origen:
        consulta = consulta.filter(origen=filtros.origen)
    if filtros.tipo:
        consulta = consulta.filter(tipo=filtros.tipo)
    if modo == PERSONAL:
        consulta = consulta.filter(Q(funcionario=usuario) | Q(responsable=usuario))
    return consulta


def _medida(consulta, filtros):
    """Las que cuentan como presencia según el filtro «Contar»."""
    if filtros.presencia == "verificada":
        return consulta.filter(estado=Actividad.Estado.APROBADA)
    return consulta


def semaforo(dias, activo=True):
    if not activo:
        return "gris"
    if dias is None or dias > AMBAR_HASTA:
        return "rojo"
    if dias > VERDE_HASTA:
        return "ambar"
    return "verde"


def hace_texto(dias):
    if dias is None:
        return "Nunca"
    if dias == 0:
        return "Hoy"
    if dias == 1:
        return "Ayer"
    return f"Hace {dias} días"


def calcular(usuario, filtros, modo):
    """
    Todo lo que la pantalla muestra, en estructuras simples.

    Devuelve un diccionario con ``territorios`` (una entrada por territorio,
    lista para convertirse en JSON), ``resumen`` y ``sin_ubicar``.
    """
    periodo = filtros.periodo
    territorios = list(
        Territorio.objects.filter(delegacion_id__in=filtros.ids)
        .select_related("delegacion").order_by("delegacion__nombre", "nombre")
    )
    ids = [t.pk for t in territorios]

    base = _actividades(filtros, usuario, modo, ids)
    medida = _medida(base, filtros)

    # Última presencia: la actividad más reciente hasta la fecha de
    # referencia, de cualquier trimestre. Si se mirara solo el trimestre,
    # el primer día de cada uno todo el mapa amanecería en rojo.
    ultima = dict(
        medida.filter(fecha__lte=filtros.referencia)
        .values_list("territorio_id").annotate(m=Max("fecha"))
    )

    del_periodo = base.filter(periodo=periodo) if periodo else base.none()
    conteos = {
        fila["territorio_id"]: fila for fila in
        del_periodo.values("territorio_id").annotate(
            registradas=Count("id"),
            verificadas=Count("id", filter=Q(estado=Actividad.Estado.APROBADA)),
        )
    }

    # El mismo conteo en el trimestre anterior, hasta la misma altura.
    anteriores = {}
    if filtros.anterior is not None:
        previo = _medida(base.filter(periodo=filtros.anterior, fecha__lte=filtros.corte), filtros)
        anteriores = dict(previo.values_list("territorio_id").annotate(n=Count("id")))

    por_tipo = defaultdict(list)
    etiquetas_tipo = dict(Actividad.Tipo.choices)
    for fila in (_medida(del_periodo, filtros).values("territorio_id", "tipo")
                 .annotate(n=Count("id")).order_by("territorio_id", "-n", "tipo")):
        por_tipo[fila["territorio_id"]].append([etiquetas_tipo.get(fila["tipo"], fila["tipo"]), fila["n"]])

    quienes = defaultdict(list)
    if modo == COMPLETO:
        filas = (_medida(del_periodo, filtros)
                 .values("territorio_id", "funcionario_id").annotate(n=Count("id"))
                 .order_by("territorio_id", "-n"))
        personas = {}
        for fila in filas:
            if len(quienes[fila["territorio_id"]]) < 3:
                personas.setdefault(fila["funcionario_id"], None)
                quienes[fila["territorio_id"]].append(fila)
        if personas:
            from django.contrib.auth import get_user_model

            nombres = {u.pk: nombre_de_usuario(u) for u in
                       get_user_model().objects.filter(pk__in=personas)}
            for lista in quienes.values():
                for i, fila in enumerate(lista):
                    lista[i] = {"nombre": nombres.get(fila["funcionario_id"], "—"), "n": fila["n"]}

    gestiones = _gestiones(filtros, usuario, modo, ids)
    agenda, sin_reconocer = _compromisos(filtros, usuario, modo, territorios)
    juntas = _juntas(filtros, territorios) if _ve_juntas(usuario, modo) else {}
    hitos = _hitos(filtros, usuario, modo, ids)

    acciones = Acciones(usuario, modo, filtros)
    filas = []
    for t in territorios:
        conteo = conteos.get(t.pk, {})
        registradas = conteo.get("registradas", 0)
        verificadas = conteo.get("verificadas", 0)
        compromisos = agenda.get(t.pk, {})
        # Un territorio desactivado solo se muestra si todavía tiene algo.
        if not t.activo and not (registradas or compromisos.get("abiertos")):
            continue
        fecha = ultima.get(t.pk)
        dias = (filtros.referencia - fecha).days if fecha else None
        color = semaforo(dias, t.activo)
        filas.append({
            "id": t.pk,
            "codigo": t.codigo,
            "nombre": t.nombre,
            "delegacion": t.delegacion.nombre,
            "delegacion_id": t.delegacion_id,
            "activo": t.activo,
            "lat": float(t.latitud) if t.latitud is not None else None,
            "lng": float(t.longitud) if t.longitud is not None else None,
            "ultima": fecha.strftime("%d-%m-%Y") if fecha else None,
            "dias": dias,
            "hace": hace_texto(dias),
            "semaforo": color,
            "semaforo_texto": SEMAFORO[color],
            "registradas": registradas,
            "verificadas": verificadas,
            "medida": verificadas if filtros.presencia == "verificada" else registradas,
            "anterior": anteriores.get(t.pk, 0) if filtros.anterior is not None else None,
            "cambio": ((verificadas if filtros.presencia == "verificada" else registradas)
                       - anteriores.get(t.pk, 0)) if filtros.anterior is not None else None,
            "por_tipo": por_tipo.get(t.pk, []),
            "gestiones": gestiones.get(t.pk, 0),
            "abiertos": compromisos.get("abiertos", 0),
            "vencidos": compromisos.get("vencidos", 0),
            "realizados": compromisos.get("realizados", 0),
            "juntas": juntas.get(t.pk, []),
            "socios": sum(j["socios"] for j in juntas.get(t.pk, [])),
            "hitos": hitos.get(t.pk, 0),
            "quienes": quienes.get(t.pk, []),
            "acciones": acciones.de(t),
        })

    ubicados = [f for f in filas if f["lat"] is not None]
    cuenta = Counter(f["semaforo"] for f in filas)
    return {
        "territorios": filas,
        "ubicados": len(ubicados),
        "sin_ubicar": [f for f in filas if f["lat"] is None],
        "sin_reconocer": sin_reconocer,
        "resumen": {
            "total": len(filas),
            "verde": cuenta["verde"],
            "ambar": cuenta["ambar"],
            "rojo": cuenta["rojo"],
            "gris": cuenta["gris"],
            "actividades": sum(f["medida"] for f in filas),
            "vencidos": sum(f["vencidos"] for f in filas),
            "abiertos": sum(f["abiertos"] for f in filas),
            "suben": sum(1 for f in filas if f["anterior"] is not None and f["medida"] > f["anterior"]),
            "bajan": sum(1 for f in filas if f["anterior"] is not None and f["medida"] < f["anterior"]),
        },
    }


def compromisos_abiertos(filtros, usuario, modo, territorios):
    """
    Los compromisos abiertos de cada territorio, de cualquier trimestre: los
    que conviene tener a mano en una salida a terreno. En la vista personal,
    solo los propios.
    """
    consulta = (Compromiso.objects
                .filter(delegacion_id__in={t.delegacion_id for t in territorios},
                        estado__in=Compromiso.ABIERTOS)
                .order_by("vencimiento", "codigo"))
    if modo == PERSONAL:
        consulta = consulta.filter(responsable=usuario)
    reconoce = _reconocedor(territorios)
    resultado = defaultdict(list)
    for c in consulta:
        pk = reconoce.get((c.delegacion_id, normalizar(c.territorio)))
        if pk is not None:
            resultado[pk].append(c)
    return resultado


def distancia_km(a, b):
    """Distancia en línea recta entre dos puntos (latitud, longitud), en km."""
    import math

    la1, lo1, la2, lo2 = (math.radians(float(v)) for v in (a[0], a[1], b[0], b[1]))
    h = (math.sin((la2 - la1) / 2) ** 2
         + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2)
    return 6371.0 * 2 * math.asin(math.sqrt(h))


def _gestiones(filtros, usuario, modo, ids):
    """Gestiones sociales del trimestre, por el territorio del beneficiario."""
    periodo = filtros.periodo
    if periodo is None:
        return {}
    consulta = (CasoSocial.objects
                .filter(atencion__solicitante__territorio_id__in=ids,
                        ingreso__range=(periodo.inicio, periodo.termino))
                .exclude(estado=CasoSocial.Estado.ANULADO))
    if modo == PERSONAL:
        consulta = consulta.filter(responsable=usuario)
    return dict(consulta.values_list("atencion__solicitante__territorio_id")
                .annotate(n=Count("id")))


def _compromisos(filtros, usuario, modo, territorios):
    """
    Compromisos del trimestre por territorio, y cuántos no se reconocieron.

    Se cuentan los vigentes (los anulados dejaron de ser una deuda). Vencido
    es abierto con el plazo ya pasado a hoy: un compromiso de un trimestre
    anterior que sigue abierto sigue estando vencido.
    """
    periodo = filtros.periodo
    if periodo is None:
        return {}, 0
    consulta = (Compromiso.objects.filter(delegacion_id__in=filtros.ids, periodo=periodo)
                .exclude(estado=Compromiso.Estado.ANULADO))
    if modo == PERSONAL:
        consulta = consulta.filter(responsable=usuario)
    reconoce = _reconocedor(territorios)
    con_territorios = {t.delegacion_id for t in territorios}
    resultado = defaultdict(lambda: {"abiertos": 0, "vencidos": 0, "realizados": 0})
    sin_reconocer = 0
    for delegacion_id, texto, estado, vence in consulta.values_list(
            "delegacion_id", "territorio", "estado", "vencimiento"):
        pk = reconoce.get((delegacion_id, normalizar(texto)))
        if pk is None:
            # Una delegación sin territorios no está en el mapa: no hay con
            # qué reconocer, así que tampoco se avisa.
            if delegacion_id in con_territorios:
                sin_reconocer += 1
            continue
        if estado in Compromiso.ABIERTOS:
            resultado[pk]["abiertos"] += 1
            if vence and vence < filtros.hoy:
                resultado[pk]["vencidos"] += 1
        elif estado == Compromiso.Estado.REALIZADO:
            resultado[pk]["realizados"] += 1
    return dict(resultado), sin_reconocer


def _ve_juntas(usuario, modo):
    return modo == COMPLETO or puede(usuario, "junta", "view")


def _juntas(filtros, territorios):
    """
    Las juntas vigentes de cada territorio, con sus socios y el último
    contacto: el compromiso más reciente que pidió la junta o la actividad
    más reciente coordinada con ella, de cualquier trimestre.
    """
    ids = [t.pk for t in territorios]
    juntas = list(
        JuntaVecinos.objects.filter(territorio_id__in=ids, activo=True)
        .annotate(socios=Count("participaciones", filter=Q(participaciones__activo=True)))
        .order_by("nombre")
    )
    if not juntas:
        return {}
    # El nombre de una junta es largo y propio («junta de vecinos el
    # mirador»), así que basta que aparezca dentro del texto: «Directiva de
    # la Junta de Vecinos El Mirador» cuenta como contacto con ella.
    por_delegacion = defaultdict(list)
    for j in juntas:
        por_delegacion[j.delegacion_id].append((" %s " % normalizar(j.nombre), j))
    contacto = {}

    def anotar(delegacion_id, texto, fecha):
        if not fecha or fecha > filtros.referencia:
            return
        texto = " %s " % normalizar(texto)
        for nombre, junta in por_delegacion.get(delegacion_id, ()):
            if nombre in texto and (contacto.get(junta.pk) is None or fecha > contacto[junta.pk]):
                contacto[junta.pk] = fecha

    for deleg, texto, creado in (Compromiso.objects
                                 .filter(delegacion_id__in=filtros.ids)
                                 .exclude(estado=Compromiso.Estado.ANULADO)
                                 .values_list("delegacion_id", "solicitante", "creado")):
        anotar(deleg, texto, timezone.localdate(creado) if creado else None)
    for deleg, texto, fecha in (Actividad.objects
                                .filter(delegacion_id__in=filtros.ids)
                                .exclude(contacto="").exclude(estado=Actividad.Estado.ANULADA)
                                .values_list("delegacion_id", "contacto", "fecha")):
        anotar(deleg, texto, fecha)

    resultado = defaultdict(list)
    for j in juntas:
        fecha = contacto.get(j.pk)
        resultado[j.territorio_id].append({
            "nombre": j.nombre,
            "socios": j.socios,
            "contacto": fecha.strftime("%d-%m-%Y") if fecha else None,
            "dias": (filtros.referencia - fecha).days if fecha else None,
        })
    return dict(resultado)


def _hitos(filtros, usuario, modo, ids):
    """Hitos activos que tocan el trimestre, en ese territorio."""
    periodo = filtros.periodo
    if periodo is None:
        return {}
    consulta = Hito.objects.filter(
        territorio_id__in=ids, activo=True,
        fecha_inicio__lte=periodo.termino, fecha_termino__gte=periodo.inicio,
    )
    if modo == PERSONAL:
        consulta = consulta.filter(responsables=usuario)
    return dict(consulta.values_list("territorio_id").annotate(n=Count("id", distinct=True)))


# =========================================================================
# Lo que se puede hacer desde un territorio
# =========================================================================


class Acciones:
    """
    Los botones del panel de cada territorio, según lo que puede hacer quien
    mira. Esconder un botón es cortesía: la vista de destino vuelve a
    comprobar el permiso igual.
    """

    def __init__(self, usuario, modo, filtros):
        self.usuario = usuario
        self.modo = modo
        self.filtros = filtros
        self.perfil = P.perfil_de(usuario)
        hay_abierto = Periodo.objects.filter(estado=Periodo.Estado.ABIERTO, activo=True).exists()
        self.registro = hay_abierto and puede(usuario, "actividad", "add")
        self.propia = (hay_abierto and P.tiene_permiso(usuario, P.REGISTRAR_ACTIVIDAD)
                       and self.perfil is not None and self.perfil.cargo_asignado is not None)
        self.agenda = hay_abierto and P.tiene_permiso(usuario, P.REGISTRAR_ACTIVIDAD) and self.perfil is not None
        self.lista = puede(usuario, "actividad", "view")
        self.ficha = puede(usuario, "territorio", "view")
        self.ubicar = puede(usuario, "territorio", "change")

    @staticmethod
    def _url(nombre, args=None, **parametros):
        url = reverse(nombre, args=args)
        return f"{url}?{urlencode(parametros)}" if parametros else url

    def de(self, t):
        botones = []
        if t.activo:
            if self.registro:
                botones.append({"texto": "Registrar actividad aquí", "corto": "Registrar aquí",
                                "principal": True,
                                "url": self._url("gestion:registro_actividad_nueva",
                                                 territorio=t.pk, delegacion=t.delegacion_id)})
            elif self.propia and self.perfil.delegacion_id == t.delegacion_id:
                botones.append({"texto": "Registrar actividad aquí", "corto": "Registrar aquí",
                                "principal": True,
                                "url": self._url("gestion:actividad_nueva", territorio=t.pk)})
            if self.agenda:
                botones.append({"texto": "Crear compromiso aquí", "corto": "Crear compromiso",
                                "principal": not botones,
                                "url": self._url("gestion:compromiso_nuevo",
                                                 territorio=t.nombre, delegacion=t.delegacion_id)})
        if self.lista:
            botones.append({"texto": "Ver sus actividades", "principal": False,
                            "url": self._url("gestion:registro_actividades", q=t.nombre)})
        if self.ficha:
            botones.append({"texto": "Ver la ficha del territorio", "principal": False,
                            "url": self._url("organizacion:territorio_detalle", args=[t.pk])})
        if self.ubicar and t.latitud is None:
            botones.append({"texto": "Ubicarlo en el mapa", "principal": False,
                            "url": self._url("organizacion:territorio_editar", args=[t.pk])})
        return botones
